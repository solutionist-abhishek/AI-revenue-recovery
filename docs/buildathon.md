# Buildathon Submission Guide

## Project

**RecoverPay** is an AI-gated revenue recovery engine for failed payments.

**Track:** AI Revenue Recovery

**Repository:** https://github.com/solutionist-abhishek/AI-revenue-recovery

## Problem

Merchants lose revenue when payment failures are retried blindly or handled manually. RecoverPay explains the likely cause of each failure, ranks recovery opportunities, and recommends policy-safe next actions.

## Differentiator

AI is diagnostic-only. The deterministic policy engine controls retries, escalation, and approval requirements. This keeps recovery explainable and prevents a language model from directly moving money or contacting customers without guardrails.

## Five-minute demo

1. Open the dashboard and log in with the local demo account.
2. Show the five payment events loaded from `data/simulated_failed_payments.json`.
3. Select an error and demonstrate classification plus recovery policy.
4. Open the top opportunity and explain its reason, confidence, and guardrail.
5. Click **Run Recovery** to show queued actions and human approval requirements.
6. Send a `payment.failed` webhook and show its classification in the audit trail.
7. Show the simulation total matching the dashboard's computed expected recovery.

## What broke and how it was fixed

- The first dashboard used hardcoded presentation data. It was replaced with a pipeline that loads the payment batch and runs classifier, AI diagnostic, and policy decisions for every record.
- Browser login succeeded while the login panel remained visible because the shared `hidden` CSS class was missing. The UI state transition was fixed and tested.
- Old Uvicorn processes served stale code during testing. Fresh ports and explicit health checks were used to validate the current build.
- Repeated webhook delivery could create duplicate decisions. Payment IDs are now stored as idempotency keys.
- Webhook verification is permissive for local demos but fails closed in production when no secret is configured.

## Demo credentials

The checked-in credentials are for local demonstration only. Do not use them in a deployment. Configure real authentication and Razorpay sandbox secrets before production use.
