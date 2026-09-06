"""
Independent Verification Service for ReviveAI.
Crucial Architectural Principle: Never blindly trust executor.result.success.
Verification independently validates recovery through:
  1. Provider event audit (payment.captured webhook receipts)
  2. Provider reference validation
  3. Ground-truth state confirmation
On confirmed recovery, records an append-only entry into the RecoveryLedger with strict cost accounting.
"""

import logging
import json
import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models.recovery_case import RecoveryCase, RecoveryCaseStatus
from ..models.payment import Payment, PaymentStatus
from ..models.payment_event import PaymentEvent
from ..models.recovery_action import RecoveryAction, RecoveryActionType, RecoveryActionStatus
from ..models.recovery_ledger import RecoveryLedger
from ..models.audit_log import AuditLog
from ..services.timeline import get_timeline_service

logger = logging.getLogger(__name__)

from ..config import ACTION_COST_MAP, PAYMENT_LINK_COST_INR, get_action_cost


class IndependentVerificationService:
    def calculate_accumulated_action_cost(self, db: Session, case_id: int) -> Decimal:
        """Calculate actual accumulated recovery cost from all executed actions on this case."""
        actions = db.query(RecoveryAction).filter(
            RecoveryAction.case_id == case_id,
            RecoveryAction.status.in_([RecoveryActionStatus.EXECUTED, RecoveryActionStatus.VERIFIED])
        ).all()

        total_cost = Decimal("0.00")
        for act in actions:
            total_cost += get_action_cost(act.action_type)
        return total_cost

    def verify_recovery(
        self,
        case_id: int,
        action_id: Optional[int] = None,
        verification_mode: str = "simulation",
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Independently evaluate whether money was actually recovered into the merchant account.
        Does NOT trust executor.result.success alone.
        """
        logger.info(f"IndependentVerification validating case #{case_id} [mode={verification_mode}]")

        should_close = False
        if db is None:
            db = SessionLocal()
            should_close = True
        try:
            recovery_case = db.query(RecoveryCase).filter(RecoveryCase.id == case_id).first()
            if not recovery_case:
                raise ValueError(f"Recovery case #{case_id} not found")

            payment = db.query(Payment).filter(Payment.id == recovery_case.payment_id).first()
            if not payment:
                raise ValueError(f"Payment for case #{case_id} not found")

            if action_id:
                action = db.query(RecoveryAction).filter(RecoveryAction.id == action_id).first()
            else:
                action = db.query(RecoveryAction).filter(
                    RecoveryAction.case_id == case_id,
                    RecoveryAction.status.in_([RecoveryActionStatus.EXECUTED, RecoveryActionStatus.APPROVED])
                ).order_by(RecoveryAction.executed_at.desc()).first()

            if not action:
                raise ValueError(f"No active or executed action to verify for case #{case_id}")

            verification_result = {
                "success": True,
                "recovered": False,
                "case_id": case_id,
                "action_id": action.id,
                "action_type": action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type),
                "verification_mode": verification_mode,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": {},
            }

            act_type = action.action_type
            if hasattr(act_type, "value"):
                act_type = act_type.value
            act_type_str = str(act_type).lower()

            # 1. Independent Check: Look for incoming payment.captured webhook event
            captured_event = db.query(PaymentEvent).filter(
                PaymentEvent.payment_id == payment.id,
                PaymentEvent.event_type == "payment.captured"
            ).first()

            # Protective actions (STOP, WAIT, ESCALATE) are policy barriers, never revenue recovery events
            if act_type_str in ["escalate", "stop", "wait"]:
                recovered = False
                provider_ref = None
                verification_result["details"] = {
                    "proof_source": "protective_policy_barrier",
                    "action_type": act_type_str,
                    "message": f"Action {act_type_str.upper()} is a protective policy barrier; no recovery attempted or claimed."
                }
            elif captured_event:
                # Confirmed independent proof of payment capture via webhook event
                recovered = True
                provider_ref = captured_event.razorpay_event_id
                verification_result["details"] = {
                    "proof_source": "payment_captured_webhook_event",
                    "provider_reference": provider_ref,
                    "confidence": 1.0,
                }
            elif verification_mode == "simulation":
                # High-fidelity simulation outcome verification
                # Based on failure cause and action efficacy
                recovered = self._verify_simulation_outcome(payment, action, recovery_case)
                provider_ref = f"sim_captured_{uuid.uuid4().hex[:10]}" if recovered else None
                verification_result["details"] = {
                    "proof_source": "controlled_outcome_simulation",
                    "provider_reference": provider_ref,
                    "recovered": recovered,
                }
            else:
                # Live mode without captured event: payment has not yet succeeded
                recovered = False
                provider_ref = None
                verification_result["details"] = {
                    "proof_source": "provider_inquiry",
                    "message": "No confirmed capture event detected from payment provider",
                }

            verification_result["recovered"] = recovered

            # 2. State Mutation and Recovery Ledger Writing
            if recovered:
                # Mark payment and case
                payment.status = PaymentStatus.CAPTURED
                recovery_case.status = RecoveryCaseStatus.RECOVERED
                recovery_case.closed_at = datetime.now(timezone.utc)
                recovery_case.recovered_amount = payment.amount

                action.status = RecoveryActionStatus.VERIFIED
                action.result = json.dumps(verification_result["details"])

                # Cost accounting
                gross_amount = Decimal(str(payment.amount))
                action_cost = self.calculate_accumulated_action_cost(db, case_id)
                net_recovered = gross_amount - action_cost

                # Append-Only Financial Ledger Entry (with duplicate protection)
                existing_ledger = db.query(RecoveryLedger).filter(RecoveryLedger.case_id == case_id).first()
                if not existing_ledger:
                    ledger_entry = RecoveryLedger(
                        case_id=case_id,
                        payment_id=payment.id,
                        gross_amount=gross_amount,
                        action_cost=action_cost,
                        net_recovered=net_recovered,
                        recovery_action=verification_result["action_type"],
                        provider_reference=provider_ref or f"ref_{payment.id}",
                        recovered_at=datetime.now(timezone.utc),
                        details=json.dumps(verification_result["details"]),
                    )
                    db.add(ledger_entry)
                else:
                    ledger_entry = existing_ledger

                verification_result["ledger"] = {
                    "gross_amount": float(gross_amount),
                    "action_cost": float(action_cost),
                    "net_recovered": float(net_recovered),
                    "provider_reference": ledger_entry.provider_reference,
                }

                # Audit Log & Timeline
                timeline_service = get_timeline_service()
                timeline_service.add_event_to_timeline(
                    case_id=case_id,
                    actor="IndependentVerification",
                    action="VERIFY_RECOVERY_SUCCESS",
                    input_data={"action_id": action.id, "mode": verification_mode},
                    decision_data=verification_result,
                    db=db,
                )

                audit_log = AuditLog(
                    case_id=case_id,
                    actor="IndependentVerification",
                    action="VERIFY_RECOVERY_SUCCESS",
                    input_json=json.dumps({"action_id": action.id, "mode": verification_mode}),
                    decision_json=json.dumps(verification_result["ledger"]),
                    policy_result="RECOVERED",
                )
                db.add(audit_log)

            else:
                # Verification confirmed no automated fund capture (e.g. wait, stop, escalate, or unrecovered)
                # If action was EXECUTED by bounded executor, preserve EXECUTED status rather than falsely marking DENIED
                if action.status != RecoveryActionStatus.EXECUTED:
                    action.status = RecoveryActionStatus.DENIED
                action.result = json.dumps(verification_result["details"])

                act_type_str = action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type).lower()
                if act_type_str == "stop":
                    unresolved_action_name = "VERIFY_CUSTOMER_PROTECTED"
                    msg = "Zero harassment guardrail verified. No further action taken."
                elif act_type_str == "wait":
                    unresolved_action_name = "VERIFY_RECOVERY_DEFERRED"
                    msg = "Recovery attempt deferred due to bank outage or degradation."
                elif act_type_str == "escalate":
                    unresolved_action_name = "VERIFY_ESCALATION_STATUS"
                    msg = "Verification Status: Pending Human Resolution. Handed off to human ops; no automated recovery recorded."
                else:
                    unresolved_action_name = "VERIFY_RECOVERY_UNRESOLVED"
                    msg = "Action did not achieve verified fund capture. Escalated or pending replanning."

                timeline_service = get_timeline_service()
                timeline_service.add_event_to_timeline(
                    case_id=case_id,
                    actor="IndependentVerification",
                    action=unresolved_action_name,
                    input_data={"action_id": action.id, "mode": verification_mode},
                    decision_data={"message": msg},
                    db=db,
                )

            if should_close:
                db.commit()
            else:
                db.flush()
            return verification_result

        except Exception as e:
            db.rollback()
            logger.error(f"Verification error on case #{case_id}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "recovered": False,
                "error": str(e),
                "case_id": case_id,
            }
        finally:
            if should_close:
                db.close()

    def _verify_simulation_outcome(self, payment: Payment, action: RecoveryAction, case: RecoveryCase) -> bool:
        """Deterministic simulation outcome matching probability of action effectiveness."""
        act_type = action.action_type
        if hasattr(act_type, "value"):
            act_type = act_type.value
        act_type_str = str(act_type).lower()

        err_code = str(payment.error_code or "").upper()

        if act_type_str in ["escalate", "stop", "wait"]:
            return False

        # If expired card, retry definitely fails (0% chance); payment_link succeeds
        if err_code in ["CARD_EXPIRED", "FAIL_EXPIRED_CARD"]:
            return act_type_str in ["generate_payment_link", "payment_link"]

        # If bank outage / technical error, retrying immediately fails; waiting or payment link succeeds
        if err_code in ["BANK_GATEWAY_TIMEOUT", "05", "FAIL_BANK_DECLINED", "FAIL_TECHNICAL_ERROR"]:
            return act_type_str in ["wait", "retry", "generate_payment_link", "payment_link"]

        # Insufficient funds or authentication or transaction_not_allowed: payment link or retry recovers
        if act_type_str in ["retry", "generate_payment_link", "payment_link", "send_notification", "wait"]:
            return True

        return False


verification_service = IndependentVerificationService()


def get_verification_service() -> IndependentVerificationService:
    return verification_service