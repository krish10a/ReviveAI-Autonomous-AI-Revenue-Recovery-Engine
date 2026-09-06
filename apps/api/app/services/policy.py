"""
Policy engine service for ReviveAI.
Acts as the strict, impassable hard barrier between AI proposals and execution.
Enforces business rules, risk governance, customer protection, and bank health checks.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import SessionLocal
from ..models.recovery_case import RecoveryCase, RecoveryCaseStatus
from ..models.payment import Payment, PaymentStatus
from ..models.customer import Customer
from ..models.merchant import Merchant
from ..models.policy_decision import PolicyDecision, PolicyDecisionResult
from ..models.recovery_action import RecoveryAction, RecoveryActionType
from ..models.communication import Communication
from ..config import is_quiet_hours, QUIET_HOURS_START_HOUR, QUIET_HOURS_END_HOUR
from ..services.timeline import get_timeline_service

logger = logging.getLogger(__name__)


class PolicyEngineService:
    def check_bank_health(self, db: Session, bank_name: Optional[str]) -> Dict[str, Any]:
        """Check bank health based on rolling window failure rate."""
        if not bank_name:
            return {"status": "HEALTHY", "failure_rate": 0.0}

        # Look back 15 minutes
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
        payments = db.query(Payment).filter(
            Payment.bank == bank_name,
            Payment.created_at >= cutoff
        ).all()

        total = len(payments)
        if total < 3:
            # Check if current payment specifically has an outage code
            return {"status": "HEALTHY", "failure_rate": 0.0, "total_events": total}

        failed_count = sum(1 for p in payments if p.status == PaymentStatus.FAILED)
        failure_rate = failed_count / total

        # Degradation threshold: 30% failure rate indicates severe bank gateway distress
        is_degraded = failure_rate >= 0.30
        return {
            "status": "DEGRADED" if is_degraded else "HEALTHY",
            "failure_rate": round(failure_rate, 3),
            "total_events": total,
        }

    def evaluate_action(
        self,
        case_id: int,
        action: RecoveryAction,
        merchant: Merchant,
        eval_time: Optional[datetime] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate proposed recovery action against exhaustive business guardrails.
        Hard barrier: If denied, action MUST NOT be executable by the executor.
        """
        action_type_str = action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type).lower()
        logger.info(f"PolicyEngine evaluating action '{action_type_str}' for case #{case_id}")

        should_close = False
        if db is None:
            db = SessionLocal()
            should_close = True
        try:
            recovery_case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
            if not recovery_case:
                raise ValueError(f"Recovery case {case_id} not found")

            payment = db.query(Payment).filter(Payment.id == recovery_case.payment_id).first()
            customer = db.query(Customer).filter(Customer.id == recovery_case.customer_id).first()
            if not payment or not customer:
                raise ValueError(f"Incomplete relational context for case {case_id}")

            rule_violations = []
            denial_reasons = []

            # Guardrail 1: Recovery Case Expiry / Closed state or Already Captured Payment
            if payment.status in [PaymentStatus.CAPTURED, "captured"]:
                rule_violations.append("already_captured")
                denial_reasons.append("Payment is already captured")
            elif recovery_case.status in [RecoveryCaseStatus.EXPIRED, RecoveryCaseStatus.RECOVERED, RecoveryCaseStatus.STOPPED]:
                rule_violations.append("case_already_closed")
                denial_reasons.append("Recovery case is already closed or expired")

            # Guardrail 2: Customer Hard Opt-Out
            contact_actions = ["send_notification", "generate_payment_link", "notification", "payment_link"]
            if customer.opted_out:
                rule_violations.append("customer_opt_out")
                denial_reasons.append("Customer has strictly opted out of automated recovery interactions")

            # Guardrail 3: Maximum Retry Attempt Exhaustion
            retry_actions = ["retry", "retry_now", "retry_later"]
            if action_type_str in retry_actions:
                max_retries = merchant.max_retries or 3
                if (recovery_case.attempt_count or 0) >= max_retries:
                    rule_violations.append("max_retries_exceeded")
                    denial_reasons.append(f"Maximum allowed retries ({max_retries}) already reached")

            # Guardrail 4: Night Contact Quiet Hours Window (21:00 to 08:00)
            if action_type_str in contact_actions:
                current_dt = eval_time if eval_time is not None else datetime.now()
                if is_quiet_hours(current_dt):
                    rule_violations.append("night_contact_window")
                    denial_reasons.append(
                        f"Current time ({current_dt.hour:02d}:{current_dt.minute:02d}) is within quiet hours (21:00-08:00)"
                    )

            # Guardrail 5: Merchant Automated Amount Ceiling
            ceiling = Decimal(str(merchant.max_automated_amount or 10000.00))
            if action_type_str in retry_actions + ["send_notification"]:
                if Decimal(str(recovery_case.amount)) > ceiling:
                    rule_violations.append("merchant_amount_ceiling")
                    denial_reasons.append(f"Amount ₹{recovery_case.amount} exceeds automated ceiling of ₹{ceiling}; requires manual human escalation")

            # Guardrail 6: Bank Outage & Degradation Detection
            if action_type_str in retry_actions:
                bank_health = self.check_bank_health(db, payment.bank)
                has_outage_code = payment.error_code in ["BANK_GATEWAY_TIMEOUT", "05", "BANK_OUTAGE"]
                if bank_health["status"] == "DEGRADED" or has_outage_code:
                    rule_violations.append("bank_outage_detected")
                    denial_reasons.append(f"Bank degradation detected for {payment.bank} (rolling failure rate {bank_health['failure_rate']*100:.0f}%). Retries blocked; policy dictates WAIT.")

            # Guardrail 7: Communication Cooldown Window
            if action_type_str in contact_actions:
                cooldown_hrs = merchant.message_cooldown_hours or 2
                recent_comm = db.query(Communication).filter(
                    Communication.customer_id == customer.id,
                    Communication.sent_at >= datetime.now(timezone.utc) - timedelta(hours=cooldown_hrs)
                ).first()
                if recent_comm:
                    rule_violations.append("communication_cooldown")
                    denial_reasons.append(f"Customer was contacted within cooldown period ({cooldown_hrs} hours)")

            # Guardrail 8: Case Expiry
            expiry_hrs = merchant.case_expiry_hours or 48
            if recovery_case.created_at:
                c_time = recovery_case.created_at.replace(tzinfo=None)
                if (datetime.utcnow() - c_time).total_seconds() / 3600 > expiry_hrs:
                    rule_violations.append("case_expired")
                    denial_reasons.append(f"Case exceeded expiry horizon of {expiry_hrs} hours")

            # Final Policy Outcome
            allowed = len(rule_violations) == 0
            primary_reason = denial_reasons[0] if denial_reasons else "All policy guardrails verified"

            if not hasattr(action, "id") or not action.id:
                db.add(action)
                db.flush()

            policy_decision = PolicyDecision(
                case_id=case_id,
                action_id=action.id,
                rule_name=";".join(rule_violations) if rule_violations else "policy_pass",
                result=PolicyDecisionResult.ALLOWED if allowed else PolicyDecisionResult.DENIED,
                reason=primary_reason,
            )
            db.add(policy_decision)

            timeline_service = get_timeline_service()
            timeline_service.add_event_to_timeline(
                case_id=case_id,
                actor="ReviveAI::PolicyEngine",
                action="EVALUATE_POLICY",
                input_data={
                    "scenario": recovery_case.scenario_key,
                    "action": action_type_str,
                    "amount": float(recovery_case.amount),
                },
                decision_data={
                    "result": "ALLOWED" if allowed else "DENIED",
                    "reason": primary_reason,
                    "rule_violations": rule_violations,
                },
                db=db,
            )
            if should_close:
                db.commit()
            else:
                db.flush()

            fallback_action = "wait" if "bank_outage_detected" in rule_violations else ("stop" if "already_captured" in rule_violations or "customer_opt_out" in rule_violations else "escalate")

            return {
                "allowed": allowed,
                "denied_reason": primary_reason if not allowed else None,
                "rule_violations": rule_violations,
                "fallback_recommended_action": fallback_action,
                "policy_decision_id": policy_decision.id,
            }

        except Exception as e:
            if should_close:
                db.rollback()
            logger.error(f"Policy evaluation error for case #{case_id}: {str(e)}", exc_info=True)
            raise
        finally:
            if should_close:
                db.close()


policy_engine_service = PolicyEngineService()


def get_policy_engine_service() -> PolicyEngineService:
    return policy_engine_service