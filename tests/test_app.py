import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_classify_endpoint():
    response = client.post(
        "/classify",
        json={"gateway_code": "NSF", "gateway_message": "insufficient_funds"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["category"] == "retryable"
    assert payload["normalized_reason"] == "nsf"


def test_recovery_endpoint():
    response = client.post(
        "/recover",
        json={"gateway_code": "BAD_REQUEST_ERROR", "gateway_message": "invalid_cvv"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["classification"]["category"] == "non_retryable"
    assert payload["decision"]["should_retry"] is False
    assert payload["decision"]["stop_reason"] == "non_retryable_reason"


def test_razorpay_webhook_persists_auditable_decision(monkeypatch, tmp_path):
    monkeypatch.setenv("RECOVERPAY_WEBHOOK_SECRET", "buildathon-secret")
    monkeypatch.setenv("RECOVERPAY_DB_PATH", str(tmp_path / "recoverpay.db"))
    payload = {
        "id": "evt_test_001",
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_001",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_description": "invalid_cvv",
                }
            }
        },
    }
    raw_body = json.dumps(payload).encode()
    signature = hmac.new(b"buildathon-secret", raw_body, hashlib.sha256).hexdigest()

    response = client.post(
        "/webhooks/razorpay",
        content=raw_body,
        headers={"x-razorpay-signature": signature},
    )
    assert response.status_code == 200
    assert response.json()["classification"]["normalized_reason"] == "invalid_cvv"
    assert response.json()["decision"]["should_retry"] is False

    duplicate = client.post(
        "/webhooks/razorpay",
        content=raw_body,
        headers={"x-razorpay-signature": signature},
    )
    assert duplicate.json()["duplicate"] is True

    audit_response = client.get("/audit", cookies={"session_token": "admin"})
    assert audit_response.status_code == 200
    assert audit_response.json()[0]["event_id"] == "pay_test_001"


def test_razorpay_webhook_rejects_invalid_signature(monkeypatch, tmp_path):
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "buildathon-secret")
    monkeypatch.setenv("RECOVERPAY_DB_PATH", str(tmp_path / "recoverpay.db"))
    response = client.post(
        "/webhooks/razorpay",
        content=b'{"event":"payment.failed"}',
        headers={"x-razorpay-signature": "invalid"},
    )
    assert response.status_code == 401


def test_dashboard_returns_ranked_opportunities():
    login_response = client.post(
        "/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert login_response.status_code == 200

    response = client.get("/dashboard", cookies={"session_token": "admin"})
    assert response.status_code == 200
    payload = response.json()
    assert "summary" in payload
    assert "opportunities" in payload
    assert payload["opportunities"][0]["expected_recovery"] >= payload["opportunities"][1]["expected_recovery"]


def test_simulation_returns_strategy_comparison():
    response = client.get("/simulate", cookies={"session_token": "admin"})
    assert response.status_code == 200
    payload = response.json()
    assert "current_state" in payload
    assert "strategies" in payload
    assert len(payload["strategies"]) >= 3


def test_recovery_run_returns_policy_aware_actions():
    response = client.post("/recovery-run", cookies={"session_token": "admin"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["queued_actions"] >= 1
    assert payload["approval_required"] >= 1
    assert len(payload["actions"]) == 5
    assert any(item["status"] == "approval_required" for item in payload["actions"])


def test_payments_endpoint_returns_records():
    response = client.get("/payments", cookies={"session_token": "admin"})
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) >= 4


def test_report_endpoint_returns_summary_and_chart_data():
    response = client.get("/report", cookies={"session_token": "admin"})
    assert response.status_code == 200
    payload = response.json()
    assert "summary" in payload
    assert "chart" in payload
    assert len(payload["chart"]) >= 3


def test_upload_endpoint_accepts_payment_batch():
    response = client.post(
        "/upload",
        json={
            "payments": [
                {"customer": "Test User", "amount": 25000, "failure": "Bank timeout", "recoverability": 0.8},
            ]
        },
        cookies={"session_token": "admin"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1


def test_login_flow_and_protected_dashboard():
    isolated_client = TestClient(app)

    unauthenticated = isolated_client.get("/dashboard")
    assert unauthenticated.status_code == 401

    login = isolated_client.post(
        "/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert login.status_code == 200
    payload = login.json()
    assert payload["username"] == "admin"
    assert payload["role"] == "admin"

    session_cookie = login.headers.get("set-cookie", "")
    assert "session_token=" in session_cookie

    authed = isolated_client.get("/dashboard")
    assert authed.status_code == 200
