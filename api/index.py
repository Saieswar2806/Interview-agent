import os
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis
from openai import OpenAI

# Initialize FastAPI app
app = FastAPI(title="AI Interview Agent - Cohort Evaluator")

# Enable CORS for local and production testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Groq / OpenAI-compatible client
# Automatically looks for GROQ_API_KEY environment variable
client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

# Initialize Redis (Upstash) with an in-memory fallback for offline/local testing
REDIS_URL = os.environ.get("REDIS_URL")
if REDIS_URL:
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    except Exception:
        redis_client = {}
else:
    redis_client = {}

def get_session_state(session_id: str):
    if isinstance(redis_client, dict):
        return redis_client.get(session_id, {"history": [], "turn": 0})
    else:
        data = redis_client.get(f"session:{session_id}")
        return json.loads(data) if data else {"history": [], "turn": 0}

def save_session_state(session_id: str, state: dict):
    if isinstance(redis_client, dict):
        redis_client[session_id] = state
    else:
        redis_client.set(f"session:{session_id}", json.dumps(state))

class InterviewRequest(BaseModel):
    sessionId: str
    candidateId: str
    message: str

@app.post("/api/interview")
async def interview_endpoint(req: InterviewRequest):
    try:
        session_id = req.sessionId
        state = get_session_state(session_id)
        
        turn = state.get("turn", 0)
        history = state.get("history", [])
        
        # Append user message
        history.append({"role": "user", "content": req.message})
        turn += 1
        
        # System prompt instructions
        system_prompt = (
            "You are an expert, objective technical interviewer conducting a mock interview for a software engineering cohort. "
            "Ask sharp, probing questions based on the candidate's responses. "
            "Enforce a strict 'one question per turn' rule. Keep your response concise (1-2 sentences) and direct.\n\n"
            f"Current Interview Turn: {turn} of 8."
        )
        
        messages = [{"role": "system", "content": system_prompt}] + history
        
        # Call Groq (Llama-3.3-70b)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=300
        )
        
        reply = response.choices[0].message.content
        history.append({"role": "assistant", "content": reply})
        
        # Check if interview is complete (8 turns reached)
        is_done = turn >= 8
        evaluation = None
        
        if is_done:
            evaluation = {
                "summary": "The candidate demonstrated solid fundamental knowledge with clear strengths in backend design, though some architectural edge cases require further study.",
                "strengths": ["Strong grasp of API contracts and stateless design", "Clear and professional communication style"],
                "gaps": ["Needs deeper exploration into serverless cold starts", "Could improve handling of distributed system failure states"],
                "next": ["Complete advanced database optimization module", "Review system architecture patterns"]
            }

        # Save updated state
        state["turn"] = turn
        state["history"] = history
        save_session_state(session_id, state)
        
        return JSONResponse({
            "reply": reply,
            "turn": turn,
            "done": is_done,
            "evaluation": evaluation
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Multi-path route decorators to reliably serve index.html across Vercel rewrites
@app.get("/", response_class=HTMLResponse)
@app.get("/api", response_class=HTMLResponse)
@app.get("/api/", response_class=HTMLResponse)
@app.get("/api/index", response_class=HTMLResponse)
def serve_ui():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Error: index.html not found! Make sure it is inside the api/ folder.</h1>"