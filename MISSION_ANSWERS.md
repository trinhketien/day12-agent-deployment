# Day 12 Lab — Mission Answers

> **Course:** AICB-P1 · VinUniversity 2026  
> **Lab:** Day 12 — Hạ Tầng Cloud & Deployment  
> **Deadline:** 17/04/2026

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns phát hiện trong `01-localhost-vs-production/develop/app.py`

1. **Hardcoded API Key** — `api_key = "sk-abc123"` xuất hiện trực tiếp trong source code. Nếu repo public, ai cũng thấy và dùng được.

2. **Port cố định (Hardcoded Port)** — `app.run(port=8000)` không linh hoạt. Cloud platforms thường assign port động qua biến `PORT`.

3. **Debug mode bật cứng** — `app.run(debug=True)` trong production sẽ expose stack trace và cho phép arbitrary code execution.

4. **Không có Health Check endpoint** — Platform không biết app còn sống hay đã crash, không thể tự động restart.

5. **Không xử lý Graceful Shutdown** — Khi container nhận SIGTERM, app tắt đột ngột, các request đang xử lý bị mất.

6. **Logging bằng `print()`** — Không có timestamp, log level, hay struct format. Không thể dùng log aggregation tools.

7. **Không validate input** — Không giới hạn độ dài câu hỏi, dễ bị abuse hoặc gây lỗi downstream.

### Exercise 1.2: Chạy basic version

```bash
cd 01-localhost-vs-production/develop
pip install -r requirements.txt
python app.py

# Test
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

**Quan sát:** App chạy được nhưng không production-ready vì thiếu security, health check, và logging.

### Exercise 1.3: So sánh basic vs advanced

| Feature | Basic (develop) | Advanced (production) | Tại sao quan trọng? |
|---------|-----------------|----------------------|---------------------|
| Config | Hardcode trong code | Environment variables (`.env`) | Bảo mật, linh hoạt khi deploy |
| Health check | ❌ Không có | ✅ `GET /health` trả 200 | Platform biết khi nào restart |
| Logging | `print()` | JSON structured logging | Searchable, parseable bởi log tools |
| Shutdown | Đột ngột (mất request) | Graceful (drain + 30s timeout) | Không mất in-flight requests |
| Port | `8000` hardcode | `int(os.getenv("PORT", 8000))` | Cloud platforms assign port động |
| API Key | `"sk-abc123"` trong code | `os.getenv("OPENAI_API_KEY")` | Không lộ secrets trên Git |
| Input validation | ❌ None | ✅ Pydantic (min/max_length) | Tránh abuse, lỗi runtime |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile cơ bản

1. **Base image là gì?** `python:3.11-slim` — Python 3.11 trên Debian slim (nhỏ hơn full image ~800MB → ~180MB)

2. **Working directory là gì?** `/app` — tất cả file được copy và chạy trong thư mục này

3. **Tại sao COPY requirements.txt trước?** Docker build cache: nếu requirements.txt không thay đổi, layer `pip install` được cache lại. Tránh re-install mỗi lần đổi code.

4. **CMD vs ENTRYPOINT?**
   - `ENTRYPOINT`: command cố định, không override được (thường là binary như `["uvicorn"]`)
   - `CMD`: arguments mặc định, user có thể override khi `docker run`
   - Kết hợp: `ENTRYPOINT ["uvicorn"]` + `CMD ["app.main:app"]` cho phép override arguments

### Exercise 2.2: Build và run

```bash
# Build
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .

# Run
docker run -p 8000:8000 my-agent:develop

# Kiểm tra size (thường ~400-600MB với develop image)
docker images my-agent:develop
```

### Exercise 2.3: Multi-stage build

**Stage 1 (builder):** Install dependencies với gcc, libpq-dev. Kết quả: `/root/.local` chứa packages đã compile.

**Stage 2 (runtime):** Copy chỉ packages đã build từ stage 1. Không có compiler, build tools → image nhỏ hơn.

```bash
docker build -t my-agent:advanced 02-docker/production/
docker images | grep my-agent
```

**Kết quả:** Production image thường nhỏ hơn 40-60% so với develop image.

| Image | Size (ước tính) |
|-------|----------------|
| `my-agent:develop` | ~450 MB |
| `my-agent:advanced` | ~180 MB |
| Giảm | ~60% |

### Exercise 2.4: Docker Compose stack

Services được start:
1. **agent** — FastAPI app (có thể scale)
2. **redis** — In-memory store cho rate limit + conversation history
3. **nginx** — Load balancer, single entry point port 80

Communication: tất cả trong Docker network `agent-net`, communicate qua service name (`redis:6379`, `agent:8000`).

---

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment

```bash
npm i -g @railway/cli
railway login
railway init
railway variables set AGENT_API_KEY=my-secret-key-$(date +%s)
railway variables set RATE_LIMIT_PER_MINUTE=10
railway variables set MONTHLY_BUDGET_USD=10.0
railway up
railway domain
```

**URL:** Xem `DEPLOYMENT.md` để biết public URL

### Exercise 3.2: So sánh Railway vs Render config

| Aspect | `railway.toml` | `render.yaml` |
|--------|---------------|---------------|
| Format | TOML | YAML |
| Build | Auto-detect / Dockerfile | `buildCommand` |
| Start | `startCommand` | `startCommand` |
| Env vars | Dashboard / CLI | `envVars` block |
| Free tier | $5 credit | 750h/month |
| Deploy trigger | `railway up` hoặc Git push | Git push |

---

## Part 4: API Security

### Exercise 4.1: API Key Authentication

**API key được check ở đâu?** FastAPI dependency `verify_api_key` được inject vào endpoint qua `Depends()`. Nó đọc header `X-API-Key` và so sánh với `settings.agent_api_key`.

**Điều gì xảy ra nếu sai key?** Trả HTTP 401 `{"detail": "Invalid API key."}` với header `WWW-Authenticate: ApiKey`.

**Làm sao rotate key?** Update biến môi trường `AGENT_API_KEY` → restart container. Với zero-downtime: implement key versioning hoặc dùng key in header `X-API-Key-Version`.

### Test Results:

```bash
# ❌ Không có key → 401
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# {"detail":"API key required. Add header: X-API-Key: <your-key>"}

