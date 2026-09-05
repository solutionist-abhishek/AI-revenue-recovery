from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.classifier import classify_payment
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


def build_payment_records() -> list[dict[str, Any]]:
    return [
        {
            "customer": "Rahul",
            "amount": 48000,
            "failure": "Bank timeout",
            "recoverability": 0.94,
            "expected_recovery": 45120,
            "status": "retry",
            "risk": "LOW",
        },
        {
            "customer": "Neha",
            "amount": 75000,
            "failure": "Network error",
            "recoverability": 0.90,
            "expected_recovery": 67500,
            "status": "retry",
            "risk": "LOW",
        },
        {
            "customer": "Arjun",
            "amount": 8500,
            "failure": "UPI timeout",
            "recoverability": 0.88,
            "expected_recovery": 7480,
            "status": "retry",
            "risk": "LOW",
        },
        {
            "customer": "Priya",
            "amount": 12500,
            "failure": "Low balance",
            "recoverability": 0.62,
            "expected_recovery": 7750,
            "status": "nudge",
            "risk": "MEDIUM",
        },
        {
            "customer": "Sanjay",
            "amount": 75000,
            "failure": "Card decline",
            "recoverability": 0.53,
            "expected_recovery": 39750,
            "status": "approval",
            "risk": "HIGH",
        },
    ]


def build_opportunities() -> list[dict[str, Any]]:
    opportunities = [
        {
            "customer": "Rahul",
            "amount": 48000,
            "failure": "Bank timeout",
            "recoverability": 0.94,
            "expected_recovery": 45120,
            "risk": "LOW",
            "confidence": 0.91,
            "recommended_action": "Retry payment later",
            "approval_required": False,
            "reasons": [
                "Bank timeout is usually transient",
                "Customer has 17/18 successful payments",
                "Customer lifetime value: ₹1.25L",
                "No suspicious payment behavior",
                "Similar failures recovered successfully",
            ],
            "guardrail": "PASSED",
        },
        {
            "customer": "Neha",
            "amount": 75000,
            "failure": "Network error",
            "recoverability": 0.90,
            "expected_recovery": 67500,
            "risk": "LOW",
            "confidence": 0.88,
            "recommended_action": "Retry with backoff",
            "approval_required": False,
            "reasons": [
                "Failure pattern matches infrastructure instability",
                "Recent payment history is healthy",
                "Customer has low dispute rate",
                "Retry timing is low-risk",
            ],
            "guardrail": "PASSED",
        },
        {
            "customer": "Arjun",
            "amount": 8500,
            "failure": "UPI timeout",
            "recoverability": 0.88,
            "expected_recovery": 7480,
            "risk": "LOW",
            "confidence": 0.86,
            "recommended_action": "Send payment link",
            "approval_required": False,
            "reasons": [
                "Transient gateway issue",
                "Low-value payment minimizes risk",
                "Alternate method is inexpensive to test",
                "Customer engagement is high",
            ],
            "guardrail": "PASSED",
        },
        {
            "customer": "Priya",
            "amount": 12500,
            "failure": "Low balance",
            "recoverability": 0.62,
            "expected_recovery": 7750,
            "risk": "MEDIUM",
            "confidence": 0.72,
            "recommended_action": "Send gentle nudge",
            "approval_required": False,
            "reasons": [
                "Issue appears customer-side",
                "A reminder may improve completion",
                "Payment is mid-sized and low-risk",
                "Nudge is cheaper than a retry loop",
            ],
            "guardrail": "PASSED",
        },
        {
            "customer": "Sanjay",
            "amount": 75000,
            "failure": "Card decline",
            "recoverability": 0.53,
            "expected_recovery": 39750,
            "risk": "HIGH",
            "confidence": 0.67,
            "recommended_action": "Request approval before retry",
            "approval_required": True,
            "reasons": [
                "High-value payment above approval threshold",
                "Failure may be customer or issuer issue",
                "Action must be controlled and auditable",
                "Merchant policy requires manual review",
            ],
            "guardrail": "HUMAN_APPROVAL_REQUIRED",
        },
    ]

    for item in opportunities:
        item["action_label"] = item["recommended_action"].upper().replace(" ", "_")
    return sorted(opportunities, key=lambda item: item["expected_recovery"], reverse=True)


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
            "headline": "12 HIGH-VALUE OPPORTUNITIES",
            "recommended_now": "Retry Rahul, Neha, and Arjun first",
        },
    }


def build_simulation() -> dict[str, Any]:
    current_state = {
        "failed_payments": 47,
        "revenue_at_risk": 840000,
        "current_recovery": 170000,
        "recovery_rate": 20,
    }
    strategies = [
        {"name": "No automation", "expected_recovery": 170000, "delta": 0},
        {"name": "Retry everything", "expected_recovery": 240000, "delta": 70000},
        {"name": "AI recovery", "expected_recovery": 390000, "delta": 220000},
        {"name": "AI + targeted nudges", "expected_recovery": 430000, "delta": 260000},
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
        return True
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
