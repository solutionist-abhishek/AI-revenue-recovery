# RecoverPay — AI-Gated Revenue Recovery Engine

RecoverPay is a deterministic recovery engine for failed payments, checkout abandonment, and unpaid B2B invoices. The project follows the core idea behind the Razorpay AI Buildathon 2026 track: use AI only to diagnose ambiguous failures, while all execution and customer contact remain governed by strict, auditable rules.

## One-line pitch

A deterministic recovery engine for failed payments, abandoned checkouts, and unpaid B2B invoices where an LLM is only allowed to diagnose, never to execute.

## Core architecture

- Deterministic classifier handles obvious payment declines with static rules.
- AI diagnostic module handles ambiguous or unstructured failures.
- Recovery policy engine decides retries, messaging windows, and escalation.
- Every action is logged with a rule ID and reason for full auditability.
- Razorpay-style `payment.failed` webhooks are signature-verified and persisted idempotently.
- Operators can inspect the resulting audit trail from the protected `/audit` endpoint.
- The command center is data-driven: ranking, recoverability, expected recovery, and what-if totals are computed from the payment batch through the classifier, diagnostic, and policy layers.

## Why this matters

The key differentiator is control. In fintech, an LLM must not decide whether to retry a payment or contact a customer. The model is allowed to read raw signals, identify probable causes, and return a structured diagnosis with confidence — but the policy engine is the only component with permission to act.

## Quick start

1. Open the project directory.
2. Install dependencies:

```powershell
cd d:\Projects\recoverpay
py -3 -m pip install -r requirements.txt
```

3. Start the app locally on a free port:

```powershell
cd d:\Projects\recoverpay
py -3 -m uvicorn app:app --host 0.0.0.0 --port 8010
```

4. Open the dashboard in a browser:

```text
http://localhost:8010
```

5. Run the automated verification suite:

```powershell
cd d:\Projects\recoverpay
py -3 -m pytest -q
```

6. Review the simulated payment data in data/simulated_failed_payments.json.

### Webhook demo

Set a webhook secret before starting the server to enable HMAC-SHA256 verification:

```powershell
$env:RAZORPAY_WEBHOOK_SECRET = "local-buildathon-secret"
py -3 -m uvicorn app:app --host 0.0.0.0 --port 8010
```

Send a Razorpay-style `payment.failed` payload to `POST /webhooks/razorpay` with the `x-razorpay-signature` header. The service classifies the failure, applies the deterministic policy, stores the event in SQLite, and safely treats repeated payment IDs as duplicates. Authenticated operators can review recent records at `GET /audit`.

For local demo mode, omitting `RAZORPAY_WEBHOOK_SECRET` accepts requests without signature verification. Always configure it in a deployed environment.

## Project structure

```text
recoverpay/
├── README.md
├── data/
│   └── simulated_failed_payments.json
├── docs/
│   └── architecture.md
├── src/
│   ├── __init__.py
│   ├── ai_diagnostic/
│   │   ├── __init__.py
│   │   └── diagnostic.py
│   ├── actions/
│   │   ├── __init__.py
│   │   └── recovery_actions.py
│   ├── classifier/
│   │   ├── __init__.py
│   │   └── classifier.py
│   └── policy_engine/
│       ├── __init__.py
│       └── policy.py
├── tests/
│   └── test_recovery_pipeline.py
├── requirements.txt
└── .gitignore
```

## Demo idea

Run a synthetic batch of failed payments and compare the deterministic policy engine against a naive retry-everything baseline. Show:

- total value at risk
- recovery rate by reason code
- audit trail for each decision
- real versus baseline recovered amount

## Compliance guardrails

- max retry attempts are hard-coded
- do-not-disturb windows are respected
- opt-out/chargeback suppression blocks future actions
- non-retryable reasons are never retried
- every decision is logged with a reason code

## Current implementation status

This repository includes the core MVP logic for:

- deterministic decline classification
- rule-based retry timing
- audit-friendly recovery decisions
- tests covering retryable and non-retryable scenarios
