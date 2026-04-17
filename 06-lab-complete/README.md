# Production AI Agent — Day 12 VinUniversity Lab

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://docker.com)

Production-ready AI agent triển khai đầy đủ các concepts từ **Day 12: Hạ Tầng Cloud & Deployment**.

---

## 🏗️ Architecture

```
                    Internet
                        │
                   [Nginx :80]           ← Load Balancer
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
  [Agent1 :8000]  [Agent2 :8000]  [Agent3 :8000]
         └──────────────┴──────────────┘
                        │
                  [Redis :6379]          ← Shared State
```

---

## ✅ Features Implemented

| Feature | File | Status |
|---------|------|--------|
| 12-Factor Config | `app/config.py` | ✅ |
| API Key Auth | `app/auth.py` | ✅ |
| Rate Limiting (10/min) | `app/rate_limiter.py` | ✅ |
| Cost Guard ($10/month) | `app/cost_guard.py` | ✅ |
| Health + Readiness | `app/main.py` | ✅ |
| Graceful Shutdown | `app/main.py` | ✅ |
| JSON Logging | `app/main.py` | ✅ |
| Multi-stage Docker | `Dockerfile` | ✅ |
| Nginx Load Balancer | `nginx/nginx.conf` | ✅ |
| Full Stack Compose | `docker-compose.yml` | ✅ |

---

## 🚀 Quick Start

### Option A: Python trực tiếp

```bash
pip install -r requirements.txt
python -m app.main

# Test
curl http://localhost:8000/health
curl -X POST http://localhost:8000/ask \
  -H "X-API-Key: local-dev-key-12345" \
  -H "Content-Type: application/json" \
  -d '{"question": "Docker là gì?"}'
```

### Option B: Docker single instance

```bash
docker build -t day12-agent .
docker run -p 8000:8000 -e AGENT_API_KEY=my-secret-key day12-agent
```

### Option C: Full Stack (Nginx + Redis + 3 instances)

```bash
cp .env.example .env.local   # edit AGENT_API_KEY
docker compose up --scale agent=3
curl http://localhost/health   # via Nginx port 80
```

---

## 🔌 API

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/health` | No | Liveness probe |
| GET | `/ready` | No | Readiness probe |
| POST | `/ask` | X-API-Key | Ask the agent |
| GET | `/metrics` | X-API-Key | Usage stats |

---

## ☁️ Deploy to Railway

```bash
npm i -g @railway/cli && railway login
railway init
railway variables set AGENT_API_KEY=<your-secret>
railway variables set ENVIRONMENT=production
railway up && railway domain
```

---

## ✔️ Validation

```bash
python check_production_ready.py
# Expected: 21/21 checks passed (100%)
```
