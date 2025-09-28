# backend/Dockerfile
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app
RUN apt-get update && apt-get install -y \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# ================================================================
# Stage 2: Dependencies Builder
# ================================================================
FROM base AS deps-builder
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ================================================================
# Stage 3: Development
# ================================================================
FROM base AS development
COPY --from=deps-builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
COPY . .
RUN groupadd -r fastapi && useradd -r -g fastapi fastapi
RUN chown -R fastapi:fastapi /app
USER fastapi
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ================================================================
# Stage 4: Production
# ================================================================
FROM python:3.11-slim AS production
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app
RUN apt-get update && apt-get install -y \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=deps-builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
RUN pip install --no-cache-dir gunicorn uvicorn[standard]

RUN groupadd -r fastapi && useradd -r -g fastapi fastapi
COPY --chown=fastapi:fastapi . .

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

USER fastapi
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "main:app"]