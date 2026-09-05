"""
Recovery case service for managing recovery cases
"""
import logging
from sqlalchemy.orm import Session
from ..models.recovery_case import RecoveryCase, RecoveryCaseStatus
from ..models.payment import Payment
from ..database import SessionLocal

logger = logging.getLogger(__name__)

class RecoveryCaseService:
    def create_recovery_case_from_payment(self, payment_id: int) -> RecoveryCase:
        """
        Create a recovery case from a failed payment
        """
        db = SessionLocal()
        try:
            # Get the payment
            payment = db.query(Payment).filter(Payment.id == payment_id).first()
            if not payment:
                raise ValueError(f"Payment with ID {payment_id} not found")

            # Check if recovery case already exists
            existing_case = db.query(RecoveryCase).filter(
                RecoveryCase.payment_id == payment_id
            ).first()

            if existing_case:
                logger.info(f"Recovery case already exists for payment {payment_id}")
                return existing_case

            # Create new recovery case
            recovery_case = RecoveryCase(
                payment_id=payment_id,
                amount=payment.amount,
                currency=payment.currency,
                status=RecoveryCaseStatus.OPEN
            )

            db.add(recovery_case)
            db.commit()
            db.refresh(recovery_case)

            logger.info(f"Created recovery case {recovery_case.id} for payment {payment_id}")
            return recovery_case

        except Exception as e:
            db.rollback()
            logger.error(f"Error creating recovery case: {str(e)}")
            raise
        finally:
            db.close()

    def get_recovery_case(self, case_id: int) -> RecoveryCase:
        """
        Get a recovery case by ID
        """
        db = SessionLocal()
        try:
            recovery_case = db.query(RecoveryCase).filter(
                RecoveryCase.id == case_id
            ).first()
            return recovery_case
        finally:
            db.close()

    def update_recovery_case_status(self, case_id: int, status: RecoveryCaseStatus) -> RecoveryCase:
        """
        Update the status of a recovery case
        """
        db = SessionLocal()
        try:
            recovery_case = db.query(RecoveryCase).filter(
                RecoveryCase.id == case_id
            ).first()

            if not recovery_case:
                raise ValueError(f"Recovery case with ID {case_id} not found")

            recovery_case.status = status
            if status in [RecoveryCaseStatus.RECOVERED, RecoveryCaseStatus.STOPPED, RecoveryCaseStatus.EXPIRED]:
                from datetime import datetime
                recovery_case.closed_at = datetime.utcnow()

            db.commit()
            db.refresh(recovery_case)

            logger.info(f"Updated recovery case {case_id} status to {status}")
            return recovery_case

        except Exception as e:
            db.rollback()
            logger.error(f"Error updating recovery case status: {str(e)}")
            raise
        finally:
            db.close()

    def update_recovered_amount(self, case_id: int, amount: float) -> RecoveryCase:
        """
        Update the recovered amount for a recovery case
        """
        db = SessionLocal()
        try:
            recovery_case = db.query(RecoveryCase).filter(
                RecoveryCase.id == case_id
            ).first()

            if not recovery_case:
                raise ValueError(f"Recovery case with ID {case_id} not found")

            recovery_case.recovered_amount = amount
            recovery_case.updated_at = datetime.utcnow()

            db.commit()
            db.refresh(recovery_case)

            logger.info(f"Updated recovery case {case_id} recovered amount to {amount}")
            return recovery_case

        except Exception as e:
            db.rollback()
            logger.error(f"Error updating recovered amount: {str(e)}")
            raise
        finally:
            db.close()

# Singleton instance
recovery_case_service = RecoveryCaseService()

def get_recovery_case_service():
    return recovery_case_service
