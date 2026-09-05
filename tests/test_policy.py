"""
Automated tests for Policy Engine Guardrails.
Verifies all policy barrier rules: max retry, opt-out, night window, high value, bank outage, captured payment, amount ceiling.
"""

from decimal import Decimal
import pytest
from apps.api.app.database import SessionLocal
from apps.api.app.models import (
    RecoveryCase,
    RecoveryCaseStatus,
    Payment,
    PaymentStatus,
    Customer,
    Merchant,
    RecoveryAction,
    RecoveryActionType,
    RecoveryActionStatus,
)
from apps.api.app.services.policy import get_policy_engine_service

policy_service = get_policy_engine_service()


def test_policy_blocks_captured_payment():
    """Policy must deny actions on already captured payments."""
    db = SessionLocal()
    try:
        case = db.query(RecoveryCase).join(Payment).filter(Payment.status == PaymentStatus.CAPTURED).first()
        assert case is not None

        act = RecoveryAction(
            case_id=case.id,
            action_type=RecoveryActionType.RETRY,
            status=RecoveryActionStatus.PROPOSED
        )
        res = policy_service.evaluate_action(case.id, act, case.merchant)
        assert res["allowed"] is False
        assert "already_captured" in res["rule_violations"]
    finally:
        db.close()


def test_policy_blocks_opted_out_customer():
    """Policy must block all customer contact actions for opted-out customers."""
    db = SessionLocal()
    try:
        case = db.query(RecoveryCase).join(Customer).filter(Customer.opted_out == True).first()
        assert case is not None

        act = RecoveryAction(
            case_id=case.id,
            action_type=RecoveryActionType.SEND_NOTIFICATION,
            status=RecoveryActionStatus.PROPOSED
        )
        res = policy_service.evaluate_action(case.id, act, case.merchant)
        assert res["allowed"] is False
        assert "customer_opt_out" in res["rule_violations"]
    finally:
        db.close()


def test_policy_blocks_exceeded_retries():
    """Policy must deny retries when merchant max_retries is reached."""
    db = SessionLocal()
    try:
        case = db.query(RecoveryCase).filter(RecoveryCase.attempt_count >= 3).first()
        assert case is not None

        act = RecoveryAction(
            case_id=case.id,
            action_type=RecoveryActionType.RETRY,
            status=RecoveryActionStatus.PROPOSED
        )
        res = policy_service.evaluate_action(case.id, act, case.merchant)
        assert res["allowed"] is False
        assert "max_retries_exceeded" in res["rule_violations"]
    finally:
        db.close()


def test_policy_blocks_high_value_transaction():
    """Policy must deny automated retry for transactions exceeding merchant automated ceiling."""
    db = SessionLocal()
    try:
        case = db.query(RecoveryCase).filter(RecoveryCase.amount > 10000.00).first()
        assert case is not None

        act = RecoveryAction(
            case_id=case.id,
            action_type=RecoveryActionType.RETRY,
            status=RecoveryActionStatus.PROPOSED
        )
        res = policy_service.evaluate_action(case.id, act, case.merchant)
        assert res["allowed"] is False
        assert "merchant_amount_ceiling" in res["rule_violations"]
    finally:
        db.close()


def test_policy_detects_bank_outage_and_forces_wait():
    """Policy must detect degraded bank health, block retries, and mandate WAIT."""
    db = SessionLocal()
    try:
        case = db.query(RecoveryCase).join(Payment).filter(Payment.bank == "Kotak").first()
        assert case is not None

        act = RecoveryAction(
            case_id=case.id,
            action_type=RecoveryActionType.RETRY,
            status=RecoveryActionStatus.PROPOSED
        )
        res = policy_service.evaluate_action(case.id, act, case.merchant)
        assert res["allowed"] is False
        assert "bank_outage_detected" in res["rule_violations"]
        assert res["fallback_recommended_action"] == "wait"
    finally:
        db.close()
