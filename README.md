# AI Assistant — Phase 1/2 (Auth + Chat + Streaming)

A ChatGPT-like AI assistant. This is the Phase 1/2 core: authentication, persisted
conversations, and streaming AI responses over OpenAI/Gemini. Later phases (memory,
RAG, tool calling, LangGraph, multi-agent, MCP, multimodal, deployment) build on top
of this in separate passes.

## Stack

- **Frontend**: Next.js (App Router) + React + TypeScript + Tailwind
- **Backend**: FastAPI, layered (routes → services → repositories), SQLAlchemy 2.0 async
- **Database**: PostgreSQL (Docker), Redis (Docker)
- **LLM providers**: OpenAI and Google Gemini behind a shared provider abstraction

## Local setup

```bash
# 1. Environment
cp .env.example backend/.env
cp .env.example frontend/.env.local   # keep only NEXT_PUBLIC_API_BASE_URL
# edit backend/.env: set OPENAI_API_KEY, GEMINI_API_KEY, JWT_SECRET_KEY

# 2. Infra
docker compose up -d postgres redis

# 3. Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 4. Frontend (new terminal)
cd frontend
npm install
npm run dev   # http://localhost:3000
```

Open http://localhost:3000/register, create an account, and start chatting.

## What's in scope right now

Register/login (JWT access + refresh tokens), create/list/delete conversations,
send a message and get a streamed AI response (SSE), persisted history.

## What's explicitly deferred

Long-term memory, RAG, tool calling, LangGraph orchestration, multi-agent, MCP,
voice/vision/file upload, OAuth login, deployment/CI/CD/monitoring, admin dashboard,
sharing/export, message edit/regenerate, conversation search.
