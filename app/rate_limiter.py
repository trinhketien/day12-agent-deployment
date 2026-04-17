"""
Rate Limiter — Day 12 Lab
Sliding Window algorithm: giới hạn số request mỗi user/phút.
"""
import time
import logging
import json
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Depends

from app.config import settings
from app.auth import verify_api_key

logger = logging.getLogger(__name__)

# Thread-safe in-memory store: user_id → deque of timestamps
_windows: dict[str, deque] = defaultdict(deque)
_lock = Lock()


def check_rate_limit(user_id: str = Depends(verify_api_key)) -> str:
    """
    FastAPI dependency — sliding window rate limiter.
    
    Algorithm:
    1. Remove timestamps older than 60 seconds
    2. Count remaining timestamps
    3. If count >= limit → raise 429
    4. Else append current timestamp
    
    Returns user_id for chaining with other dependencies.
    """
    limit = settings.rate_limit_per_minute
    now = time.time()
    window_start = now - 60.0

    with _lock:
        window = _windows[user_id]

        # Evict old timestamps (sliding window)
        while window and window[0] < window_start:
            window.popleft()

        current_count = len(window)

        if current_count >= limit:
            oldest = window[0] if window else now
            retry_after = int(oldest - window_start) + 1
            logger.warning(json.dumps({
                "event": "rate_limited",
                "user_id": user_id,
                "current_count": current_count,
                "limit": limit,
                "retry_after_seconds": retry_after,
            }))
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {limit} requests/minute. "
                       f"Retry after {retry_after}s.",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        window.append(now)

    logger.debug(json.dumps({
        "event": "rate_check_ok",
        "user_id": user_id,
        "count": current_count + 1,
        "limit": limit,
    }))
    return user_id


def get_rate_limit_status(user_id: str) -> dict:
    """Trả về trạng thái rate limit hiện tại của user (dùng cho /metrics)."""
    now = time.time()
    window_start = now - 60.0
    with _lock:
        window = _windows[user_id]
        remaining = [ts for ts in window if ts >= window_start]
    used = len(remaining)
    return {
        "user_id": user_id,
        "requests_used": used,
        "limit_per_minute": settings.rate_limit_per_minute,
        "remaining": max(0, settings.rate_limit_per_minute - used),
    }
