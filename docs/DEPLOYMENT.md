# Deployment guide

Two deployment paths exist, matching different scales: a single-host Docker Compose setup, and
AWS via Terraform (ECS Fargate). Both share the same Dockerfiles.

## Docker images

`backend/Dockerfile` and `frontend/Dockerfile` are multi-stage, non-root builds.

- **Backend**: Node.js + Chromium are installed as root (needed for the Playwright MCP browser
  tool) before switching to `appuser`; `PLAYWRIGHT_BROWSERS_PATH=/ms-playwright` is a fixed
  shared path (not root's default `~/.cache`, which `appuser` can't read) chowned to `appuser`.
- **Frontend**: builds with `output: "standalone"` (`next.config.ts`) for a minimal runtime
  image; `NEXT_PUBLIC_API_BASE_URL` is a build `ARG`, not a runtime env var, since Next.js inlines
  `NEXT_PUBLIC_*` values into the client bundle at build time.

```bash
docker build -t ai-assistant-backend ./backend
docker build -t ai-assistant-frontend ./frontend \
  --build-arg NEXT_PUBLIC_API_BASE_URL=https://your-domain.com/api/v1
```

## Single-host: Docker Compose + Nginx

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

`docker-compose.prod.yml` is a layered overlay (not a standalone file) — the base
`docker-compose.yml` still works unmodified for local dev, where backend/frontend run on the host
via `uvicorn`/`npm run dev` rather than in containers. The prod overlay adds the backend and
frontend as built services, wired to the infra services by Compose's service-name DNS
(`postgres`, `redis`, `qdrant`, `minio`) instead of the host-mapped ports `backend/.env` uses for
local dev.

`nginx/nginx.conf` reverse-proxies `/api/` to the backend and everything else to the frontend.
`client_max_body_size 25M` matches the largest upload the app accepts (`DocumentService`'s 20MB
limit plus headroom). `proxy_buffering off` on `/api/` is required for SSE chat streaming — the
backend already sends `X-Accel-Buffering: no` on that response, and this is Nginx's own
belt-and-suspenders covering the whole location. The HTTPS server block is present but commented
out: enable it once you have a real domain and certificate (e.g. via certbot) — not something
fakeable without one.

## AWS via Terraform

`terraform/aws/` provisions: VPC + subnets + a single NAT gateway (a deliberate cost tradeoff —
one NAT, not per-AZ), RDS Postgres, ElastiCache Redis, S3 (replacing MinIO), ECS Fargate
(backend/frontend/Qdrant as separate services), EFS for Qdrant's stateful storage (Fargate has no
attachable EBS), AWS Cloud Map for internal service discovery (`qdrant.ai-assistant.local`), an
ALB with path-based routing, Secrets Manager for every sensitive env var, and IAM roles split
into an execution role (ECR/CloudWatch/Secrets access) and a task role (S3 access).

```bash
cd terraform/aws
cp terraform.tfvars.example terraform.tfvars   # fill in real values
terraform init
terraform plan
terraform apply
```

This config has been validated (`terraform fmt`, `terraform init -backend=false`,
`terraform validate`, and `terraform plan` failing only at the AWS-authentication step) but never
actually applied — doing so provisions real, billed AWS resources. Review `terraform.tfvars`
against your own AWS account before running `apply`.

Two things worth knowing before touching this config:

- `app/storage/s3_client.py`'s `get_s3_client()` only passes `endpoint_url` to boto3 when
  `S3_ENDPOINT_URL` is set. Leave it unset in the ECS task's env and boto3 resolves real AWS S3
  normally; MinIO's local dev URL is what it defaults to otherwise.
- `db_pool_size`/`db_max_overflow` (`backend/app/config/settings.py`) were tuned from a local
  load test (see [DEVELOPMENT.md](DEVELOPMENT.md#load-testing)) that hit its own confound (load
  generator and backend sharing one machine's CPU) — treat the current values as a reasonable
  starting point, not a number proven correct under real multi-host load.

## CI/CD

`.github/workflows/ci.yml` runs on every push/PR to `main`:

- **backend**: spins up Postgres + Redis as GitHub Actions service containers, installs
  dependencies, imports `app.main` (catches broken imports a clean install wouldn't), then runs
  the full `pytest` suite — unit tests and the real HTTP integration tests together, against
  those service containers.
- **frontend**: `tsc --noEmit`, `eslint`, `next build`.
- **docker-build**: builds both images; on a push to `main` (never on a PR — an unreviewed image
  should never reach the registry), logs into GHCR and pushes `:latest` and `:<sha>` tags. Image
  references must be all-lowercase, so the repository owner/name is lowercased into an
  `IMAGE_REPO` env var before tagging — this repo's actual name has mixed case, which broke the
  push step on the first two real runs until fixed.

Actually deploying a pushed image (rolling an ECS service, etc.) is a deliberately separate,
unautomated step — not something that should happen on every push to `main` without a human
deciding to.

## Observability

`docker-compose.monitoring.yml` is a third, optional overlay: Prometheus + Grafana, pre-wired to
the backend's `/metrics` endpoint and a provisioned dashboard. See
[DEVELOPMENT.md](DEVELOPMENT.md#monitoring-stack-optional) for local usage; the same containers
work unmodified pointed at a deployed backend by changing `monitoring/prometheus.yml`'s scrape
target.
