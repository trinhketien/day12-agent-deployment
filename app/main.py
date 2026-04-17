"""
Production AI Agent — Day 12 Complete Lab
==========================================
Kết hợp TẤT CẢ concepts đã học:

  ✅ 12-Factor Config (environment variables)
  ✅ Structured JSON Logging
  ✅ API Key Authentication (app/auth.py)
  ✅ Sliding-Window Rate Limiting (app/rate_limiter.py)
  ✅ Monthly Cost Guard (app/cost_guard.py)
  ✅ Input Validation (Pydantic)
  ✅ Health Check + Readiness Probe
  ✅ Graceful Shutdown (SIGTERM)
  ✅ Security Headers (CORS, X-Frame-Options, etc.)
  ✅ Request Logging Middleware
  ✅ Conversation History (in-memory, stateless-ready)
"""
import os
import sys
import time
import signal
import logging
import json
import hashlib
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from app.config import settings
from app.auth import verify_api_key
from app.rate_limiter import check_rate_limit, get_rate_limit_status
from app.cost_guard import check_budget, record_cost, get_budget_status

# Mock LLM — replace with OpenAI when OPENAI_API_KEY is set
from utils.mock_llm import ask as llm_ask

# ─────────────────────────────────────────────────────────────
# Logging — JSON Structured (12-Factor III)
# ─────────────────────────────────────────────────────────────
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    level = logging.DEBUG if settings.debug else logging.INFO
    logging.basicConfig(level=level, handlers=[handler], force=True)


setup_logging()
logger = logging.getLogger("agent")

# ─────────────────────────────────────────────────────────────
# Global State
# ─────────────────────────────────────────────────────────────
START_TIME = time.time()
_is_ready = False
_request_count = 0
_error_count = 0

# In-memory conversation store (stateless-ready: swap for Redis)
_conversations: dict[str, list[dict]] = {}

# ─────────────────────────────────────────────────────────────
# Lifespan (startup / shutdown)
# ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({
        "event": "startup",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "llm": "openai" if settings.openai_api_key else "mock",
    }))
    # Simulate initialization (e.g. warm up LLM client, connect DB)
    time.sleep(0.1)
    _is_ready = True
    logger.info(json.dumps({"event": "ready", "port": settings.port}))

    yield  # ← Application runs here

    _is_ready = False
    logger.info(json.dumps({
        "event": "shutdown",
        "total_requests": _request_count,
        "total_errors": _error_count,
        "uptime_seconds": round(time.time() - START_TIME, 1),
    }))


# ─────────────────────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Production-ready AI Agent — Day 12 VinUniversity Lab",
    lifespan=lifespan,
    # Disable /docs in production
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
)

# ── CORS ─────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    max_age=600,
)


# ── Request / Response Middleware ─────────────────────────────
@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    req_id = hashlib.md5(
        f"{time.time()}{request.url.path}".encode()
    ).hexdigest()[:8]

    try:
        response: Response = await call_next(request)
    except Exception as exc:
        _error_count += 1
        logger.error(json.dumps({
            "event": "unhandled_error",
            "req_id": req_id,
            "error": str(exc),
        }))
        raise

    duration_ms = round((time.time() - start) * 1000, 1)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Request-Id"] = req_id
    # Remove server header (MutableHeaders has no .pop() in newer starlette)
    try:
        del response.headers["server"]
    except KeyError:
        pass

    logger.info(json.dumps({
        "event": "http",
        "req_id": req_id,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "ms": duration_ms,
    }))
    return response


# ─────────────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Câu hỏi gửi đến AI agent",
        examples=["Docker là gì?"],
    )
    user_id: str = Field(
        default="anonymous",
        max_length=64,
        description="User identifier for conversation history",
    )
    include_history: bool = Field(
        default=True,
        description="Include previous conversation context",
    )


class AskResponse(BaseModel):
    question: str
    answer: str
    user_id: str
    model: str
    conversation_turn: int
    timestamp: str


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    uptime_seconds: float
    total_requests: int
    llm_backend: str
    timestamp: str


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────

@app.get("/", tags=["Info"], summary="Agent info")
def root():
    """Thông tin về agent và các endpoints."""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "endpoints": {
            "POST /ask": "Ask the agent a question (requires X-API-Key)",
            "GET /health": "Liveness check",
            "GET /ready": "Readiness check",
            "GET /metrics": "Usage metrics (requires X-API-Key)",
        },
    }


