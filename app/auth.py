"""
Authentication — Day 12 Lab
Implements API Key verification as a FastAPI dependency.
"""
import hashlib
import logging
import json

from fastapi import HTTPException, Security, Header
from fastapi.security.api_key import APIKeyHeader

from app.config import settings

logger = logging.getLogger(__name__)

# ─── API Key ─────────────────────────────────────────────────
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(x_api_key: str = Security(api_key_header)) -> str:
    """
    FastAPI dependency — verifies X-API-Key header.
    
    Returns user_id (derived from key hash) if valid.
    Raises HTTPException(401) if missing or invalid.
    """
    if not x_api_key:
        logger.warning(json.dumps({
            "event": "auth_missing",
            "detail": "No X-API-Key header provided",
        }))
        raise HTTPException(
            status_code=401,
            detail="API key required. Add header: X-API-Key: <your-key>",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Constant-time comparison to prevent timing attacks
    is_valid = _secure_compare(x_api_key, settings.agent_api_key)
    if not is_valid:
        logger.warning(json.dumps({
            "event": "auth_failed",
            "key_prefix": x_api_key[:4] + "****",
        }))
        raise HTTPException(
            status_code=401,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Derive a stable user_id from the key (so we can track per-user limits)
    user_id = "user_" + hashlib.sha256(x_api_key.encode()).hexdigest()[:8]
    logger.debug(json.dumps({"event": "auth_ok", "user_id": user_id}))
    return user_id


def _secure_compare(a: str, b: str) -> bool:
    """Constant-time string comparison to prevent timing attacks."""
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a.encode(), b.encode()):
        result |= x ^ y
    return result == 0
