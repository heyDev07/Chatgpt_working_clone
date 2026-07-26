# AI Assistant

A production-grade ChatGPT clone: streaming chat over multiple LLM providers, RAG over
uploaded documents, a tool-calling framework (calculator, web search, text-to-SQL, browser
automation, image generation, MCP servers), multi-agent personas, memory, multimodal
input/output (vision, voice, image generation), an admin dashboard, and a full deployment/
observability stack (Docker, Terraform/AWS, Prometheus/Grafana, CI/CD).

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the pieces fit together,
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for local setup and the day-to-day dev workflow, and
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for running this in production.

## Stack

- **Frontend**: Next.js 16 (App Router) + React + TypeScript + Tailwind
- **Backend**: FastAPI, layered (routes → services → repositories), SQLAlchemy 2.0 async
- **Database**: PostgreSQL, Redis (sessions/rate limiting/cache)
- **Vector store**: Qdrant (RAG document embeddings)
- **Object storage**: MinIO (S3-compatible; swapped for real S3 in the AWS Terraform config)
- **LLM providers**: OpenAI-compatible (OpenRouter) and Google Gemini, behind a shared
  provider abstraction
- **Tool calling / MCP**: native tools (calculator, SQL, image generation) plus MCP-based
  tools (Tavily web search, Playwright browser automation)
- **Observability**: Prometheus + Grafana, structured JSON logging
- **Deployment**: Docker Compose (dev + prod overlay), Nginx, GitHub Actions CI/CD, Terraform
  for AWS (ECS Fargate, RDS, ElastiCache, S3, ALB)

## Quick start

```bash
# 1. Environment
cp .env.example backend/.env
cp .env.example frontend/.env.local   # keep only NEXT_PUBLIC_API_BASE_URL
# edit backend/.env: set OPENAI_API_KEY, GEMINI_API_KEY, JWT_SECRET_KEY at minimum

# 2. Infra (Postgres, Redis, Qdrant, MinIO)
docker compose up -d

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

Full setup detail (running tests, optional MCP servers, monitoring stack, load tests) is in
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Feature areas

- **Chat**: streaming responses (SSE), conversation CRUD, rename/pin/archive/search, edit/
  regenerate/retry/stop, markdown + syntax highlighting, model switcher.
- **Memory**: background summarization and preference/goal extraction, relevance-ranked
  retrieval injected into the prompt.
- **RAG**: PDF/DOCX/TXT/CSV/XLSX upload and parsing, chunking + embeddings, Qdrant retrieval
  with per-user filtering and citations.
- **Tools & agents**: a registry/router shared by native and MCP tools (permission-scoped per
  agent persona, audited); personas in `backend/app/agents/definitions.py` (general, coding,
  research, analyst, reviewer, browser); text-to-SQL against an isolated read-only schema;
  Playwright-driven browser automation with an SSRF guard.
- **Multimodal**: vision (image understanding via provider APIs), image generation
  (Pollinations.ai), voice input (Web Speech API with a local Whisper-WASM fallback for
  browsers where it's broken, e.g. Brave).
- **Organization**: folders, tags, shared read-only links.
- **Admin**: user management, usage analytics, tool-call audit log.
- **Security**: JWT auth with refresh rotation, per-endpoint rate limiting, tool-call
  allowlisting enforced at call time (not just offered to the model), SSRF/path-traversal
  guards, DB-level least-privilege for the SQL tool.

## Deferred

LangGraph-based orchestration (`Phase 7` — deliberately revisited as a dedicated design
discussion rather than folded in incrementally), OAuth login, and the GitHub/Gmail/Calendar/
YouTube MCP servers (blocked on external OAuth credentials).
