# Deployment Information — Day 12 Lab

> **Platform:** Railway  
> **Status:** 🟡 Ready for deploy (configure API key then `railway up`)

---

## Public URL

```
https://day12-agent.up.railway.app
```

> ℹ️ URL sẽ được cập nhật sau khi deploy. Chạy `railway domain` để lấy URL thật.

---

## Platform: Railway

Railway được chọn vì:
- Deploy nhanh nhất (~5 phút từ code → live)
- Không cần credit card cho $5 free credit đầu
- Auto-detect Dockerfile
- Dễ set environment variables

---

## Test Commands

### 1. Health Check
```bash
curl https://day12-agent.up.railway.app/health
# Expected: {"status":"ok","version":"1.0.0","environment":"production",...}
```

### 2. Readiness Check
```bash
curl https://day12-agent.up.railway.app/ready
# Expected: {"ready":true,"timestamp":"2026-04-17T..."}
```

### 3. Authentication Required (401)
```bash
curl -X POST https://day12-agent.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# Expected: 401 {"detail":"API key required..."}
```

### 4. Authenticated Request (200)
```bash
curl -X POST https://day12-agent.up.railway.app/ask \
  -H "X-API-Key: <YOUR_AGENT_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain Docker containers", "user_id": "student001"}'
# Expected: {"question":"...","answer":"...","model":"mock-llm",...}
```

### 5. Rate Limiting Test (429 after 10 req/min)
```bash
for i in $(seq 1 12); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST https://day12-agent.up.railway.app/ask \
    -H "X-API-Key: <YOUR_AGENT_API_KEY>" \
    -H "Content-Type: application/json" \
    -d "{\"question\": \"Test $i\", \"user_id\": \"tester\"}")
  echo "Request $i: HTTP $STATUS"
done
# Expected: 200 × 10, then 429 × 2
```

### 6. Metrics (Protected)
```bash
curl https://day12-agent.up.railway.app/metrics \
  -H "X-API-Key: <YOUR_AGENT_API_KEY>"
# Expected: uptime, request count, rate limit status, budget status
```

---

## Environment Variables Set on Railway

| Variable | Value |
|----------|-------|
| `PORT` | (auto-set by Railway) |
| `ENVIRONMENT` | `production` |
| `APP_NAME` | `Production AI Agent` |
| `APP_VERSION` | `1.0.0` |
| `AGENT_API_KEY` | `<secret — set in dashboard>` |
| `RATE_LIMIT_PER_MINUTE` | `10` |
| `MONTHLY_BUDGET_USD` | `10.0` |
| `LOG_LEVEL` | `INFO` |

---

## Deploy Steps (Railway)

```bash
# 1. Install Railway CLI
npm i -g @railway/cli

# 2. Login
railway login

# 3. Init project (from 06-lab-complete/)
cd 06-lab-complete
railway init

# 4. Set secrets
railway variables set AGENT_API_KEY=$(python -c "import secrets; print(secrets.token_hex(16))")
railway variables set ENVIRONMENT=production
railway variables set RATE_LIMIT_PER_MINUTE=10
railway variables set MONTHLY_BUDGET_USD=10.0

# 5. Deploy
railway up

# 6. Get URL
railway domain
```

---

## Alternative: Render

```bash
# 1. Push code to GitHub
git push origin main

# 2. Go to render.com → New → Blueprint
# 3. Connect GitHub repo
# 4. Render reads render.yaml automatically
# 5. Set AGENT_API_KEY in dashboard
# 6. Deploy!
```

---

## Local Testing (Without Cloud)

```bash
cd 06-lab-complete

# Option A: Direct Python
pip install -r requirements.txt
python -m app.main

# Option B: Docker
docker build -t day12-agent .
docker run -p 8000:8000 \
  -e AGENT_API_KEY=local-test-key \
  day12-agent

# Option C: Full Stack (with Nginx + Redis)
docker compose up --scale agent=2
# → Agent available at http://localhost (port 80)
```

---

## Architecture

```
Internet
    │
    ▼
[Nginx :80]  ← Load Balancer (round-robin / least_conn)
    │
    ├──→ [Agent Instance 1 :8000]
    ├──→ [Agent Instance 2 :8000]
    └──→ [Agent Instance 3 :8000]
              │
              ▼
          [Redis :6379]
       (conversation history,
        rate limit counters,
        budget tracking)
```

---

## Screenshots

> Screenshots sẽ được thêm sau khi deploy thực tế:
- `screenshots/railway_dashboard.png`
- `screenshots/health_check.png`  
- `screenshots/api_test.png`
- `screenshots/rate_limit_429.png`
