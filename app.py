from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.classifier import classify_payment
from src.ai_diagnostic.diagnostic import diagnose_failure
from src.persistence import list_audit_events, save_webhook_event
from src.policy_engine import decide_recovery


class PaymentRequest(BaseModel):
    gateway_code: str = ""
    gateway_message: str = ""


class UploadRequest(BaseModel):
    payments: list[dict[str, Any]] = []


class LoginRequest(BaseModel):
    username: str = ""
    password: str = ""


USERS = {
    "admin": {"password": "admin123", "role": "admin", "name": "Operations Admin"},
    "operator": {"password": "ops123", "role": "operator", "name": "Recovery Operator"},
}


def get_current_user(request: Request) -> dict[str, str]:
    session_token = request.cookies.get("session_token")
    if not session_token or session_token not in USERS:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = USERS[session_token]
    return {"username": session_token, "role": user["role"], "name": user["name"]}


SIMULATED_PAYMENTS_PATH = Path(__file__).resolve().parent / "data" / "simulated_failed_payments.json"


def load_simulated_payments() -> list[dict[str, Any]]:
    return json.loads(SIMULATED_PAYMENTS_PATH.read_text(encoding="utf-8"))


def build_opportunities() -> list[dict[str, Any]]:
    opportunities = []
    recovery_rates = {
        "nsf": 0.62,
        "insufficient_funds": 0.62,
        "bank_timeout": 0.88,
        "gateway_timeout": 0.88,
        "network_error": 0.84,
        "invalid_cvv": 0.0,
        "card_blocked": 0.0,
        "needs_human_review": 0.25,
    }

    for payment in load_simulated_payments():
        classification = classify_payment(payment["gateway_code"], payment["gateway_message"])
        diagnosis = None
        if classification["category"] == "ambiguous":
            diagnosis = diagnose_failure(payment["gateway_code"], payment["gateway_message"])
            classification = {
                **classification,
                "normalized_reason": diagnosis["likely_cause"],
                "confidence": diagnosis["confidence"],
                "diagnostic_source": "ai_diagnostic",
            }

        decision = decide_recovery(classification)
        reason = classification["normalized_reason"]
        recoverability = recovery_rates.get(reason, 0.25 if decision["should_retry"] else 0.0)
        approval_required = payment["amount"] >= 50000 or reason == "needs_human_review"
        if approval_required:
            recoverability = min(recoverability, 0.25)

        if approval_required:
            action = "Request approval before recovery"
            status = "approval"
        elif decision["should_retry"]:
            action = "Retry with policy backoff"
            status = "retry"
        else:
            action = "Stop and review"
            status = "review"

        reasons = [
            f"Gateway {payment['gateway_code']} normalized to {reason}",
            f"Policy decision: {'retry permitted' if decision['should_retry'] else decision['stop_reason']}",
            f"Confidence: {classification['confidence']:.0%}",
        ]
        if diagnosis:
            reasons.append(f"AI diagnosis: {diagnosis['likely_cause']} ({diagnosis['recommended_action']})")
        if approval_required:
            reasons.append("Human approval is required above the ₹50,000 guardrail")

        opportunities.append({
            "customer": payment["payment_id"],
            "payment_id": payment["payment_id"],
            "merchant_id": payment["merchant_id"],
            "amount": payment["amount"],
            "failure": payment["gateway_message"],
            "gateway_code": payment["gateway_code"],
            "normalized_reason": reason,
            "category": classification["category"],
            "recoverability": recoverability,
            "expected_recovery": round(payment["amount"] * recoverability),
            "status": status,
            "risk": "HIGH" if approval_required else "LOW" if recoverability >= 0.7 else "MEDIUM",
            "confidence": classification["confidence"],
            "recommended_action": action,
            "approval_required": approval_required,
            "reasons": reasons,
            "guardrail": "HUMAN_APPROVAL_REQUIRED" if approval_required else "PASSED",
            "action_label": action.upper().replace(" ", "_"),
            "classification": classification,
            "decision": decision,
        })

    return sorted(opportunities, key=lambda item: item["expected_recovery"], reverse=True)


def build_payment_records() -> list[dict[str, Any]]:
    return [
        {
            "customer": item["customer"],
            "amount": item["amount"],
            "failure": item["failure"],
            "recoverability": item["recoverability"],
            "expected_recovery": item["expected_recovery"],
            "status": item["status"],
            "risk": item["risk"],
        }
        for item in build_opportunities()
    ]


def build_dashboard() -> dict[str, Any]:
    opportunities = build_opportunities()
    total_at_risk = sum(item["amount"] for item in opportunities)
    expected_recovery = sum(item["expected_recovery"] for item in opportunities)
    high_priority = sum(1 for item in opportunities if item["expected_recovery"] >= 30000)
    return {
        "summary": {
            "revenue_at_risk": total_at_risk,
            "expected_recovery": expected_recovery,
            "top_recovery_rate": round((expected_recovery / total_at_risk) * 100, 1),
            "high_priority_cases": high_priority,
        },
        "opportunities": opportunities,
        "insights": {
            "headline": f"{len(opportunities)} PIPELINE OPPORTUNITIES",
            "recommended_now": f"Prioritize {opportunities[0]['customer']} ({opportunities[0]['normalized_reason']}) first",
        },
    }


