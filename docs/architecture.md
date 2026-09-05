# RecoverPay architecture

The architecture is intentionally split into deterministic and diagnostic layers.

## Flow

1. Payment webhook arrives with a raw gateway code and message.
2. Deterministic classifier interprets the event.
3. If the reason is obvious, the engine applies a static retry policy.
4. If the reason is ambiguous, the LLM module diagnoses the likely root cause using a structured schema.
5. Policy engine validates the diagnosis against compliance rules before issuing a retry, message, or escalation.
6. Every action is logged to an audit trail.

## Razorpay integration boundary

`POST /webhooks/razorpay` accepts a Razorpay-style `payment.failed` event. When `RAZORPAY_WEBHOOK_SECRET` is configured, the raw request body is verified with HMAC-SHA256 against the `x-razorpay-signature` header before parsing. The payment ID is the idempotency key, so a retried webhook is recorded as a duplicate rather than producing a second recovery decision.

Webhook events and policy decisions are stored in SQLite at `data/recoverpay.db` by default. Set `RECOVERPAY_DB_PATH` to use another location. The protected `GET /audit` endpoint exposes the audit trail for the command center and operator review.

## Why the split matters

This design avoids the main fintech failure mode: giving an LLM execution authority over payments. The model is intentionally constrained to diagnosis only.

## Policy examples

- bank timeout -> retry after 15 minutes, then 2 hours, then stop
- insufficient funds -> retry next day near salary-credit windows, max 2 attempts
- invalid CVV -> stop immediately, no retry
- card blocked -> stop immediately, no retry

## Audit log model

Each event stores:

- payment_id
- decision_id
- reason_code
- rule_triggered
- attempt_count
- scheduled_at
- policy_version
- confidence_score

This makes the engine explainable and reviewable during demo and judging.
