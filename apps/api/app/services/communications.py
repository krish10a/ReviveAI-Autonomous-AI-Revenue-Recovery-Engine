"""
Communications service for sending notifications to customers.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from ..services.recovery_case import get_recovery_case_service
from ..database import SessionLocal
from ..models.recovery_case import RecoveryCase
from ..models.payment import Payment
from ..models.customer import Customer
from ..models.merchant import Merchant
from ..models.communication import Communication
from ..models.audit_log import AuditLog
from ..services.timeline import get_timeline_service

logger = logging.getLogger(__name__)

class CommunicationsService:
    def send_notification(self, case_id: int, channel: str = "email",
                         template: str = "payment_recovery", language: str = "en") -> Dict[str, Any]:
        """
        Send a notification to the customer about payment recovery.

        Args:
            case_id: ID of the recovery case
            channel: Communication channel (email, sms, whatsapp, etc.)
            template: Template to use for the notification
            language: Language for the notification

        Returns:
            dict: Result of the notification sending
        """
        logger.info(f"Sending {channel} notification for case {case_id} using {template} template")

        db = SessionLocal()
        try:
            # Get the recovery case
            recovery_case = db.query(RecoveryCase).filter(
                RecoveryCase.id == case_id
            ).first()

            if not recovery_case:
                raise ValueError(f"Recovery case {case_id} not found")

            # Get related entities
            payment = db.query(Payment).filter(
                Payment.id == recovery_case.payment_id
            ).first()

            customer = db.query(Customer).filter(
                Customer.id == recovery_case.customer_id
            ).first()

            merchant = db.query(Merchant).filter(
                Merchant.id == recovery_case.merchant_id
            ).first()

            if not payment or not customer or not merchant:
                raise ValueError("Related entities not found")

            # Check if customer has opted out
            if customer.opted_out:
                return {
                    "success": False,
                    "channel": channel,
                    "template": template,
                    "language": language,
                    "timestamp": datetime.utcnow().isoformat(),
                    "details": {},
                    "error": "Customer has opted out of recovery communications"
                }

            # Initialize notification result
            notification_result = {
                "success": False,
                "channel": channel,
                "template": template,
                "language": language,
                "timestamp": datetime.utcnow().isoformat(),
                "details": {},
                "error": None
            }

            # Send notification based on channel
            if channel == "email":
                notification_result = self._send_email_notification(
                    payment, customer, merchant, notification_result, template, language
                )
            elif channel == "sms":
                notification_result = self._send_sms_notification(
                    payment, customer, merchant, notification_result, template, language
                )
            elif channel == "whatsapp":
                notification_result = self._send_whatsapp_notification(
                    payment, customer, merchant, notification_result, template, language
                )
            else:
                # Generic notification fallback
                notification_result = self._send_generic_notification(
                    payment, customer, merchant, notification_result, channel, template, language
                )

            # If successful, save the communication record
            if notification_result["success"]:
                communication = Communication(
                    case_id=case_id,
                    channel=channel,
                    template=template,
                    language=language,
                    subject=notification_result["details"].get("subject"),
                    body=notification_result["details"].get("body"),
                    status="sent",
                    sent_at=datetime.utcnow()
                )
                db.add(communication)

                # Record in timeline
                timeline_service = get_timeline_service()
                timeline_service.add_event_to_timeline(
                    case_id=case_id,
                    actor="communications_service",
                    action=f"send_{channel}_notification",
                    input_data={
                        "template": template,
                        "language": language
                    },
                    decision_data={
                        "success": True,
                        "details": notification_result["details"]
                    }
                )

                # Create audit log
                audit_log = AuditLog(
                    case_id=case_id,
                    actor="communications_service",
                    action=f"send_{channel}_notification",
                    input_json=str({
                        "template": template,
                        "language": language,
                        "channel": channel
                    }),
                    decision_json=str(notification_result["details"]),
                    policy_result="sent"
                )
                db.add(audit_log)

                db.commit()

            return notification_result

        except Exception as e:
            db.rollback()
            logger.error(f"Error sending notification for case {case_id}: {str(e)}")
            return {
                "success": False,
                "channel": channel,
                "template": template,
                "language": language,
                "timestamp": datetime.utcnow().isoformat(),
                "details": {},
                "error": str(e)
            }
        finally:
            db.close()

    def _send_email_notification(self, payment: Payment, customer: Customer,
                               merchant: Merchant, notification_result: Dict,
                               template: str, language: str) -> Dict:
        """Send email notification (simulated)."""
        # In a real implementation, this would:
        # 1. Render an email template with customer and payment details
        # 2. Send via an email service (SendGrid, SES, etc.)
        # 3. Handle bounces and delivery receipts

        # For now, we'll simulate it
        subject = f"Payment Recovery Assistance - {merchant.name}"
        body = f"""
        Dear {customer.name},

        We noticed that your recent payment of {payment.amount} {payment.currency} to {merchant.name} was not successful.

        To help you complete this payment, we've generated a secure payment link:
        https://pay.merchant.com/recover/{payment.id}

        This link will expire in 24 hours. If you need assistance, please contact our support team.

        Best regards,
        The {merchant.name} Team
        """.strip()

        notification_result["success"] = True
        notification_result["details"]["subject"] = subject
        notification_result["details"]["body"] = body
        notification_result["details"]["message_id"] = f"email_{datetime.utcnow().timestamp()}"
        notification_result["details"]["delivery_status"] = "sent"
        notification_result["details"]["message"] = "Email notification sent successfully (simulation)"

        return notification_result

    def _send_sms_notification(self, payment: Payment, customer: Customer,
                              merchant: Merchant, notification_result: Dict,
                              template: str, language: str) -> Dict:
        """Send SMS notification (simulated)."""
        # In a real implementation, this would:
        # 1. Format an SMS message with customer and payment details
        # 2. Send via an SMS service (Twilio, etc.)
        # 3. Handle delivery receipts

        # For now, we'll simulate it
        message = f"Hi {customer.name}, your payment of {payment.amount} {payment.currency} to {merchant.name} failed. Pay now: https://pay.merchant.com/recover/{payment.id}"

        notification_result["success"] = True
        notification_result["details"]["message"] = message
        notification_result["details"]["message_id"] = f"sms_{datetime.utcnow().timestamp()}"
        notification_result["details"]["delivery_status"] = "sent"
        notification_result["details"]["message"] = "SMS notification sent successfully (simulation)"

        return notification_result

    def _send_whatsapp_notification(self, payment: Payment, customer: Customer,
                                   merchant: Merchant, notification_result: Dict,
                                   template: str, language: str) -> Dict:
        """Send WhatsApp notification (simulated)."""
        # In a real implementation, this would:
        # 1. Format a WhatsApp message with customer and payment details
        # 2. Send via WhatsApp Business API
        # 3. Handle delivery and read receipts

        # For now, we'll simulate it
        message = f"Hello {customer.name}! Your payment of {payment.amount} {payment.currency} to {merchant.name} needs completion. Secure link: https://pay.merchant.com/recover/{payment.id} (valid 24h)"

        notification_result["success"] = True
        notification_result["details"]["message"] = message
        notification_result["details"]["message_id"] = f"whatsapp_{datetime.utcnow().timestamp()}"
        notification_result["details"]["delivery_status"] = "sent"
        notification_result["details"]["message"] = "WhatsApp notification sent successfully (simulation)"

        return notification_result

    def _send_generic_notification(self, payment: Payment, customer: Customer,
                                  merchant: Merchant, notification_result: Dict,
                                  channel: str, template: str, language: str) -> Dict:
        """Send generic notification (simulated)."""
        # Fallback for other channels
        notification_result["success"] = True
        notification_result["details"]["channel"] = channel
        notification_result["details"]["message"] = f"{channel} notification sent for payment {payment.id} (simulation)"
        notification_result["details"]["message_id"] = f"{channel}_{datetime.utcnow().timestamp()}"

        return notification_result

# Singleton instance
communications_service = CommunicationsService()

def get_communications_service():
    return communications_service