@app.post(
    "/ask",
    response_model=AskResponse,
    tags=["Agent"],
    summary="Ask the AI agent",
)
async def ask_agent(
    body: AskRequest,
    request: Request,
    # ↓ Dependency chain: auth → rate_limit → budget_check
    user_id: str = Depends(check_budget),
):
    """
    Gửi câu hỏi đến AI agent.

    **Authentication:** Header `X-API-Key: <your-key>`  
    **Rate limit:** {settings.rate_limit_per_minute} requests/minute  
    **Budget:** ${settings.monthly_budget_usd}/month per user  
    """
    # Get conversation history (stateless-ready pattern)
    history = _conversations.get(body.user_id, [])
    turn = len(history) + 1

    logger.info(json.dumps({
        "event": "agent_call",
        "user_id": user_id,
        "req_user": body.user_id,
        "q_len": len(body.question),
        "history_turns": len(history),
        "client_ip": str(request.client.host) if request.client else "unknown",
    }))

    # Build context-aware prompt
    if body.include_history and history:
        context = "\n".join(
            f"Q: {h['question']}\nA: {h['answer']}" for h in history[-3:]
        )
        full_question = f"Context:\n{context}\n\nNew question: {body.question}"
    else:
        full_question = body.question

    # Call LLM (mock or real)
    answer = llm_ask(full_question)

    # Record cost AFTER successful call
    record_cost(user_id, body.question, answer)

    # Save to conversation history
    _conversations.setdefault(body.user_id, []).append({
        "question": body.question,
        "answer": answer,
        "turn": turn,
        "ts": datetime.now(timezone.utc).isoformat(),
    })

    return AskResponse(
        question=body.question,
        answer=answer,
        user_id=body.user_id,
        model=settings.llm_model if settings.openai_api_key else "mock-llm",
        conversation_turn=turn,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Operations"],
    summary="Liveness probe",
)
def health():
    """
    Liveness probe — platform restarts container if this returns non-2xx.
    Docker HEALTHCHECK calls this endpoint every 30s.
    """
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        environment=settings.environment,
        uptime_seconds=round(time.time() - START_TIME, 1),
        total_requests=_request_count,
        llm_backend="openai" if settings.openai_api_key else "mock",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get(
    "/ready",
    tags=["Operations"],
    summary="Readiness probe",
)
def ready():
    """
    Readiness probe — load balancer stops routing traffic here if not ready.
    Returns 503 during startup or graceful shutdown.
    """
    if not _is_ready:
        raise HTTPException(
            status_code=503,
            detail="Service not ready. Initialization in progress.",
        )
    return {"ready": True, "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get(
    "/metrics",
    tags=["Operations"],
    summary="Usage metrics",
)
def metrics(user_id: str = Depends(verify_api_key)):
    """Protected metrics endpoint — shows rate limit and budget status."""
    uptime = round(time.time() - START_TIME, 1)
    rate_status = get_rate_limit_status(user_id)
    budget_status = get_budget_status(user_id)

    return {
        "uptime_seconds": uptime,
        "total_requests": _request_count,
        "error_count": _error_count,
        "requests_per_second": round(_request_count / max(1, uptime), 3),
        "rate_limit": rate_status,
        "budget": budget_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─────────────────────────────────────────────────────────────
# Graceful Shutdown — handle SIGTERM from container orchestrator
# ─────────────────────────────────────────────────────────────
def _sigterm_handler(signum, frame):
    """
    Handle SIGTERM: uvicorn will drain in-flight requests then exit.
    We just log the signal and let uvicorn's timeout_graceful_shutdown do the rest.
    """
    logger.info(json.dumps({
        "event": "sigterm_received",
        "signum": signum,
        "in_flight_requests": _request_count,
        "msg": "Graceful shutdown initiated. Draining requests...",
    }))


try:
    signal.signal(signal.SIGTERM, _sigterm_handler)
except (ValueError, OSError):
    # signal.signal chỉ chạy được ở main thread
    # Trong multi-worker mode, child processes bỏ qua bước này
    pass


# ─────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info(json.dumps({
        "event": "starting",
        "app": settings.app_name,
        "host": settings.host,
        "port": settings.port,
        "env": settings.environment,
        "api_key_preview": settings.agent_api_key[:4] + "****",
    }))
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=1 if settings.debug else 2,
        timeout_graceful_shutdown=30,  # wait 30s for in-flight requests
        access_log=False,              # we handle logging ourselves
    )
