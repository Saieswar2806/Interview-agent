import os
import json
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import redis
from fastapi.responses import HTMLResponse
from fastapi.responses import HTMLResponse
import os

# Load variables from .env file
load_dotenv()

app = FastAPI(title="AI Interview Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
def serve_ui():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()
    
# Use Groq free tier via OpenAI-compatible SDK
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("API Key missing! Please set GROQ_API_KEY in your .env file.")

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# Groq's best production model
MODEL_NAME = "llama-3.3-70b-versatile"

# ---------------------------------------------------------------------------
# Storage Layer: Upstash Redis (Vercel Serverless) with In-Memory Fallback
# ---------------------------------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL") or os.getenv("KV_URL")
memory_store: Dict[str, str] = {}

redis_client = None
if REDIS_URL:
    try:
        redis_client = redis.from_url(REDIS_URL)
    except Exception as e:
        print(f"Redis connection failed, defaulting to in-memory: {e}")

def save_session(session_id: str, data: dict):
    serialized = json.dumps(data)
    if redis_client:
        redis_client.setex(f"session:{session_id}", 86400, serialized)
    else:
        memory_store[session_id] = serialized

def get_session(session_id: str) -> Optional[dict]:
    if redis_client:
        val = redis_client.get(f"session:{session_id}")
        if val:
            return json.loads(val.decode("utf-8") if isinstance(val, bytes) else val)
        return None
    val = memory_store.get(session_id)
    return json.loads(val) if val else None

# ---------------------------------------------------------------------------
# Curriculum Loader & Adaptive Agenda Builder
# ---------------------------------------------------------------------------
CURRICULUM_PATH = os.path.join(os.path.dirname(__file__), "curriculum.json")
try:
    with open(CURRICULUM_PATH, "r", encoding="utf-8") as f:
        CURRICULUM_DATA = json.load(f)
except Exception:
    CURRICULUM_DATA = {"days": []}

def build_interview_agenda(candidate_data: dict) -> List[dict]:
    missions = candidate_data.get("missions", [])
    struggled_day_ids = [
        m["day"] for m in missions if m.get("skipped") or m.get("attempts", 1) >= 3
    ]
    
    all_days = {d["day"]: d for d in CURRICULUM_DATA.get("days", [])}
    
    selected_day_ids = [d_id for d_id in struggled_day_ids if d_id in all_days]
    
    core_milestones = [7, 10, 13, 21, 23, 28]
    for day_id in core_milestones:
        if day_id not in selected_day_ids and day_id in all_days:
            selected_day_ids.append(day_id)
        if len(selected_day_ids) >= 5:
            break

    return [all_days[d_id] for d_id in selected_day_ids[:5]]

# ---------------------------------------------------------------------------
# API Contract Models
# ---------------------------------------------------------------------------
class Feedback(BaseModel):
    summary: str
    strengths: List[str]
    gaps: List[str]
    next: List[str]

class InterviewRequest(BaseModel):
    sessionId: str
    candidate: Optional[Dict[str, Any]] = None
    message: Optional[str] = None

class InterviewResponse(BaseModel):
    reply: str
    done: bool = False
    feedback: Optional[Feedback] = None

# ---------------------------------------------------------------------------
# LLM Orchestrator
# ---------------------------------------------------------------------------
def generate_interviewer_system_prompt(session_data: dict) -> str:
    candidate = session_data.get("candidate", {})
    member = candidate.get("member", {})
    agenda = session_data.get("agenda", [])
    
    agenda_str = "\n".join([
        f"- Day {d['day']}: {d['title']} (Tools: {', '.join(d.get('tools', []))})"
        for d in agenda
    ])
    
    return f"""You are a Principal AI Architect conducting a rigorous, professional technical interview.
You are evaluating a candidate completing a 31-day enterprise AI Cohort.

CANDIDATE PROFILE:
- Name: {member.get('name', 'Candidate')}
- Current Role: {member.get('jobRole', 'Software Engineer')} ({member.get('yearsExperience', 0)} years experience)
- Education: {member.get('education', 'N/A')}

TARGET CURRICULUM TOPICS (Cover these across the interview):
{agenda_str}

CANDIDATE SIGNALS & MISSIONS:
{json.dumps(candidate.get('missions', []))}

INTERVIEW RULES:
1. Conduct an authentic, multi-turn technical discussion. Do not act like a static quiz bot.
2. Probe areas where the candidate had multiple attempts or skipped missions to test their conceptual depth.
3. Adapt tone according to their experience level.
4. If a response is shallow, ask an intelligent technical follow-up before moving to the next topic.
5. Keep each response concise (1-2 sentences) and ask only ONE direct question per turn.
"""

def generate_final_evaluation(session_data: dict) -> Feedback:
    eval_prompt = f"""You are an elite AI technical interviewer conducting a final evaluation.

CANDIDATE PROFILE:
{json.dumps(session_data.get('candidate', {}).get('member', {}))}

FULL INTERVIEW TRANSCRIPT:
{json.dumps(session_data.get('history', []))}

Evaluate their technical depth and problem-solving.
Return ONLY a valid JSON object matching this schema:
{{
  "summary": "2-3 sentences summarizing their readiness and performance.",
  "strengths": ["Concise, specific technical strength 1", "Strength 2"],
  "gaps": ["Concise, specific technical gap 1", "Gap 2"],
  "next": ["Concise, actionable improvement recommendation 1", "Recommendation 2"]
}}
"""
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": eval_prompt}],
        response_format={"type": "json_object"},
        temperature=0.3
    )
    
    data = json.loads(response.choices[0].message.content)
    return Feedback(
        summary=data.get("summary", ""),
        strengths=data.get("strengths", []),
        gaps=data.get("gaps", []),
        next=data.get("next", [])
    )

