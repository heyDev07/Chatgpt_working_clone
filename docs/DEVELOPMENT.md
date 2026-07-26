# Development guide

## Prerequisites

- Python 3.12, Node 22
- Docker (for Postgres/Redis/Qdrant/MinIO — everything in the base `docker-compose.yml`)

## Local setup

```bash
cp .env.example backend/.env
cp .env.example frontend/.env.local   # keep only NEXT_PUBLIC_API_BASE_URL
```

Edit `backend/.env`: at minimum set `OPENAI_API_KEY` (or point `OPENAI_BASE_URL` at an
OpenAI-compatible endpoint like OpenRouter), `GEMINI_API_KEY`, and `JWT_SECRET_KEY`. Every other
setting in `backend/app/config/settings.py` has a working local default. Optional keys
(`TAVILY_API_KEY` for MCP web search) degrade gracefully when unset — see
[ARCHITECTURE.md](ARCHITECTURE.md) — rather than failing at startup.

```bash
docker compose up -d          # postgres, redis, qdrant, minio

cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# new terminal
cd frontend
npm install
npm run dev                   # http://localhost:3000
```

Register at http://localhost:3000/register.

## Project layout

```
backend/app/
  api/v1/        # routes — thin, auth + request/response shape only
  services/       # business logic, orchestrates providers/tools/repositories
  repositories/    # the only layer that touches SQLAlchemy models
  providers/       # OpenAI-compatible + Gemini, behind a shared interface
  tools/            # native tools + MCP adapter, shared registry/router
  agents/           # persona definitions (system prompt + allowed_tools per persona)
  models/           # SQLAlchemy models
  schemas/          # Pydantic request/response schemas
  middleware/, core/, config/, db/, storage/, vectorstore/, mcp/

frontend/
  app/              # Next.js App Router pages
  components/       # chat, sidebar, admin, documents, memory, settings, auth
  lib/               # API client, speech/transcription helpers, etc.
```

## Testing

### Backend

```bash
cd backend
source .venv/bin/activate
pytest -v
```

`tests/test_security_helpers.py` is pure unit tests (no infra needed). `tests/test_auth.py` and
`tests/test_conversations.py` are real integration tests — they start an actual `uvicorn` server
in a background thread and hit it over real HTTP against real Postgres/Redis, not mocks and not
httpx's in-process `ASGITransport` (that transport hits a documented Starlette/anyio
incompatibility with `BaseHTTPMiddleware`, which this app's request-logging middleware extends).
They need Postgres reachable at the URL in `tests/conftest.py`'s `DATABASE_URL` default
(`localhost:5433`, matching the base `docker-compose.yml`'s port mapping) and Redis DB index 1 —
`docker compose up -d` provides the Postgres server itself, and `conftest.py` creates the
`ai_assistant_test` database on it automatically if missing (the dev compose file only
provisions the `ai_assistant` database, not a dedicated test one, so this has to be
self-provisioning rather than assumed). CI runs the same suite against GitHub Actions service
containers instead (see `.github/workflows/ci.yml`), which provision `ai_assistant_test`
directly.

### Frontend

```bash
cd frontend
npx tsc --noEmit
npm run lint
npm run build
```

No component/E2E test suite yet — deliberately deferred (see the project roadmap) rather than
half-built. If you're adding one, Vitest + React Testing Library for components and Playwright
for E2E flows are the natural fits given the existing stack (Playwright is already a project
dependency for the browser-automation tool).

## Monitoring stack (optional)

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

Prometheus at http://localhost:9090, Grafana at http://localhost:3001 (default login
`admin`/`admin` — change before any real deployment). Grafana is pre-provisioned with a
datasource and an "App Overview" dashboard (`monitoring/grafana/dashboards/app-overview.json`).
Prometheus scrapes `host.docker.internal:8000` by default, matching the primary dev workflow of
running the backend directly via `uvicorn` on the host; see `monitoring/prometheus.yml` for the
containerized-backend alternative.

## Load testing

```bash
cd load_tests
python3 -m venv .venv && source .venv/bin/activate   # a SEPARATE venv from backend/.venv —
pip install -r requirements.txt                       # installing Locust into the backend venv
                                                        # previously upgraded greenlet and broke
                                                        # SQLAlchemy async; keep these isolated
python3 seed_users.py         # pre-creates test accounts, bypassing the register rate limiter
locust -f locustfile.py --host http://localhost:8000
```

`locustfile.py` deliberately never sends real chat messages — that would measure the upstream
LLM provider's rate limiter, not this app. It exercises auth, conversation CRUD, and tool
listing instead. See the Phase 18 commit message for the DB-connection-pool findings from the
last real run (`db_pool_size`/`db_max_overflow` in `backend/app/config/settings.py`).
