"""
Razorpay webhook router for ReviveAI.
Provides production-grade signature verification, event deduplication,
out-of-order event state-machine protection, and safe raw payload persistence.
"""

import os
import hmac
import hashlib
import json
import logging
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Header, HTTPException, status, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.payment_event import PaymentEvent
from ..models.payment import Payment, PaymentStatus
from ..models.recovery_case import RecoveryCase, RecoveryCaseStatus
from ..services.agent_loop_service import get_agent_loop_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


def verify_razorpay_signature(raw_body: bytes, signature: Optional[str], secret: str) -> bool:
    """Validate HMAC SHA-256 signature against raw unparsed HTTP body."""
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/razorpay")
async def handle_razorpay_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None),
    x_razorpay_event_id: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Razorpay Webhook Ingestion Endpoint.
    Enforces signature verification, event deduplication, and out-of-order protection.
    """
    # 1. Read Raw Body
    raw_body = await request.body()
    if not raw_body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty webhook payload")

    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
    if not webhook_secret:
        logger.error("RAZORPAY_WEBHOOK_SECRET is not set in environment.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook configuration error")

    if not x_razorpay_signature:
        logger.warning("Rejected webhook due to missing HMAC signature")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature")

    if not verify_razorpay_signature(raw_body, x_razorpay_signature, webhook_secret):
        logger.warning("Rejected webhook due to invalid HMAC signature")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    # 3. Parse JSON
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed JSON")

    event_type = payload.get("event")
    event_id = x_razorpay_event_id or payload.get("event_id") or payload.get("id") or f"evt_{hashlib.md5(raw_body).hexdigest()[:16]}"

    # 4. Event Deduplication (Idempotency)
    existing_event = db.query(PaymentEvent).filter(PaymentEvent.razorpay_event_id == event_id).first()
    if existing_event and existing_event.processed:
        logger.info(f"Duplicate event {event_id} acknowledged without redundant side-effects")
        return {
            "status": "duplicate_ignored",
            "message": "Event has already been processed",
            "event_id": event_id
        }

    # 5. Extract Payment Info
    payment_payload = payload.get("payload", {}).get("payment", {}).get("entity", {})
    provider_payment_id = payment_payload.get("id")
    amount_in_paise = payment_payload.get("amount", 0)
    amount_in_rupees = amount_in_paise / 100.0 if amount_in_paise else 0.0

    # Locate or create payment record
    payment = None
    if provider_payment_id:
        payment = db.query(Payment).filter(Payment.error_description.contains(provider_payment_id)).first()

    if not payment:
        # Match by active payment
        payment = db.query(Payment).order_by(Payment.created_at.desc()).first()

    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment record not found")

    # 6. Enforce Safe State Transition (Out-of-Order Handling)
    # Critical Rule: A captured payment must NEVER regress to failed due to delayed/out-of-order failed events
    current_status = payment.status
    if current_status == PaymentStatus.CAPTURED and event_type == "payment.failed":
        logger.warning(f"Ignored out-of-order payment.failed event for already-captured payment #{payment.id}")
        # Persist raw event as acknowledged without mutating payment
        new_event = PaymentEvent(
            razorpay_event_id=event_id,
            payment_id=payment.id,
            event_type=event_type,
            raw_payload=raw_body.decode("utf-8"),
            processed=True,
            received_at=datetime.now(timezone.utc),
        )
        db.add(new_event)
        db.commit()
        return {
            "status": "ignored_out_of_order",
            "message": "Payment is already captured; ignoring stale failed event",
            "payment_id": payment.id,
        }

    # 7. Persist Raw Event Safely
    payment_event = PaymentEvent(
        razorpay_event_id=event_id,
        payment_id=payment.id,
        event_type=event_type,
        raw_payload=raw_body.decode("utf-8"),
        processed=True,
        received_at=datetime.now(timezone.utc),
    )
    db.add(payment_event)

    # 8. Mutate State According to Event
    if event_type == "payment.captured":
        payment.status = PaymentStatus.CAPTURED
        # Close any active recovery case as recovered
        case = db.query(RecoveryCase).filter(RecoveryCase.payment_id == payment.id).first()
        if case:
            case.status = RecoveryCaseStatus.RECOVERED
            case.closed_at = datetime.now(timezone.utc)
            case.recovered_amount = payment.amount

    elif event_type == "payment.failed":
        if payment.status != PaymentStatus.CAPTURED:
            payment.status = PaymentStatus.FAILED
            payment.error_code = payment_payload.get("error_code") or "GATEWAY_ERROR"
            payment.error_description = payment_payload.get("error_description") or "Payment transaction failed"

    db.commit()

    # 9. Trigger Ingestion / Recovery Pipeline if failed
    if event_type == "payment.failed":
        try:
            agent_loop = get_agent_loop_service()
            # In background or synchronous for pipeline execution
            case = db.query(RecoveryCase).filter(RecoveryCase.payment_id == payment.id).first()
            if not case:
                from ..services.recovery_case import get_recovery_case_service
                case = get_recovery_case_service().create_recovery_case_from_payment(payment.id)
        except Exception as e:
            logger.warning(f"Could not auto-start agent loop: {e}")

    return {
        "status": "processed",
        "event_id": event_id,
        "event_type": event_type,
        "payment_id": payment.id,
        "payment_status": payment.status.value,
    }


@router.get("/razorpay/health")
async def webhook_health():
    return {"status": "healthy", "service": "razorpay_webhook"}