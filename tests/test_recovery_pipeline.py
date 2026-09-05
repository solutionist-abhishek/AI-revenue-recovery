from src.classifier import classify_payment
from src.policy_engine import decide_recovery


def test_classify_nsfs_as_retryable():
    result = classify_payment("NSF", "insufficient_funds")
    assert result["category"] == "retryable"
    assert result["normalized_reason"] == "nsf"


def test_classify_invalid_cvv_as_non_retryable():
    result = classify_payment("BAD_REQUEST_ERROR", "invalid_cvv")
    assert result["category"] == "non_retryable"
    assert result["normalized_reason"] == "invalid_cvv"


def test_policy_decision_for_timeout_payment():
    decision = decide_recovery(classify_payment("GATEWAY_ERROR", "bank timeout"))
    assert decision["should_retry"] is True
    assert decision["max_attempts"] == 3
    assert decision["retry_schedule_minutes"][0] == 15


def test_policy_decision_for_non_retryable_payment():
    decision = decide_recovery(classify_payment("RISK_DECLINE", "card blocked"))
    assert decision["should_retry"] is False
    assert decision["stop_reason"] == "non_retryable_reason"
