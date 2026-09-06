"""
Recovery prediction service for ML-based recovery probability estimation.
"""
import logging
from decimal import Decimal
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime
import pickle
import os
from sqlalchemy.orm import Session
from ..services.recovery_case import get_recovery_case_service
from ..database import SessionLocal
from ..models.recovery_case import RecoveryCase
from ..models.payment import Payment
from ..models.customer import Customer
from ..models.merchant import Merchant
from ..models.failure_diagnosis import FailureDiagnosis
from ..models.recovery_prediction import RecoveryPrediction
from ..models.audit_log import AuditLog
from ..services.timeline import get_timeline_service

logger = logging.getLogger(__name__)

class RecoveryPredictionService:
    def __init__(self):
        from ml.models.recovery_predictor import get_recovery_predictor
        self.predictor = get_recovery_predictor()

    def predict_recovery(self, case_id: int, prediction_mode: str = "ml_model", db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Predict recovery probability for different actions.

        Args:
            case_id: ID of the recovery case
            prediction_mode: Either "heuristic" or "ml_model"
            db: Optional database session

        Returns:
            dict: Prediction results for each action type with probabilities
        """
        logger.info(f"Predicting recovery for case {case_id} in {prediction_mode} mode")

        should_close = False
        if db is None:
            db = SessionLocal()
            should_close = True
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

            failure_diagnosis = db.query(FailureDiagnosis).filter(
                FailureDiagnosis.case_id == case_id
            ).first()

            if not payment or not customer or not merchant:
                raise ValueError("Related entities not found")

            # Initialize prediction result
            prediction_result = {
                "success": False,
                "predictions": {},
                "prediction_mode": prediction_mode,
                "timestamp": datetime.utcnow().isoformat(),
                "details": {},
                "error": None
            }

            # Predict based on mode
            if prediction_mode == "ml_model":
                prediction_result = self._predict_with_ml_model(
                    payment, customer, merchant, failure_diagnosis, prediction_result
                )
            else:
                prediction_result = self._predict_with_heuristics(
                    payment, customer, merchant, failure_diagnosis, prediction_result
                )

            # Save predictions to database
            if prediction_result["success"]:
                db.query(RecoveryPrediction).filter(
                    RecoveryPrediction.case_id == case_id
                ).delete()

                for action_type, pred_data in prediction_result["predictions"].items():
                    recovery_prediction = RecoveryPrediction(
                        case_id=case_id,
                        action_type=action_type,
                        probability=pred_data["probability"],
                        confidence=pred_data.get("confidence", 0.8)
                    )
                    db.add(recovery_prediction)

                best_action = max(
                    prediction_result["predictions"].items(),
                    key=lambda x: x[1]["probability"]
                )
                best_prob = float(best_action[1]["probability"])
                recovery_case.recovery_probability = Decimal(str(round(best_prob, 2)))
                recovery_case.expected_recovery = Decimal(str(round(float(recovery_case.amount) * best_prob, 2)))
                recovery_case.updated_at = datetime.utcnow()

                timeline_service = get_timeline_service()
                timeline_service.add_event_to_timeline(
                    case_id=case_id,
                    actor="prediction_service",
                    action="predict_recovery",
                    input_data={
                        "prediction_mode": prediction_mode
                    },
                    decision_data={
                        "predictions": prediction_result["predictions"],
                        "best_action": best_action[0],
                        "best_probability": best_action[1]["probability"]
                    },
                    db=db
                )

                audit_log = AuditLog(
                    case_id=case_id,
                    actor="prediction_service",
                    action="predict_recovery",
                    input_json=str({
                        "payment_id": payment.id,
                        "prediction_mode": prediction_mode
                    }),
                    decision_json=str({
                        "predictions": prediction_result["predictions"]
                    }),
                    policy_result="predicted"
                )
                db.add(audit_log)

                if should_close:
                    db.commit()
                else:
                    db.flush()

            return prediction_result

        except Exception as e:
            if should_close:
                db.rollback()
            logger.error(f"Error predicting recovery for case {case_id}: {str(e)}")
            return {
                "success": False,
                "predictions": {},
                "prediction_mode": prediction_mode,
                "timestamp": datetime.utcnow().isoformat(),
                "details": {},
                "error": str(e)
            }
        finally:
            if should_close:
                db.close()

    def _predict_with_heuristics(self, payment: Payment, customer: Customer,
                               merchant: Merchant, failure_diagnosis: Optional[FailureDiagnosis],
                               prediction_result: Dict) -> Dict:
        """Predict recovery using heuristic-based approach."""
        # Define the actions we can take
        actions = ["wait", "send_notification", "generate_payment_link", "retry", "escalate", "stop"]

        # Base recovery probability per action type
        base_probabilities = {
            "generate_payment_link": 0.75,
            "retry": 0.55,
            "wait": 0.50,
            "send_notification": 0.40,
            "escalate": 0.15,
            "stop": 0.05
        }

        predictions = {}

        for action in actions:
            prob = base_probabilities.get(action, 0.25)

            # Adjust based on failure category
            if failure_diagnosis:
                failure_category = failure_diagnosis.category

                if action == "retry":
                    if failure_category == "insufficient_funds":
                        prob *= 0.7
                    elif failure_category in ["expired_card", "FAIL_EXPIRED_CARD"]:
                        prob = 0.0
                    elif failure_category == "authentication_failed":
                        prob *= 0.5
                    elif failure_category in ["technical_error", "bank_declined"]:
                        prob *= 0.8
                elif action == "generate_payment_link":
                    if failure_category in ["expired_card", "FAIL_EXPIRED_CARD"]:
                        prob = 0.85
                    elif failure_category in ["insufficient_funds", "authentication_failed"]:
                        prob = 0.75
                    elif failure_category in ["technical_error", "bank_declined"]:
                        prob = 0.80
                elif action == "wait":
                    if failure_category in ["bank_declined", "technical_error"]:
                        prob = 0.70
                    elif failure_category in ["expired_card", "FAIL_EXPIRED_CARD"]:
                        prob = 0.0
                elif action == "escalate":
                    prob = 0.15
                elif action == "stop":
                    prob = 0.05

            # Adjust based on amount
            amount_factor = 1.0
            if payment.amount > 10000:
                amount_factor = 0.85
            elif payment.amount > 5000:
                amount_factor = 0.90

            if action != "escalate":
                prob *= amount_factor

            # Adjust based on customer history
            history_factor = 1.0
            if customer.previous_recoveries > 0:
                history_factor = 1.1
            elif customer.previous_failed_payments > customer.previous_successful_payments:
                history_factor = 0.9

            prob *= history_factor
            prob = max(0.0, min(1.0, prob))

            confidence = 0.7
            if failure_diagnosis and failure_diagnosis.confidence:
                confidence = (confidence + float(failure_diagnosis.confidence)) / 2

            predictions[action] = {
                "probability": round(prob, 3),
                "confidence": round(confidence, 3),
                "reasoning": f"Heuristic prediction based on failure category ({failure_diagnosis.category if failure_diagnosis else 'unknown'}), amount, and history"
            }

        prediction_result["success"] = True
        prediction_result["predictions"] = predictions
        prediction_result["details"]["model_type"] = "heuristic"
        prediction_result["details"]["factors_considered"] = ["failure_category", "amount", "customer_history", "merchant_settings"]

        return prediction_result

    def _predict_with_ml_model(self, payment: Payment, customer: Customer,
                               merchant: Merchant, failure_diagnosis: Optional[FailureDiagnosis],
                               prediction_result: Dict) -> Dict:
        """Predict recovery using trained action-conditioned ML model."""
        context = {
            "amount": float(payment.amount),
            "payment_method": payment.method.value if hasattr(payment.method, "value") else str(payment.method),
            "bank": payment.bank or "HDFC",
            "failure_category": failure_diagnosis.category if failure_diagnosis else "insufficient_funds",
            "merchant_category": "ecommerce",
            "hour": datetime.utcnow().hour,
            "day_of_week": datetime.utcnow().weekday(),
            "retry_count": payment.attempt_count or 0,
            "time_since_failure": 15.0,
            "failure_streak": 1,
            "customer": {
                "tenure_days": customer.tenure_days or 180,
                "previous_successful_payments": customer.previous_successful_payments or 5,
                "previous_failed_payments": customer.previous_failed_payments or 1,
                "previous_recoveries": 1,
            }
        }

        # Query real trained model
        ml_probs = self.predictor.predict_recovery_probabilities(context)

        # Map ML actions to system RecoveryActionType
        mapping = {
            "retry": ml_probs.get("retry_now", {}).get("probability", 0.45),
            "generate_payment_link": ml_probs.get("payment_link", {}).get("probability", 0.70),
            "send_notification": ml_probs.get("notification", {}).get("probability", 0.55),
            "wait": ml_probs.get("wait", {}).get("probability", 0.40),
            "escalate": ml_probs.get("escalate", {}).get("probability", 0.15),
            "stop": 0.05,
        }

        predictions = {}
        for action, prob in mapping.items():
            confidence = 0.85 if self.predictor.is_trained else 0.50
            if failure_diagnosis and failure_diagnosis.confidence:
                confidence = float((float(confidence) + float(failure_diagnosis.confidence)) / 2.0)

            predictions[action] = {
                "probability": round(float(prob), 4),
                "confidence": round(float(confidence), 3),
                "source": "calibrated_ml_model" if self.predictor.is_trained else "fallback_heuristic",
                "reasoning": f"P(recovery|action={action}) estimated by trained ML model"
            }

        prediction_result["success"] = True
        prediction_result["predictions"] = predictions
        prediction_result["details"]["model_type"] = "calibrated_ml_model"
        prediction_result["details"]["is_trained"] = self.predictor.is_trained
        return prediction_result

# Singleton instance
prediction_service = RecoveryPredictionService()

def get_prediction_service():
    return prediction_service