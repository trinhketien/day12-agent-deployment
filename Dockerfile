# ============================================================
# Production Dockerfile — Day 12 Lab
# Fix: install packages to /usr/local (standard Python path)
# ============================================================

# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# Stage 2: Runtime
FROM python:3.11-slim AS runtime

RUN groupadd -r agent && useradd -r -g agent -d /app agent

WORKDIR /app

# Copy installed packages from builder (standard /usr/local path)
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy source code
COPY app/ ./app/
COPY utils/ ./utils/

RUN chown -R agent:agent /app

USER agent

ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" \
    || exit 1

# Single worker for Railway free tier (512MB RAM)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
