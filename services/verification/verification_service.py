"""
Verification service for confirming recovery outcomes
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..services.recovery_case import get_recovery_case_service
from ..services.timeline import get_timeline_service
from ..database import SessionLocal
from ..models.recovery_case import RecoveryCase, RecoveryCaseStatus
from ..models.payment import Payment

logger = logging.getLogger(__name__)

class VerificationService:
    def verify_action_outcome(self, case_id: int, action_id: int) -> Dict[str, Any]:
        """
        Verify whether a recovery action actually resulted in money recovery
        """
        logger.info(f"Verifying outcome of action {action_id} for case {case_id}")
        
        db = SessionLocal()
        try:
            # Get the recovery case
            recovery_case = db.query(RecoveryCase).filter(
                RecoveryCase.id == case_id
            ).first()
            
            if not recovery_case:
                raise ValueError(f"Recovery case {case_id} not found")
            
            # In a real system, we would:
            # 1. Check for payment.captured webhook from Razorpay
            # 2. Poll Razorpay API for payment status
            # 3. Check bank settlement reports
            # 4. Verify with merchant's internal systems
            
            # For simulation, we'll check if payment status changed to captured
            payment = db.query(Payment).filter(
                Payment.id == recovery_case.payment_id
            ).first()
            
            if payment and payment.status == "captured":
                # Payment was successfully captured
                recovery_case.status = RecoveryCaseStatus.RECOVERED
                recovery_case.closed_at = datetime.utcnow()
                db.commit()
                
                # Record verification success in timeline
                timeline_service = get_timeline_service()
                timeline_service.add_event_to_timeline(
                    case_id=case_id,
                    agent="verification_service",
                    action="payment_verification",
                    input_data={"action_id": action_id, "payment_id": payment.id},
                    decision_data={
                        "verified": True,
                        "method": "payment_status_check",
                        "amount_recovered": float(recovery_case.amount)
                    }
                )
                
                logger.info(f"Payment verified as captured for case {case_id}")
                return {
                    "verified": True,
                    "amount_recovered": float(recovery_case.amount),
                    "verification_method": "payment_status_check",
                    "verified_at": datetime.utcnow().isoformat()
                }
            else:
                # Payment not captured yet
                # Record verification failure in timeline
                timeline_service = get_timeline_service()
                timeline_service.add_event_to_timeline(
                    case_id=case_id,
                    agent="verification_service",
                    action="payment_verification",
                    input_data={"action_id": action_id, "payment_id": payment.id if payment else None},
                    decision_data={
                        "verified": False,
                        "method": "payment_status_check",
                        "reason": "Payment not yet captured"
                    }
                )
                
                logger.info(f"Payment not yet captured for case {case_id}")
                return {
                    "verified": False,
                    "amount_recovered": 0,
                    "verification_method": "payment_status_check",
                    "verified_at": datetime.utcnow().isoformat(),
                    "reason": "Payment not yet captured"
                }
                
        except Exception as e:
            db.rollback()
            logger.error(f"Error verifying action outcome: {str(e)}")
            raise
        finally:
            db.close()
    
    def verify_case_outcome(self, case_id: int) -> Dict[str, Any]:
        """
        Verify the final outcome of a recovery case
        """
        logger.info(f"Verifying final outcome for case {case_id}")
        
        db = SessionLocal()
        try:
            recovery_case = db.query(RecoveryCase).filter(
                RecoveryCase.id == case_id
            ).first()
            
            if not recovery_case:
                raise ValueError(f"Recovery case {case_id} not found")
            
            is_recovered = recovery_case.status == RecoveryCaseStatus.RECOVERED
            
            return {
                "case_id": case_id,
                "is_recovered": is_recovered,
                "amount": float(recovery_case.amount) if is_recovered else 0,
                "currency": recovery_case.currency,
                "status": recovery_case.status.value,
                "attempt_count": recovery_case.attempt_count,
                "closed_at": recovery_case.closed_at.isoformat() if recovery_case.closed_at else None
            }
            
        finally:
            db.close()

# Singleton instance
verification_service = VerificationService()

def get_verification_service():
    return verification_service
