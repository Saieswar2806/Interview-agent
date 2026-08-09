# 🎙️ AI Interview Agent - Cohort Evaluator

An autonomous, adaptive AI Interview Agent built for the ABTalks AI Cohort Hackathon. This agent conducts dynamic, multi-turn technical interviews based on a candidate's specific learning journey, seamlessly adapting its questions to probe technical gaps and evaluate core competencies.

## 🚀 Live Demo
**[Insert your Vercel URL here, e.g., https://my-interview-agent.vercel.app]**

## ✨ Key Features
* **Adaptive Curriculum Grounding (RAG):** Dynamically selects 4-5 core curriculum days based on the candidate's historical performance (targeting missions with high attempts or skipped status).
* **Stateful Serverless Memory:** Uses Upstash Redis (Vercel KV) to maintain conversation history across stateless API calls, ensuring natural follow-up questions.
* **Intelligent Turn-Pacing:** Enforces the minimum 8-question requirement before concluding the interview and generating the final evaluation.
* **Structured Feedback Dashboard:** Produces a strictly formatted JSON evaluation (Summary, Strengths, Gaps, Next Steps) rendered into a premium gamified UI.
* **Blazing Fast Inference:** Powered by Groq (Llama-3.3-70b) for near-zero latency conversational flow.

## 🛠️ Tech Stack
* **Backend:** Python, FastAPI, Vercel Serverless Functions
* **Frontend:** Vanilla JavaScript, HTML5, Tailwind CSS, Lucide Icons
* **AI / LLM:** Groq API (OpenAI-Compatible SDK)
* **Database:** Upstash Redis (Session State)

## 📦 Local Development

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/saieswar.2806/interview-agent.git](https://github.com/saieswar2806/interview-agent.git)
   cd interview-agent