# ---------------------------------------------------------------------------
# Main /api/interview Endpoint
# ---------------------------------------------------------------------------
@app.post("/api/interview", response_model=InterviewResponse)
def handle_interview(payload: InterviewRequest):
    session_id = payload.sessionId

    # 1. Turn 1: Initialize New Session
    if payload.candidate is not None:
        agenda = build_interview_agenda(payload.candidate)
        session_data = {
            "sessionId": session_id,
            "candidate": payload.candidate,
            "agenda": agenda,
            "history": [],
            "question_count": 0
        }
        
        system_prompt = generate_interviewer_system_prompt(session_data)
        init_instruction = (
            "Start the interview. Welcome the candidate by name, acknowledge their background briefly, "
            "and ask your first technical question focused on one of the target curriculum topics."
        )
        
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": init_instruction}
            ],
            temperature=0.7
        )
        
        reply = completion.choices[0].message.content
        session_data["history"].append({"role": "assistant", "content": reply})
        session_data["question_count"] = 1
        
        save_session(session_id, session_data)
        return InterviewResponse(reply=reply, done=False)

    # 2. Conversation Turn
    session_data = get_session(session_id)
    if not session_data:
        raise HTTPException(
            status_code=400,
            detail=f"Session '{session_id}' not found. You must initialize with a candidate object first."
        )

    user_message = payload.message or ""
    session_data["history"].append({"role": "user", "content": user_message})
    
    # 3. Check for Completion (8 questions minimum)
    if session_data.get("question_count", 0) >= 8:
        feedback = generate_final_evaluation(session_data)
        session_data["done"] = True
        save_session(session_id, session_data)
        
        return InterviewResponse(
            reply="Thank you for taking the time to complete this technical interview. We have concluded the evaluation. Here is your structured performance feedback.",
            done=True,
            feedback=feedback
        )

    # 4. Generate Follow-up / Next Question
    system_prompt = generate_interviewer_system_prompt(session_data)
    messages = [{"role": "system", "content": system_prompt}] + session_data["history"]

    completion = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.7
    )
    
    reply = completion.choices[0].message.content
    session_data["history"].append({"role": "assistant", "content": reply})
    session_data["question_count"] += 1
    
    save_session(session_id, session_data)
    return InterviewResponse(reply=reply, done=False)

@app.get("/", response_class=HTMLResponse)
def serve_ui():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Error: index.html not found!</h1>"