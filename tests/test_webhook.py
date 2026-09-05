"""
Automated tests for Razorpay webhook ingestion.
Covers valid signature, invalid signature, duplicate idempotency, and out-of-order event safety.
"""

import os
import hmac
import hashlib
import json
import pytest
from fastapi.testclient import TestClient
from apps.api.app.main import app
from apps.api.app.database import SessionLocal
from apps.api.app.models import Payment, PaymentStatus, PaymentEvent

client = TestClient(app)
WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "demo_webhook_secret")


def test_valid_webhook_signature():
    """Test webhook with valid HMAC SHA256 signature."""
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_001",
                    "amount": 250000,
                    "currency": "INR",
                    "status": "captured"
                }
            }
        }
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    response = client.post(
        "/webhook/razorpay",
        content=raw_body,
        headers={
            "X-Razorpay-Signature": sig,
            "X-Razorpay-Event-Id": "evt_test_valid_sig_1",
            "Content-Type": "application/json"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"


def test_invalid_webhook_signature():
    """Test webhook rejection on invalid signature."""
    payload = {"event": "payment.failed", "payload": {}}
    raw_body = json.dumps(payload).encode("utf-8")

    response = client.post(
        "/webhook/razorpay",
        content=raw_body,
        headers={
            "X-Razorpay-Signature": "invalid_tampered_signature",
            "X-Razorpay-Event-Id": "evt_invalid_1",
            "Content-Type": "application/json"
        }
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid signature"


def test_duplicate_event_idempotency():
    """Test that duplicate events are recognized and processed only once."""
    payload = {
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_dup",
                    "amount": 100000,
                    "currency": "INR",
                    "status": "failed",
                    "error_code": "BAD_REQUEST"
                }
            }
        }
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    event_id = "evt_dedup_unique_999"

    # First delivery
    res1 = client.post(
        "/webhook/razorpay",
        content=raw_body,
        headers={"X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": event_id}
    )
    assert res1.status_code == 200

    # Second duplicate delivery
    res2 = client.post(
        "/webhook/razorpay",
        content=raw_body,
        headers={"X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": event_id}
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "duplicate_ignored"


def test_out_of_order_event_protection():
    """Test that a payment.failed event received after payment.captured does not regress payment state."""
    db = SessionLocal()
    try:
        # Get or create payment marked as captured
        p = db.query(Payment).filter(Payment.status == PaymentStatus.CAPTURED).first()
        assert p is not None

        payload = {
            "event": "payment.failed",
            "payload": {
                "payment": {
                    "entity": {
                        "id": f"pay_{p.id}",
                        "amount": int(p.amount * 100),
                        "status": "failed"
                    }
                }
            }
        }
        raw_body = json.dumps(payload).encode("utf-8")
        sig = hmac.new(WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

        response = client.post(
            "/webhook/razorpay",
            content=raw_body,
            headers={"X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": "evt_out_of_order_1"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ignored_out_of_order"

        # Verify DB was NOT regressed
        db.refresh(p)
        assert p.status == PaymentStatus.CAPTURED
    finally:
        db.close()
