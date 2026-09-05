"""Deterministic payment classification logic."""

from __future__ import annotations


NON_RETRYABLE_REASONS = {
    "invalid_cvv",
    "expired_card",
    "card_blocked",
    "fraud_block",
    "stolen_card",
}

RETRYABLE_REASONS = {
    "nsf",
    "insufficient_funds",
    "bank_timeout",
    "gateway_timeout",
    "gateway_blip",
    "network_error",
}


def classify_payment(gateway_code: str, gateway_message: str) -> dict:
    """Classify a payment failure into a deterministic category.

    Returns a dictionary with:
      - category: retryable | non_retryable | ambiguous
      - normalized_reason: canonical reason label
      - confidence: coarse confidence score
    """
    code = (gateway_code or "").upper()
    message = (gateway_message or "").lower()

    if "nsf" in message or code == "NSF" or "insufficient_funds" in message:
        return {
            "category": "retryable",
            "normalized_reason": "nsf",
            "confidence": 0.96,
        }

    if any(token in message for token in ("timeout", "gateway error", "network")) or code in {"GATEWAY_ERROR", "TIMEOUT"}:
        return {
            "category": "retryable",
            "normalized_reason": "bank_timeout",
            "confidence": 0.9,
        }

    if "invalid_cvv" in message or "cvv" in message or code == "BAD_REQUEST_ERROR":
        return {
            "category": "non_retryable",
            "normalized_reason": "invalid_cvv",
            "confidence": 0.95,
        }

    if "blocked" in message or "fraud" in message or "stolen" in message or code in {"RISK_DECLINE"}:
        return {
            "category": "non_retryable",
            "normalized_reason": "card_blocked",
            "confidence": 0.94,
        }

    return {
        "category": "ambiguous",
        "normalized_reason": "needs_human_review",
        "confidence": 0.5,
    }
