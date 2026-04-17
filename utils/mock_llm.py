"""
LLM Backend — Day 12 Lab
Supports:
  1. Google Gemini (free tier) — if GEMINI_API_KEY is set
  2. Mock responses — fallback when no API key

Zero extra dependencies — uses urllib for Gemini REST API.
"""
import os
import time
import json
import random
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# ─── Mock Responses (fallback) ───────────────────────────────
MOCK_RESPONSES = {
    "default": [
        "This is a response from the AI agent (mock mode). In production with GEMINI_API_KEY, this would be a real AI response.",
        "Agent is running! (mock response) Ask me anything.",
        "I am an AI agent deployed to the cloud. Your question has been received and processed.",
    ],
    "docker": [
        "Docker is a containerization platform that packages app + dependencies into a container. "
        "Build once, run anywhere! Containers are lighter than VMs and start much faster."
    ],
    "deploy": [
        "Deployment is the process of putting your code on a server so others can use it. "
        "Use Railway or Render to deploy in just 5 minutes!"
    ],
    "health": [
        "Agent is operating normally. All systems operational. "
        "Health check endpoint returns 200 OK."
    ],
    "kubernetes": [
        "Kubernetes (K8s) is an open-source container orchestration system. "
        "It auto-deploys, scales and manages containerized applications."
    ],
    "redis": [
        "Redis is an ultra-fast in-memory data store. Used for cache, session storage, "
        "rate limiting, and pub/sub messaging. Perfect for stateless design!"
    ],
    "scale": [
        "Horizontal scaling = add more instances. Vertical scaling = upgrade hardware. "
        "With stateless design + Redis, you can scale horizontally without limits!"
    ],
    "security": [
        "API security needs 3 layers: (1) Authentication - who can use it, "
        "(2) Rate Limiting - limit frequency, (3) Cost Guard - limit spending."
    ],
}


def _ask_gemini(question: str) -> str:
    """Call Google Gemini API via REST. Zero extra dependencies."""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/"
        f"models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    body = json.dumps({
        "contents": [{"parts": [{"text": question}]}],
        "generationConfig": {
            "maxOutputTokens": 256,
            "temperature": 0.7,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req, timeout=30)
    data = json.loads(resp.read().decode("utf-8"))

    return data["candidates"][0]["content"]["parts"][0]["text"]


def _ask_mock(question: str) -> str:
    """Mock LLM — keyword matching, no API needed."""
    time.sleep(0.05 + random.uniform(0, 0.03))  # simulate latency
    q = question.lower()
    for keyword, responses in MOCK_RESPONSES.items():
        if keyword != "default" and keyword in q:
            return random.choice(responses)
    return random.choice(MOCK_RESPONSES["default"])


def ask(question: str, delay: float = 0.0) -> str:
    """
    Ask the LLM. Uses Gemini if GEMINI_API_KEY is set, else mock.
    Always returns a string. Never raises — falls back to mock on error.
    """
    if delay > 0:
        time.sleep(delay)

    if GEMINI_API_KEY:
        try:
            answer = _ask_gemini(question)
            logger.debug(json.dumps({
                "event": "llm_call",
                "backend": "gemini",
                "model": GEMINI_MODEL,
                "q_len": len(question),
                "a_len": len(answer),
            }))
            return answer
        except urllib.error.HTTPError as e:
            logger.warning(json.dumps({
                "event": "gemini_error",
                "status": e.code,
                "reason": str(e.reason),
            }))
            return _ask_mock(question)
        except Exception as e:
            logger.warning(json.dumps({
                "event": "gemini_error",
                "error": str(e),
            }))
            return _ask_mock(question)
    else:
        return _ask_mock(question)


def get_backend() -> str:
    """Return which LLM backend is active."""
    return f"gemini/{GEMINI_MODEL}" if GEMINI_API_KEY else "mock"