# ✅ Có key → 200
curl -X POST http://localhost:8000/ask \
  -H "X-API-Key: local-dev-key-12345" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# {"question":"Hello","answer":"...","model":"mock-llm",...}
```

### Exercise 4.2: JWT Authentication

JWT flow:
1. Client POST `/token` với username/password → nhận `access_token`
2. Client gửi `Authorization: Bearer <token>` với mỗi request
3. Server verify chữ ký với `JWT_SECRET`, check expiry

Ưu điểm so với API key: stateless, có expiry tự động, có thể mang claims (user_id, roles).

### Exercise 4.3: Rate Limiting

**Algorithm:** Sliding Window — chính xác hơn Fixed Window, không có burst tại boundary.

**Limit:** 10 requests/minute (cấu hình qua `RATE_LIMIT_PER_MINUTE`).

**Bypass cho admin:** Thêm `if api_key == settings.admin_key: return` trước check, hoặc dùng whitelist user_id.

```bash
# Test rate limit (11 requests → request thứ 11 nhận 429)
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST http://localhost:8000/ask \
    -H "X-API-Key: local-dev-key-12345" \
    -H "Content-Type: application/json" \
    -d "{\"question\": \"Test $i\"}"
done
# Output: 200 200 200 200 200 200 200 200 200 200 429 429 429 429 429
```

### Exercise 4.4: Cost Guard Implementation

```python
def check_budget(user_id: str = Depends(check_rate_limit)) -> str:
    budget = _get_budget(user_id)
    with budget.lock:
        budget.reset_if_new_month()  # auto-reset đầu tháng
        estimated_cost = estimate_cost("x" * 500)  # worst case
        if budget.spent_usd + estimated_cost > settings.monthly_budget_usd:
            raise HTTPException(402, "Monthly budget exceeded")
    return user_id
```

Sau mỗi call thành công: `record_cost(user_id, question, answer)` → cộng vào `budget.spent_usd`.

---

## Part 5: Scaling & Reliability

### Exercise 5.1: Health Checks

```python
@app.get("/health")
def health():
    """Liveness probe — luôn trả 200 nếu process OK."""
    return {"status": "ok", "uptime_seconds": round(time.time() - START_TIME, 1)}

@app.get("/ready")  
def ready():
    """Readiness probe — 503 khi đang init hoặc shutdown."""
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    return {"ready": True}
```

### Exercise 5.2: Graceful Shutdown

```python
def _sigterm_handler(signum, frame):
    logger.info({"event": "sigterm_received", "msg": "Draining requests..."})
    # uvicorn handles drain với timeout_graceful_shutdown=30

signal.signal(signal.SIGTERM, _sigterm_handler)

# uvicorn được start với:
uvicorn.run(..., timeout_graceful_shutdown=30)
```

**Test:** Container nhận SIGTERM → request đang chạy vẫn hoàn thành → sau 30s process exit.

### Exercise 5.3: Stateless Design

```python
# ❌ Stateful — không scale được
conversation_history = {}  # mỗi instance có memory riêng

# ✅ Stateless — Redis shared across all instances
import redis
r = redis.from_url(settings.redis_url)

@app.post("/ask")
def ask(user_id: str, question: str):
    history = r.lrange(f"history:{user_id}", 0, -1)
    # ...
    r.rpush(f"history:{user_id}", json.dumps({"q": question, "a": answer}))
```

**Tại sao quan trọng?** Khi `--scale agent=3`, 3 instances có _memory riêng biệt_. Request lần 1 → Agent 1, request lần 2 → Agent 2 → Agent 2 không biết conversation từ Agent 1.

### Exercise 5.4: Load Balancing

```bash
docker compose up --scale agent=3

# Nginx phân tán với algorithm least_conn
# Kiểm tra logs
docker compose logs agent | grep "event.*http"
```

### Exercise 5.5: Test Stateless

```bash
python test_stateless.py
# 1. Bắt đầu conversation với Agent 1
# 2. Kill Agent 1
# 3. Tiếp tục conversation với Agent 2/3
# 4. Conversation vẫn còn (vì lưu trong Redis)
```

---

## Tổng Kết Kiến Thức

| Concept | Before Lab | After Lab |
|---------|------------|-----------|
| Config | Hardcode trong code | 12-Factor: env vars |
| Packaging | "Cài trên máy tôi" | Docker container |
| Deployment | Manual SSH | `railway up` / `git push` |
| Security | Không có | Auth + Rate Limit + Cost Guard |
| Scalability | 1 instance | Stateless + Redis + Nginx LB |
| Reliability | Hope it works | Health checks + Graceful shutdown |
| Observability | print() | JSON structured logging |
