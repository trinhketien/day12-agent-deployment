"""
Cost Guard — Day 12 Lab
Monthly budget protection per user.

Tracks estimated LLM spending and blocks requests when budget is exceeded.
In-memory implementation (production would use Redis with TTL).
"""
import time
import logging
import json
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional

from fastapi import HTTPException, Depends

from app.config import settings
from app.rate_limiter import check_rate_limit

logger = logging.getLogger(__name__)

# ─── Token cost estimates (GPT-4o-mini tier) ─────────────────
_COST_PER_INPUT_TOKEN = 0.00015 / 1000   # $0.15 per M tokens
_COST_PER_OUTPUT_TOKEN = 0.0006 / 1000   # $0.60 per M tokens
_AVG_WORDS_PER_TOKEN = 0.75              # ~0.75 words per token


@dataclass
class UserBudget:
    """Budget tracker for a single user/month."""
    spent_usd: float = 0.0
    request_count: int = 0
    month_key: str = field(default_factory=lambda: time.strftime("%Y-%m"))
    lock: Lock = field(default_factory=Lock, compare=False, repr=False)

    def reset_if_new_month(self):
        current_month = time.strftime("%Y-%m")
        if current_month != self.month_key:
            self.spent_usd = 0.0
            self.request_count = 0
            self.month_key = current_month


# Global budget registry
_budgets: dict[str, UserBudget] = {}
_registry_lock = Lock()


def _get_budget(user_id: str) -> UserBudget:
    with _registry_lock:
        if user_id not in _budgets:
            _budgets[user_id] = UserBudget()
        return _budgets[user_id]


def estimate_cost(question: str, answer: str = "") -> float:
    """Estimate USD cost for a single LLM call."""
    input_words = len(question.split())
    output_words = len(answer.split()) if answer else 50  # assume 50 words output
    
    input_tokens = input_words / _AVG_WORDS_PER_TOKEN
    output_tokens = output_words / _AVG_WORDS_PER_TOKEN
    
    return (
        input_tokens * _COST_PER_INPUT_TOKEN
        + output_tokens * _COST_PER_OUTPUT_TOKEN
    )


def check_budget(user_id: str = Depends(check_rate_limit)) -> str:
    """
    FastAPI dependency — monthly budget guard.
    
    Checks if adding an estimated cost would exceed the monthly budget.
    Raises HTTPException(402) if budget is exhausted.
    
    Returns user_id for chaining.
    """
    budget = _get_budget(user_id)
    monthly_limit = settings.monthly_budget_usd

    with budget.lock:
        budget.reset_if_new_month()

        # Estimate cost for upcoming request (worst case: long question + long answer)
        estimated_cost = estimate_cost("x" * 500)  # conservative estimate

        if budget.spent_usd + estimated_cost > monthly_limit:
            logger.warning(json.dumps({
                "event": "budget_exceeded",
                "user_id": user_id,
                "spent_usd": round(budget.spent_usd, 4),
                "limit_usd": monthly_limit,
                "month": budget.month_key,
            }))
            raise HTTPException(
                status_code=402,
                detail=(
                    f"Monthly budget of ${monthly_limit:.2f} exceeded. "
                    f"Current spend: ${budget.spent_usd:.4f}. "
                    f"Budget resets at the start of next month."
                ),
            )

    logger.debug(json.dumps({
        "event": "budget_ok",
        "user_id": user_id,
        "spent_usd": round(budget.spent_usd, 4),
        "limit_usd": monthly_limit,
    }))
    return user_id


def record_cost(user_id: str, question: str, answer: str):
    """Record actual cost after a successful LLM call."""
    cost = estimate_cost(question, answer)
    budget = _get_budget(user_id)
    with budget.lock:
        budget.reset_if_new_month()
        budget.spent_usd += cost
        budget.request_count += 1
    logger.info(json.dumps({
        "event": "cost_recorded",
        "user_id": user_id,
        "cost_usd": round(cost, 6),
        "total_usd": round(budget.spent_usd, 4),
        "request_count": budget.request_count,
    }))


def get_budget_status(user_id: str) -> dict:
    """Trả về trạng thái budget của user (dùng cho /metrics)."""
    budget = _get_budget(user_id)
    with budget.lock:
        budget.reset_if_new_month()
        return {
            "user_id": user_id,
            "spent_usd": round(budget.spent_usd, 4),
            "limit_usd": settings.monthly_budget_usd,
            "remaining_usd": round(
                max(0.0, settings.monthly_budget_usd - budget.spent_usd), 4
            ),
            "request_count": budget.request_count,
            "month": budget.month_key,
        }
