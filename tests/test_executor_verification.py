"""
Automated tests for Bounded Executor, Independent Verification, and Financial Ledger.
"""

import pytest
from apps.api.app.database import SessionLocal
from apps.api.app.models import (
    RecoveryCase,
    Payment,
    RecoveryAction,
    RecoveryActionType,
    RecoveryActionStatus,
    RecoveryLedger,
)
from apps.api.app.services.executor import get_executor_service
from apps.api.app.services.verification import get_verification_service

executor = get_executor_service()
verifier = get_verification_service()


def test_executor_rejects_arbitrary_actions():
    """Executor must strictly reject actions not present in the allowed typed enum."""
    class FakeAction:
        action_type = "REFUND_MONEY_UNAUTHORIZED"

    with pytest.raises(ValueError) as exc:
        executor.execute_action(case_id=1, action=FakeAction(), execution_mode="simulation")
    assert "rejected untyped action" in str(exc.value)


def test_executor_records_execution_mode():
    """Every executed action must explicitly record its execution mode."""
    db = SessionLocal()
    try:
        case = db.query(RecoveryCase).first()
        act = RecoveryAction(
            case_id=case.id,
            action_type=RecoveryActionType.RETRY,
            reason="Test retry",
            status=RecoveryActionStatus.PROPOSED,
        )
        db.add(act)
        db.commit()
        db.refresh(act)

        res = executor.execute_action(case.id, act, execution_mode="simulation")
        assert res["success"] is True
        assert res["execution_mode"] == "simulation"
    finally:
        db.close()


def test_independent_verification_writes_ledger():
    """Verified recovery must record an append-only entry into the RecoveryLedger."""
    db = SessionLocal()
    try:
        case = db.query(RecoveryCase).first()
        act = RecoveryAction(
            case_id=case.id,
            action_type=RecoveryActionType.RETRY,
            reason="Test ledger creation",
            status=RecoveryActionStatus.EXECUTED,
        )
        db.add(act)
        db.commit()
        db.refresh(act)

        ver_res = verifier.verify_recovery(case.id, action_id=act.id, verification_mode="simulation")
        if ver_res["recovered"]:
            ledger = db.query(RecoveryLedger).filter(RecoveryLedger.case_id == case.id).first()
            assert ledger is not None
            assert ledger.gross_amount > 0
            assert ledger.net_recovered <= ledger.gross_amount
            assert ledger.action_cost >= 0
    finally:
        db.close()


def test_payment_link_cost_canonical():
    """Verify that payment link action cost equals canonical ₹1.50 in verification service."""
    from apps.api.app.config import PAYMENT_LINK_COST_INR, get_action_cost
    from decimal import Decimal

    assert PAYMENT_LINK_COST_INR == Decimal("1.50")
    assert get_action_cost(RecoveryActionType.GENERATE_PAYMENT_LINK) == Decimal("1.50")
    assert get_action_cost("generate_payment_link") == Decimal("1.50")
    assert get_action_cost("payment_link") == Decimal("1.50")

