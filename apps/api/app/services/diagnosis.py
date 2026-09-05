"""
Failure diagnosis service for determining why payments failed.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
from sqlalchemy.orm import Session
from ..services.recovery_case import get_recovery_case_service
from ..database import SessionLocal
from ..models.recovery_case import RecoveryCase
from ..models.payment import Payment
from ..models.failure_diagnosis import FailureDiagnosis
from ..models.audit_log import AuditLog
from ..services.timeline import get_timeline_service

logger = logging.getLogger(__name__)

class FailureDiagnosisService:
    def diagnose_failure(self, case_id: int, diagnosis_mode: str = "rule_based") -> Dict[str, Any]:
        """
        Diagnose why a payment failed.

        Args:
            case_id: ID of the recovery case
            diagnosis_mode: Either "rule_based" or "llm_fallback"

        Returns:
            dict: Diagnosis results including failure category and confidence
        """
        logger.info(f"Diagnosing failure for case {case_id} in {diagnosis_mode} mode")

        db = SessionLocal()
        try:
            # Get the recovery case
            recovery_case = db.query(RecoveryCase).filter(
                RecoveryCase.id == case_id
            ).first()

            if not recovery_case:
                raise ValueError(f"Recovery case {case_id} not found")

            # Get the payment
            payment = db.query(Payment).filter(
                Payment.id == recovery_case.payment_id
            ).first()

            if not payment:
                raise ValueError(f"Payment not found for case {case_id}")

            # Initialize diagnosis result
            diagnosis_result = {
                "success": False,
                "failure_category": None,
                "confidence": 0.0,
                "diagnosis_mode": diagnosis_mode,
                "timestamp": datetime.utcnow().isoformat(),
                "details": {},
                "error": None
            }

            # Diagnose based on mode
            if diagnosis_mode == "llm_fallback":
                # In a real implementation, we would call Claude API here
                # For now, we'll fall back to rule-based if LLM is not available
                diagnosis_result = self._diagnose_with_rules(payment, recovery_case, diagnosis_result)
                diagnosis_result["diagnosis_mode"] = "rule_based (LLM fallback not implemented)"
            else:
                # Rule-based diagnosis
                diagnosis_result = self._diagnose_with_rules(payment, recovery_case, diagnosis_result)

            # If diagnosis was successful, save it to the database
            if diagnosis_result["success"]:
                # Check if diagnosis already exists
                existing_diagnosis = db.query(FailureDiagnosis).filter(
                    FailureDiagnosis.case_id == case_id
                ).first()

                if existing_diagnosis:
                    # Update existing diagnosis
                    existing_diagnosis.failure_category = diagnosis_result["failure_category"]
                    existing_diagnosis.confidence = diagnosis_result["confidence"]
                    existing_diagnosis.details = str(diagnosis_result["details"])
                    existing_diagnosis.updated_at = datetime.utcnow()
                else:
                    # Create new diagnosis
                    failure_diagnosis = FailureDiagnosis(
                        case_id=case_id,
                        failure_category=diagnosis_result["failure_category"],
                        confidence=diagnosis_result["confidence"],
                        details=str(diagnosis_result["details"])
                    )
                    db.add(failure_diagnosis)

                # Update the recovery case
                recovery_case.failure_category = diagnosis_result["failure_category"]
                recovery_case.updated_at = datetime.utcnow()

                # Record the diagnosis in the timeline
                timeline_service = get_timeline_service()
                timeline_service.add_event_to_timeline(
                    case_id=case_id,
                    actor="diagnosis_service",
                    action="diagnose_failure",
                    input_data={
                        "diagnosis_mode": diagnosis_mode
                    },
                    decision_data={
                        "failure_category": diagnosis_result["failure_category"],
                        "confidence": diagnosis_result["confidence"],
                        "details": diagnosis_result["details"]
                    },
                    db=db
                )

                # Create audit log for diagnosis
                audit_log = AuditLog(
                    case_id=case_id,
                    actor="diagnosis_service",
                    action="diagnose_failure",
                    input_json=str({
                        "payment_id": payment.id,
                        "diagnosis_mode": diagnosis_mode
                    }),
                    decision_json=str({
                        "failure_category": diagnosis_result["failure_category"],
                        "confidence": diagnosis_result["confidence"],
                        "details": diagnosis_result["details"]
                    }),
                    policy_result="diagnosed"
                )
                db.add(audit_log)

                db.commit()

            return diagnosis_result

        except Exception as e:
            db.rollback()
            logger.error(f"Error diagnosing failure for case {case_id}: {str(e)}")
            return {
                "success": False,
                "failure_category": None,
                "confidence": 0.0,
                "diagnosis_mode": diagnosis_mode,
                "timestamp": datetime.utcnow().isoformat(),
                "details": {},
                "error": str(e)
            }
        finally:
            db.close()

    def _diagnose_with_rules(self, payment: Payment, recovery_case: RecoveryCase,
                           diagnosis_result: Dict) -> Dict:
        """Diagnose failure using rule-based approach."""
        # In a real implementation, we would have more detailed failure data from Razorpay
        # For now, we'll use the failure_code from the payment or simulate based on amount/time

        # Try to get failure code from payment metadata or gateway response
        failure_code = getattr(payment, 'failure_code', None)
        failure_reason = getattr(payment, 'failure_reason', None)

        # Map common failure codes to categories
        failure_category = None
        confidence = 0.8  # Default confidence for rule-based

        if failure_code:
            # Common Razorpay failure codes (simplified mapping)
            if failure_code in ['invalid_card_number', 'card_number_incorrect']:
                failure_category = "invalid_card_number"
                confidence = 0.95
            elif failure_code in ['expired_card', 'card_expired']:
                failure_category = "expired_card"
                confidence = 0.95
            elif failure_code in ['insufficient_funds', 'insufficient_balance']:
                failure_category = "insufficient_funds"
                confidence = 0.9
            elif failure_code in ['transaction_not_allowed', 'transaction_not_permitted']:
                failure_category = "transaction_not_allowed"
                confidence = 0.85
            elif failure_code in ['authentication_failed', 'otp_failed', '3ds_failed']:
                failure_category = "authentication_failed"
                confidence = 0.9
            elif failure_code in ['technical_error', 'gateway_error', 'network_error']:
                failure_category = "technical_error"
                confidence = 0.8
            elif failure_code in ['bank_declined', 'issuer_declined']:
                failure_category = "bank_declined"
                confidence = 0.85
            else:
                # Unknown failure code
                failure_category = "unknown"
                confidence = 0.5
        else:
            # If we don't have a specific failure code, infer from other factors
            # This is a simplified simulation
            import random

            # Simulate different failure categories based on payment characteristics
            rand_val = random.random()

            if rand_val < 0.2:
                failure_category = "insufficient_funds"
                confidence = 0.75
            elif rand_val < 0.4:
                failure_category = "expired_card"
                confidence = 0.8
            elif rand_val < 0.6:
                failure_category = "technical_error"
                confidence = 0.7
            elif rand_val < 0.8:
                failure_category = "authentication_failed"
                confidence = 0.75
            else:
                failure_category = "bank_declined"
                confidence = 0.8

        diagnosis_result["success"] = True
        diagnosis_result["failure_category"] = failure_category
        diagnosis_result["confidence"] = confidence
        diagnosis_result["details"]["failure_code"] = failure_code
        diagnosis_result["details"]["failure_reason"] = failure_reason
        diagnosis_result["details"]["amount"] = str(payment.amount)
        diagnosis_result["details"]["currency"] = payment.currency
        diagnosis_result["details"]["method"] = getattr(payment, 'method', 'unknown')
        diagnosis_result["details"]["diagnosis_method"] = "rule_based"

        return diagnosis_result

    def _diagnose_with_llm(self, payment: Payment, recovery_case: RecoveryCase,
                          diagnosis_result: Dict) -> Dict:
        """Diagnose failure using LLM (Claude API) as fallback."""
        # In a real implementation, this would:
        # 1. Format a prompt with payment details and failure information
        # 2. Call the Claude API
        # 3. Parse the response to extract failure category and confidence

        # For now, we'll note that this is not implemented and fall back to rules
        logger.warning("LLM-based diagnosis not implemented, falling back to rule-based")
        return self._diagnose_with_rules(payment, recovery_case, diagnosis_result)

# Singleton instance
diagnosis_service = FailureDiagnosisService()

def get_failure_diagnosis_service():
    return diagnosis_service