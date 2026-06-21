# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Backend image: FastAPI served by uvicorn.
# Build context is the repository root (see docker-compose.yml).
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS base

# - PYTHONDONTWRITEBYTECODE: no .pyc files in the image
# - PYTHONUNBUFFERED: stream logs straight to the container output
# - PIP_NO_CACHE_DIR: keep the image small
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System packages required by some Python wheels (psycopg, bcrypt build deps).
# psycopg2-binary / psycopg-binary ship wheels, so libpq is only needed at
# runtime; install the lightweight client library and clean up afterwards.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first so the layer is cached across code changes.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Application code and the magic-item catalogue.
# magicvariants.json must live at the project root because
# app/api/inventory.py resolves it via Path(__file__).resolve().parents[2].
COPY app ./app
COPY magicvariants.json ./

# Run as an unprivileged user.
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Basic container health: the root endpoint returns a small JSON payload.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS http://localhost:8000/ || exit 1

# Production launch. WEB_CONCURRENCY controls the number of uvicorn workers
# (defaults to 2); reload is intentionally disabled.
ENV WEB_CONCURRENCY=2
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY}"]
