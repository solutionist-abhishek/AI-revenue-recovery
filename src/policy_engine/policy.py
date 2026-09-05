"""Deterministic recovery policy engine."""

from __future__ import annotations


RETRY_TABLE = {
    "nsf": {"should_retry": True, "retry_schedule_minutes": [1440, 2880], "max_attempts": 2},
    "insufficient_funds": {"should_retry": True, "retry_schedule_minutes": [1440, 2880], "max_attempts": 2},
    "bank_timeout": {"should_retry": True, "retry_schedule_minutes": [15, 120], "max_attempts": 3},
    "gateway_timeout": {"should_retry": True, "retry_schedule_minutes": [15, 120], "max_attempts": 3},
    "gateway_blip": {"should_retry": True, "retry_schedule_minutes": [15, 120], "max_attempts": 3},
    "network_error": {"should_retry": True, "retry_schedule_minutes": [15, 120], "max_attempts": 3},
    "invalid_cvv": {"should_retry": False, "stop_reason": "non_retryable_reason"},
    "expired_card": {"should_retry": False, "stop_reason": "non_retryable_reason"},
    "card_blocked": {"should_retry": False, "stop_reason": "non_retryable_reason"},
    "fraud_block": {"should_retry": False, "stop_reason": "non_retryable_reason"},
    "stolen_card": {"should_retry": False, "stop_reason": "non_retryable_reason"},
}


def decide_recovery(classification: dict) -> dict:
    """Apply the deterministic policy engine to a classified payment failure."""
    reason = classification.get("normalized_reason", "needs_human_review")
    policy = RETRY_TABLE.get(reason, {"should_retry": False, "stop_reason": "needs_human_review"})

    decision = {
        "reason": reason,
        "should_retry": policy.get("should_retry", False),
        "stop_reason": policy.get("stop_reason"),
        "max_attempts": policy.get("max_attempts", 0),
        "retry_schedule_minutes": policy.get("retry_schedule_minutes", []),
    }

    if reason == "needs_human_review":
        decision["should_retry"] = False
        decision["stop_reason"] = "needs_human_review"

    return decision
