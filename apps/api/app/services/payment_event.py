"""
Payment event service for handling Razorpay webhook events.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import json
from sqlalchemy.orm import Session
from ..services.recovery_case import get_recovery_case_service
from ..database import SessionLocal
from ..models.payment_event import PaymentEvent
from ..models.payment import Payment, PaymentStatus
from ..models.recovery_case import RecoveryCase, RecoveryCaseStatus
from ..models.audit_log import AuditLog
from ..services.timeline import get_timeline_service

logger = logging.getLogger(__name__)

class PaymentEventService:
    def process_webhook_event(self, event_type: str, event_payload: Dict[str, Any],
                            razorpay_event_id: str) -> Dict[str, Any]:
        """
        Process a Razorpay webhook event.

        Args:
            event_type: Type of the event (e.g., 'payment.captured', 'payment.failed')
            event_payload: Payload data from the webhook
            razorpay_event_id: Unique ID for the event (for idempotency)

        Returns:
            dict: Result of processing the webhook event
        """
        logger.info(f"Processing Razorpay webhook event: {event_type} (ID: {razorpay_event_id})")

        db = SessionLocal()
        try:
            # Check if we've already processed this event (idempotency)
            existing_event = db.query(PaymentEvent).filter(
                PaymentEvent.razorpay_event_id == razorpay_event_id
            ).first()

            if existing_event:
                logger.info(f"Event {razorpay_event_id} already processed, skipping")
                return {
                    "success": True,
                    "event_id": razorpay_event_id,
                    "event_type": event_type,
                    "processed": False,
                    "reason": "Already processed",
                    "timestamp": datetime.utcnow().isoformat()
                }

            # Create payment event record
            payment_event = PaymentEvent(
                razorpay_event_id=razorpay_event_id,
                event_type=event_type,
                payload=str(event_payload)  # Store as JSON string
            )

            db.add(payment_event)
            db.flush()  # Get the ID without committing

            # Process based on event type
            result = {
                "success": False,
                "event_id": razorpay_event_id,
                "event_type": event_type,
                "processed": True,
                "actions_taken": []
            }

            if event_type == "payment.captured":
                result = self._handle_payment_captured(event_payload, payment_event, db, result)
            elif event_type == "payment.failed":
                result = self._handle_payment_failed(event_payload, payment_event, db, result)
            elif event_type == "payment.authorized":
                result = self._handle_payment_authorized(event_payload, payment_event, db, result)
            else:
                # For other event types, just record them
                logger.info(f"Unhandled event type: {event_type}")
                result["actions_taken"].append({
                    "action": "record_event",
                    "details": f"Recorded unhandled event type: {event_type}"
                })
                result["success"] = True

            # Update the payment event with processing result
            payment_event.processed = True
            payment_event.processed_at = datetime.utcnow()
            payment_event.result = str(result)

            # Record in timeline
            timeline_service = get_timeline_service()
            if "case_id" in result:
                timeline_service.add_event_to_timeline(
                    case_id=result["case_id"],
                    actor="payment_event_service",
                    action=f"process_webhook_{event_type}",
                    input_data={
                        "event_type": event_type,
                        "razorpay_event_id": razorpay_event_id
                    },
                    decision_data=result
                )

            # Create audit log
            if "case_id" in result:
                audit_log = AuditLog(
                    case_id=result["case_id"],
                    actor="payment_event_service",
                    action=f"process_webhook_{event_type}",
                    input_json=str({
                        "event_type": event_type,
                        "razorpay_event_id": razorpay_event_id,
                        "payload": event_payload
                    }),
                    decision_json=str(result),
                    policy_result="processed"
                )
                db.add(audit_log)

            db.commit()

            return result

        except Exception as e:
            db.rollback()
            logger.error(f"Error processing webhook event {razorpay_event_id}: {str(e)}")
            return {
                "success": False,
                "event_id": razorpay_event_id,
                "event_type": event_type,
                "processed": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        finally:
            db.close()

    def _handle_payment_captured(self, event_payload: Dict[str, Any],
                               payment_event: PaymentEvent, db: Session,
                               result: Dict) -> Dict:
        """Handle payment.captured event."""
        # Extract payment information from payload
        payment_data = event_payload.get("payment", {})
        razorpay_payment_id = payment_data.get("id")
        amount = payment_data.get("amount")  # Amount in smallest currency unit (paise for INR)
        currency = payment_data.get("currency", "INR")
        status = payment_data.get("status")
        method = payment_data.get("method")
        bank = payment_data.get("bank")

        # Convert amount from paise to rupees for INR
        if currency.upper() == "INR" and amount is not None:
            amount = amount / 100.0

        logger.info(f"Payment captured: {razorpay_payment_id}, amount: {amount} {currency}")

        # Find the payment in our system
        payment = db.query(Payment).filter(
            Payment.razorpay_payment_id == razorpay_payment_id
        ).first()

        if payment:
            # Update payment status
            old_status = payment.status
            payment.status = PaymentStatus.CAPTURED
            payment.amount = amount
            payment.currency = currency
            payment.method = method
            payment.bank = bank
            payment.updated_at = datetime.utcnow()

            # Check if there's a recovery case for this payment
            recovery_case = db.query(RecoveryCase).filter(
                RecoveryCase.payment_id == payment.id
            ).first()

            if recovery_case:
                # Update recovery case status to recovered
                old_case_status = recovery_case.status
                recovery_case.status = RecoveryCaseStatus.RECOVERED
                recovery_case.closed_at = datetime.utcnow()
                recovery_case.recovered_amount = amount
                recovery_case.updated_at = datetime.utcnow()

                result["actions_taken"].append({
                    "action": "update_recovery_case",
                    "details": f"Updated recovery case {recovery_case.id} status from {old_case_status} to RECOVERED"
                })

                # Update case ID in result for timeline/audit
                result["case_id"] = recovery_case.id

            result["actions_taken"].append({
                "action": "update_payment",
                "details": f"Updated payment {payment.id} status from {old_status} to CAPTURED"
            })

            result["success"] = True
            result["payment_id"] = payment.id
            result["amount"] = amount
            result["currency"] = currency

        else:
            logger.warning(f"Payment not found for Razorpay ID: {razorpay_payment_id}")
            result["actions_taken"].append({
                "action": "payment_not_found",
                "details": f"No payment found for Razorpay ID: {razorpay_payment_id}"
            })

        return result

    def _handle_payment_failed(self, event_payload: Dict[str, Any],
                             payment_event: PaymentEvent, db: Session,
                             result: Dict) -> Dict:
        """Handle payment.failed event."""
        # Extract payment information from payload
        payment_data = event_payload.get("payment", {})
        razorpay_payment_id = payment_data.get("id")
        amount = payment_data.get("amount")  # Amount in smallest currency unit (paise for INR)
        currency = payment_data.get("currency", "INR")
        status = payment_data.get("status")
        method = payment_data.get("method")
        bank = payment_data.get("bank")
        error_code = payment_data.get("error_code")
        error_description = payment_data.get("error_description")

        # Convert amount from paise to rupees for INR
        if currency.upper() == "INR" and amount is not None:
            amount = amount / 100.0

        logger.info(f"Payment failed: {razorpay_payment_id}, amount: {amount} {currency}, error: {error_code}")

        # Find the payment in our system
        payment = db.query(Payment).filter(
            Payment.razorpay_payment_id == razorpay_payment_id
        ).first()

        if payment:
            # Update payment status
            old_status = payment.status
            payment.status = PaymentStatus.FAILED
            payment.amount = amount
            payment.currency = currency
            payment.method = method
            payment.bank = bank
            payment.error_code = error_code
            payment.error_description = error_description
            payment.updated_at = datetime.utcnow()

            # Increment attempt count
            payment.attempt_count += 1

            # Check if there's a recovery case for this payment
            recovery_case = db.query(RecoveryCase).filter(
                RecoveryCase.payment_id == payment.id
            ).first()

            if recovery_case:
                # Update recovery case with failure information
                recovery_case.amount = amount
                recovery_case.currency = currency
                recovery_case.updated_at = datetime.utcnow()
                # Note: We don't change the status here - it should remain OPEN
                # The agent loop will handle creating recovery actions

                result["actions_taken"].append({
                    "action": "update_recovery_case_failure_info",
                    "details": f"Updated recovery case {recovery_case.id} with failure information"
                })

                # Update case ID in result for timeline/audit
                result["case_id"] = recovery_case.id

            result["actions_taken"].append({
                "action": "update_payment",
                "details": f"Updated payment {payment.id} status from {old_status} to FAILED"
            })

            result["success"] = True
            result["payment_id"] = payment.id
            result["amount"] = amount
            result["currency"] = currency
            result["error_code"] = error_code

        else:
            # If payment doesn't exist, we might want to create it
            # For now, we'll just log it
            logger.warning(f"Payment not found for Razorpay ID: {razorpay_payment_id}")
            result["actions_taken"].append({
                "action": "payment_not_found",
                "details": f"No payment found for Razorpay ID: {razorpay_payment_id}"
            })

        return result

    def _handle_payment_authorized(self, event_payload: Dict[str, Any],
                                 payment_event: PaymentEvent, db: Session,
                                 result: Dict) -> Dict:
        """Handle payment.authorized event."""
        # Extract payment information from payload
        payment_data = event_payload.get("payment", {})
        razorpay_payment_id = payment_data.get("id")
        amount = payment_data.get("amount")  # Amount in smallest currency unit (paise for INR)
        currency = payment_data.get("currency", "INR")
        status = payment_data.get("status")
        method = payment_data.get("method")
        bank = payment_data.get("bank")

        # Convert amount from paise to rupees for INR
        if currency.upper() == "INR" and amount is not None:
            amount = amount / 100.0

        logger.info(f"Payment authorized: {razorpay_payment_id}, amount: {amount} {currency}")

        # Find the payment in our system
        payment = db.query(Payment).filter(
            Payment.razorpay_payment_id == razorpay_payment_id
        ).first()

        if payment:
            # Update payment status
            old_status = payment.status
            # For authorized, we might keep it as ATTEMPTED or create a new status
            # Let's map authorized to ATTEMPTED for now
            payment.status = PaymentStatus.ATTEMPTED
            payment.amount = amount
            payment.currency = currency
            payment.method = method
            payment.bank = bank
            payment.updated_at = datetime.utcnow()

            result["actions_taken"].append({
                "action": "update_payment",
                "details": f"Updated payment {payment.id} status from {old_status} to ATTEMPTED"
            })

            result["success"] = True
            result["payment_id"] = payment.id
            result["amount"] = amount
            result["currency"] = currency

        else:
            logger.warning(f"Payment not found for Razorpay ID: {razorpay_payment_id}")
            result["actions_taken"].append({
                "action": "payment_not_found",
                "details": f"No payment found for Razorpay ID: {razorpay_payment_id}"
            })

        return result

# Singleton instance
payment_event_service = PaymentEventService()

def get_payment_event_service():
    return payment_event_service