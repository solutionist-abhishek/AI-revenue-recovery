"""AI diagnostic module for ambiguous payment failures.

This module intentionally stays read-only and diagnostic-only. The LLM does not
trigger money movement or message sends; it only produces a structured diagnosis.
"""

from __future__ import annotations


def diagnose_failure(gateway_code: str, message: str) -> dict:
    """Return a structured diagnosis for ambiguous payment failures."""
    normalized_code = (gateway_code or "").upper()
    normalized_message = (message or "").lower()

    if "timeout" in normalized_message or normalized_code == "TIMEOUT":
        return {
            "likely_cause": "bank_timeout",
            "confidence": 0.82,
            "recommended_action": "retry_after_backoff",
            "retryable": True,
        }

    if "insufficient" in normalized_message or "nsf" in normalized_message:
        return {
            "likely_cause": "insufficient_funds",
            "confidence": 0.91,
            "recommended_action": "retry_after_salary_window",
            "retryable": True,
        }

    if "cvv" in normalized_message or "expired" in normalized_message:
        return {
            "likely_cause": "card_validation_issue",
            "confidence": 0.95,
            "recommended_action": "do_not_retry",
            "retryable": False,
        }

    return {
        "likely_cause": "needs_human_review",
        "confidence": 0.45,
        "recommended_action": "manual_review",
        "retryable": False,
    }
