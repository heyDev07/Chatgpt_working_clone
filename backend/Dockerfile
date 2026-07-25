# syntax=docker/dockerfile:1

# --- deps: build the Python venv in its own layer, cached independently of app code changes ---
FROM python:3.12-slim AS deps
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# --- runtime ---
FROM python:3.12-slim AS runtime
WORKDIR /app

# Node.js + Chromium are here for one reason: app/tools/browser.py spawns
# `npx @playwright/mcp@latest` as a subprocess for the browser-automation tool (Phase 9f). This is
# the single biggest contributor to this image's size (~1.5GB+) - a plain FastAPI backend
# wouldn't need any of this. `--with-deps` pulls in Chromium's OS-level dependencies (fonts,
# libnss, libatk, etc.) via apt automatically rather than guessing the package list by hand.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

COPY --from=deps /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY . .
RUN chown -R appuser:appuser /app

# --with-deps needs apt/root, so this runs before USER appuser below - installed into a fixed,
# shared path (not the default ~/.cache/ms-playwright, which would resolve to *root's* home
# here) so the appuser the app actually runs as can use the same browser without root access or
# re-downloading it.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN npx --yes playwright install --with-deps chromium \
    && chown -R appuser:appuser /ms-playwright

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
