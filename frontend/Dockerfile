# syntax=docker/dockerfile:1

# --- deps: install once, cached independently of source changes ---
FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# --- builder ---
FROM node:22-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Build-time-only value baked into the client bundle (NEXT_PUBLIC_* vars are inlined at build,
# not read at runtime) - override via --build-arg for a non-default API location.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
RUN npm run build

# --- runtime ---
FROM node:22-slim AS runtime
WORKDIR /app
RUN useradd --create-home --shell /bin/bash appuser
ENV NODE_ENV=production
ENV PORT=3000

# next.config.ts's output: "standalone" traces the minimal file set needed to run (a fraction of
# a full node_modules) - static assets aren't included in that trace, so public/ and .next/static
# are copied separately.
COPY --from=builder /app/public ./public
COPY --from=builder --chown=appuser:appuser /app/.next/standalone ./
COPY --from=builder --chown=appuser:appuser /app/.next/static ./.next/static

USER appuser
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD node -e "fetch('http://localhost:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