def build_simulation() -> dict[str, Any]:
    opportunities = build_opportunities()
    total_at_risk = sum(item["amount"] for item in opportunities)
    expected_recovery = sum(item["expected_recovery"] for item in opportunities)
    retryable_recovery = sum(
        item["expected_recovery"] for item in opportunities if item["decision"]["should_retry"]
    )
    targeted_recovery = sum(
        item["expected_recovery"] for item in opportunities if item["status"] != "review"
    )
    current_state = {
        "failed_payments": len(opportunities),
        "revenue_at_risk": total_at_risk,
        "current_recovery": 0,
        "recovery_rate": 0,
    }
    strategies = [
        {"name": "No automation", "expected_recovery": 0, "delta": 0},
        {"name": "Retry everything", "expected_recovery": retryable_recovery, "delta": retryable_recovery},
        {"name": "AI recovery", "expected_recovery": expected_recovery, "delta": expected_recovery},
        {"name": "AI + guardrails", "expected_recovery": targeted_recovery, "delta": targeted_recovery},
    ]
    return {
        "current_state": current_state,
        "strategies": strategies,
    }


def build_report() -> dict[str, Any]:
    records = build_payment_records()
    summary = {
        "total_failed": len(records),
        "total_at_risk": sum(item["amount"] for item in records),
        "expected_recovery": sum(item["expected_recovery"] for item in records),
        "retryable": sum(1 for item in records if item["status"] == "retry"),
        "nudge_required": sum(1 for item in records if item["status"] == "nudge"),
    }
    chart = [
        {"label": "Retry", "value": sum(1 for item in records if item["status"] == "retry")},
        {"label": "Nudge", "value": sum(1 for item in records if item["status"] == "nudge")},
        {"label": "Approval", "value": sum(1 for item in records if item["status"] == "approval")},
    ]
    return {"summary": summary, "chart": chart, "records": records}


app = FastAPI(title="RecoverPay", version="1.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.post("/classify")
def classify_endpoint(payload: PaymentRequest) -> dict:
    return classify_payment(payload.gateway_code, payload.gateway_message)


@app.post("/recover")
def recover_endpoint(payload: PaymentRequest) -> dict:
    classification = classify_payment(payload.gateway_code, payload.gateway_message)
    decision = decide_recovery(classification)
    return {
        "classification": classification,
        "decision": decision,
    }


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
    if not secret:
        return os.getenv("RECOVERPAY_ENV", "development").lower() != "production"
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return bool(signature) and hmac.compare_digest(expected, signature)


@app.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request) -> dict[str, Any]:
    raw_body = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")
    if not verify_webhook_signature(raw_body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="Webhook body must be valid JSON") from error

    event_type = payload.get("event", "unknown")
    payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
    gateway_code = payment.get("error_code", "")
    gateway_message = payment.get("error_description", "")
    event_id = payment.get("id") or payload.get("id")
    if not event_id:
        raise HTTPException(status_code=400, detail="Webhook is missing a payment or event id")

    classification = classify_payment(gateway_code, gateway_message)
    decision = decide_recovery(classification)
    recorded = save_webhook_event(event_id, event_type, payload, classification, decision)
    return {
        "status": "accepted",
        "duplicate": not recorded,
        "event_id": event_id,
        "classification": classification,
        "decision": decision,
    }


@app.post("/login")
def login(payload: LoginRequest, response: Response) -> dict[str, str]:
    user = USERS.get(payload.username)
    if not user or user["password"] != payload.password:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    response.set_cookie(
        key="session_token",
        value=payload.username,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 8,
    )
    return {"username": payload.username, "role": user["role"], "name": user["name"]}


@app.post("/logout")
def logout(response: Response) -> dict[str, str]:
    response.delete_cookie("session_token")
    return {"status": "logged_out"}


@app.get("/me")
def me(request: Request) -> dict[str, str]:
    return get_current_user(request)


@app.get("/dashboard")
def dashboard(request: Request) -> dict[str, Any]:
    get_current_user(request)
    return build_dashboard()


@app.get("/simulate")
def simulate(request: Request) -> dict[str, Any]:
    get_current_user(request)
    return build_simulation()


@app.post("/recovery-run")
def recovery_run(request: Request) -> dict[str, Any]:
    user = get_current_user(request)
    opportunities = build_opportunities()
    actions = [
        {
            "customer": item["customer"],
            "action": item["recommended_action"],
            "amount": item["amount"],
            "expected_recovery": item["expected_recovery"],
            "status": "approval_required" if item["approval_required"] else "queued",
        }
        for item in opportunities
    ]
    approval_count = sum(item["status"] == "approval_required" for item in actions)
    return {
        "status": "completed",
        "operator": user["name"],
        "queued_actions": len(actions) - approval_count,
        "approval_required": approval_count,
        "expected_recovery": sum(item["expected_recovery"] for item in actions),
        "actions": actions,
    }


@app.get("/payments")
def payments(request: Request) -> list[dict[str, Any]]:
    get_current_user(request)
    return build_payment_records()


@app.get("/report")
def report(request: Request) -> dict[str, Any]:
    get_current_user(request)
    return build_report()


@app.get("/audit")
def audit(request: Request) -> list[dict[str, Any]]:
    get_current_user(request)
    return list_audit_events()


@app.post("/upload")
def upload_payments(request: UploadRequest, session: Request) -> dict[str, Any]:
    get_current_user(session)
    records = request.payments or []
    return {"count": len(records), "payments": records}


@app.get("/")
def index() -> FileResponse:
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
