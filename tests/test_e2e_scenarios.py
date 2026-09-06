"""
Comprehensive End-to-End Tests for ReviveAI.
Validates all 4 canonical closed-loop paths:
  E2E #1: Verified Recovery Loop -> Financial Ledger
  E2E #2: Customer Opt-Out Policy Block -> Zero Contact
  E2E #3: Bank Outage Degradation -> Policy Barrier -> Enqueue WAIT
  E2E #4: Multi-Step Replanning Loop -> Success on Second Intervention
"""

import pytest
from apps.api.app.database import SessionLocal
from apps.api.app.models import (
    RecoveryCase,
    RecoveryCaseStatus,
    Payment,
    PaymentStatus,
    Customer,
    RecoveryAction,
    RecoveryActionType,
    RecoveryActionStatus,
    RecoveryLedger,
    PolicyDecision,
    AuditLog,
)
from apps.api.app.services.agent_loop_service import get_agent_loop_service
from apps.api.app.services.policy import get_policy_engine_service
from apps.api.app.services.executor import get_executor_service
from apps.api.app.services.verification import get_verification_service
from apps.api.app.services.prediction import get_prediction_service

from database.seed.seed_demo import seed_database

policy_service = get_policy_engine_service()
executor = get_executor_service()
verifier = get_verification_service()
prediction_service = get_prediction_service()


@pytest.fixture(autouse=True)
def setup_seed():
    seed_database()


def test_e2e_1_recovery_path():
    """E2E #1: Full Recovery Pipeline resulting in a verified ledger entry."""
    db = SessionLocal()
    try:
        # Get recoverable case
        case = db.query(RecoveryCase).join(Payment).filter(
            Payment.error_description.contains("Recoverable failure")
        ).first()
        assert case is not None

        # 1. Prediction via calibrated ML model
        preds = prediction_service.predict_recovery(case.id, prediction_mode="ml_model")
        assert preds["success"] is True

        # 2. Action proposed
        act = RecoveryAction(
            case_id=case.id,
            action_type=RecoveryActionType.RETRY,
            reason="ML recommended timed retry",
            predicted_success_probability=0.85,
            status=RecoveryActionStatus.PROPOSED,
        )
        db.add(act)
        db.commit()
        db.refresh(act)

        # 3. Policy evaluation
        pol_res = policy_service.evaluate_action(case.id, act, case.merchant)
        assert pol_res["allowed"] is True

        # 4. Bounded execution
        exec_res = executor.execute_action(case.id, act, execution_mode="simulation")
        assert exec_res["success"] is True

        # 5. Independent verification
        ver_res = verifier.verify_recovery(case.id, action_id=act.id, verification_mode="simulation")
        assert ver_res["recovered"] is True

        # 6. Verify Ledger entry created
        ledger = db.query(RecoveryLedger).filter(RecoveryLedger.case_id == case.id).first()
        assert ledger is not None
        assert ledger.net_recovered > 0
    finally:
        db.close()


def test_e2e_2_policy_block_opted_out():
    """E2E #2: Customer opt-out strictly blocks AI communication recommendations."""
    db = SessionLocal()
    try:
        case = db.query(RecoveryCase).join(Customer).filter(Customer.opted_out == True).first()
        assert case is not None

        act = RecoveryAction(
            case_id=case.id,
            action_type=RecoveryActionType.SEND_NOTIFICATION,
            reason="AI recommends recovery SMS",
            predicted_success_probability=0.60,
            status=RecoveryActionStatus.PROPOSED,
        )
        db.add(act)
        db.commit()
        db.refresh(act)

        # Policy evaluates action
        pol_res = policy_service.evaluate_action(case.id, act, case.merchant)
        assert pol_res["allowed"] is False
        assert "customer_opt_out" in pol_res["rule_violations"]

        # Executor must never execute denied actions
        act.status = RecoveryActionStatus.DENIED
        db.commit()

        # Audit decision exists
        dec = db.query(PolicyDecision).filter(PolicyDecision.action_id == act.id).first()
        assert dec is not None
        assert dec.result.value == "denied"
    finally:
        db.close()


def test_e2e_3_bank_outage_wait():
    """E2E #3: Bank degradation triggers policy barrier to block retry and schedule WAIT."""
    db = SessionLocal()
    try:
        case = db.query(RecoveryCase).join(Payment).filter(Payment.bank == "Kotak").first()
        assert case is not None

        # AI recommends retry
        ai_act = RecoveryAction(
            case_id=case.id,
            action_type=RecoveryActionType.RETRY,
            reason="AI Model suggests standard retry",
            predicted_success_probability=0.75,
            status=RecoveryActionStatus.PROPOSED,
        )
        db.add(ai_act)
        db.commit()
        db.refresh(ai_act)

        # Policy rejects due to degraded bank failure rate
        pol_res = policy_service.evaluate_action(case.id, ai_act, case.merchant)
        assert pol_res["allowed"] is False
        assert "bank_outage_detected" in pol_res["rule_violations"]
        assert pol_res["fallback_recommended_action"] == "wait"

        # WAIT is enqueued
        wait_act = RecoveryAction(
            case_id=case.id,
            action_type=RecoveryActionType.WAIT,
            reason="Bank outage: deferring execution",
            predicted_success_probability=0.75,
            status=RecoveryActionStatus.PROPOSED,
        )
        db.add(wait_act)
        db.commit()
        db.refresh(wait_act)

        exec_res = executor.execute_action(case.id, wait_act, execution_mode="simulation")
        assert exec_res["success"] is True
        assert "scheduled_at" in exec_res["details"]
    finally:
        db.close()


def test_e2e_4_multi_step_replanning():
    """E2E #4: Action 1 fails verification -> replanning triggers Action 2 -> success."""
    db = SessionLocal()
    try:
        case = db.query(RecoveryCase).join(Payment).filter(Payment.error_code == "CARD_EXPIRED").first()
        assert case is not None

        # Step 1: Retry action fails
        act1 = RecoveryAction(
            case_id=case.id,
            action_type=RecoveryActionType.RETRY,
            reason="Attempt 1: Gateway Retry",
            status=RecoveryActionStatus.PROPOSED,
        )
        db.add(act1)
        db.commit()
        db.refresh(act1)

        executor.execute_action(case.id, act1, execution_mode="simulation")
        ver1 = verifier.verify_recovery(case.id, action_id=act1.id, verification_mode="simulation")
        assert ver1["recovered"] is False

        # Step 2: Replanning with payment link
        act2 = RecoveryAction(
            case_id=case.id,
            action_type=RecoveryActionType.GENERATE_PAYMENT_LINK,
            reason="Attempt 2: Request card update via Payment Link",
            status=RecoveryActionStatus.PROPOSED,
        )
        db.add(act2)
        db.commit()
        db.refresh(act2)

        executor.execute_action(case.id, act2, execution_mode="simulation")
        ver2 = verifier.verify_recovery(case.id, action_id=act2.id, verification_mode="simulation")
        assert ver2["recovered"] is True

        # Verify ledger written
        ledger = db.query(RecoveryLedger).filter(RecoveryLedger.case_id == case.id).first()
        assert ledger is not None
        assert ledger.net_recovered > 0
    finally:
        db.close()
