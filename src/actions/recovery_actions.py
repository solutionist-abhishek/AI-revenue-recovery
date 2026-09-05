"""Action layer for recovery workflows.

In the hackathon prototype, this is a thin, deterministic action facade that would
interact with payment APIs and messaging services in a real deployment.
"""


def create_retry_action(payment_id: str, retry_in_minutes: int, reason: str) -> dict:
    return {
        "payment_id": payment_id,
        "action": "retry_payment_link",
        "retry_in_minutes": retry_in_minutes,
        "reason": reason,
    }


def create_message_action(payment_id: str, channel: str, message: str) -> dict:
    return {
        "payment_id": payment_id,
        "action": "send_message",
        "channel": channel,
        "message": message,
    }
