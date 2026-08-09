# 🤖 AI Usage Log (`PROMPTS.md`)

**Project:** AI Interview Agent - Cohort Evaluator  
**Workflow Paradigm:** AI-Assisted "Vibe-Coding" & Architecture Co-Design

This document outlines the synthetic prompt engineering and iterative AI collaboration used to build this submission. The prompts were designed to guide the AI from high-level system architecture down to specific, edge-case resilient implementations.

---

## Phase 1: System Architecture & Serverless Strategy

**Prompt:** 
> "Act as a Principal Staff Engineer. I am building an AI Interview Agent for a hackathon. It must be deployed on Vercel Serverless using Python (FastAPI). The API contract requires a single `POST /api/interview` endpoint that maintains conversation state. Given that Vercel spins down lambdas, design an architecture that persists multi-turn interview context, enforces a minimum 8-question constraint, and returns a strict JSON feedback object at the end."

*   **AI Output Summary:** The AI proposed using **Upstash Redis (KV)** for stateless session persistence keyed by `sessionId`. It mapped out a state machine flow: Initialize $\rightarrow$ Retrieve State $\rightarrow$ Increment Turn Counter $\rightarrow$ Break at Turn 8 $\rightarrow$ Generate JSON Evaluation.

---

## Phase 2: RAG Pipeline & Contextual Grounding

**Prompt:**
> "Write the Python logic to parse the provided `curriculum.json` and `candidates.json` files. Create an adaptive function called `build_interview_agenda`. This function must cross-reference a candidate's profile and dynamically select exactly 4 distinct curriculum days. Prioritize days where the candidate's `attempts >= 3` or `skipped` is true. Then, write a system prompt template that ingests this tailored agenda so the LLM acts as a strict technical evaluator."

*   **AI Output Summary:** The AI generated the data parsing logic and the dynamic prompt template. It successfully implemented the logic to isolate candidate weaknesses and dynamically inject specific tools and objectives from the curriculum into the LLM's system prompt, ensuring the interview is deeply personalized rather than generic.

---

## Phase 3: Enforcing Structured Output

**Prompt:**
> "The final API response must return a specific JSON schema when the interview concludes (turn 8). The required keys are: `summary` (string), `strengths` (array), `gaps` (array), and `next` (array). Write the Pydantic models for this and the specific LLM function call using OpenAI's `response_format: { "type": "json_object" }` to guarantee the evaluation never breaks the API contract."

*   **AI Output Summary:** The AI provided the `Feedback` and `InterviewResponse` Pydantic models. It also wrote the `generate_final_evaluation` function, optimizing the prompt instructions to ensure the LLM strictly adhered to the array formats for strengths and gaps based on the full conversation transcript.

---

## Phase 4: Enterprise UI/UX Engineering

**Prompt:**
> "Now, act as a Senior Frontend Developer. Write a single-file Vanilla JS and HTML frontend using Tailwind CSS. Do not make it a standard chat app; make it look like an enterprise SaaS analytics dashboard. Requirements: 
> 1. Dark mode glassmorphism UI.
> 2. A sidebar to mock candidate selection.
> 3. A live progress bar tracking the 8-turn requirement.
> 4. When the API returns `done: true`, trigger a highly visual, grid-based modal that renders the JSON feedback arrays with appropriate Lucide icons (e.g., green checks for strengths, red flags for gaps)."

*   **AI Output Summary:** The AI generated the complete `index.html` file. It implemented centralized state management within the Vanilla JS script to handle asynchronous API calls, loading states (typing indicators), and the seamless DOM injection of the final structured evaluation modal.

---

## Phase 5: Debugging & Edge Cases

**Prompt:**
> "The LLM is occasionally asking two questions in a single response, which ruins the pacing of the interview. Refine the main system prompt to strictly enforce a 'one question per turn' rule. Also, add fallback logic in the Redis connection so that if the KV store fails to connect, the application gracefully degrades to an in-memory dictionary for local testing."

*   **AI Output Summary:** The AI updated the system instructions with explicit constraints ("Keep each response concise (1-2 sentences) and ask only ONE direct question per turn"). It also provided the `try/except` block for the Redis client, seamlessly switching to a standard Python dictionary if the `REDIS_URL` environment variable was missing.