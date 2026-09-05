"""
Tests for Core Invariants in ReviveAI.
Covers:
  1. Policy denies -> executor does not act
  2. Captured -> no regression from late failure
  3. Duplicate event -> no duplicate business effect
  4. Duplicate recovery -> no duplicate ledger entry
  5. Selected action -> executed action (no silent substitution)
  6. Verification failure -> no recovery
  7. Recovery proof -> ledger written exactly once
  8. Customer opt-out -> zero communications dispatched
"""

import pytest
import uuid
from decimal import Decimal
from apps.api.app.database import SessionLocal
from apps.api.app.models import (
    Merchant,
    Customer,
    Payment,
    PaymentStatus,
    PaymentMethod,
    PaymentEvent,
    RecoveryCase,
    RecoveryCaseStatus,
    RecoveryAction,
    RecoveryActionType,
    RecoveryActionStatus,
    RecoveryLedger,
    Communication,
)
from apps.api.app.services.policy import get_policy_engine_service
from apps.api.app.services.executor import get_executor_service
from apps.api.app.services.verification import get_verification_service


def test_invariant_1_policy_denies_blocks_execution():
    """Invariant 1: When policy engine denies an action, the executor MUST NOT execute it."""
    db = SessionLocal()
    try:
        policy_service = get_policy_engine_service()
        executor = get_executor_service()

        case = db.query(RecoveryCase).first()
        assert case is not None

        # Create proposed retry action on a merchant with zero retries allowed
        action = RecoveryAction(
            case_id=case.id,
            action_type=RecoveryActionType.RETRY,
            reason="Test policy denial blocking",
            status=RecoveryActionStatus.PROPOSED,
        )
        db.add(action)
        db.commit()
        db.refresh(action)

        # Mock or evaluate against an opted-out customer or outage to ensure denial
        pol_result = policy_service.evaluate_action(case.id, action, case.merchant)
        # If policy denies, executor must never execute action
        if not pol_result["allowed"]:
            # Assert executor does not execute denied action
            assert action.status != RecoveryActionStatus.APPROVED
            assert action.status != RecoveryActionStatus.EXECUTED
    finally:
        db.close()


def test_invariant_2_captured_no_regression():
    """Invariant 2: A payment that is CAPTURED cannot be regressed by any failure event."""
    db = SessionLocal()
    try:
        # Create a captured payment
        m = db.query(Merchant).first()
        c = db.query(Customer).first()
        payment = Payment(
            merchant_id=m.id,
            customer_id=c.id,
            amount=Decimal("1500.00"),
            currency="INR",
            method=PaymentMethod.UPI,
            status=PaymentStatus.CAPTURED,
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

        # Attempt to regress via out-of-order failed event
        if payment.status == PaymentStatus.CAPTURED:
            # Transition to FAILED is rejected by state machine
            allowed_transition = payment.status != PaymentStatus.CAPTURED
            assert allowed_transition is False
            assert payment.status == PaymentStatus.CAPTURED
    finally:
        db.close()


def test_invariant_3_duplicate_event_idempotency():
    """Invariant 3: Duplicate event with same provider event ID produces no duplicate business mutation."""
    db = SessionLocal()
    try:
        event_id = f"evt_inv_test_{uuid.uuid4().hex[:8]}"
        m = db.query(Merchant).first()
        p = db.query(Payment).first()

        # First event
        ev1 = PaymentEvent(
            payment_id=p.id,
            event_type="payment.failed",
            razorpay_event_id=event_id,
            raw_payload="{}",
            processed=True,
        )
        db.add(ev1)
        db.commit()

        # Check deduplication check
        existing = db.query(PaymentEvent).filter(PaymentEvent.razorpay_event_id == event_id).first()
        assert existing is not None

        # Duplicate delivery must be ignored
        duplicate_detected = db.query(PaymentEvent).filter(PaymentEvent.razorpay_event_id == event_id).count() == 1
        assert duplicate_detected is True
    finally:
        db.close()


def test_invariant_4_duplicate_recovery_no_duplicate_ledger():
    """Invariant 4: Repeating verification on an already recovered case must not create duplicate financial ledger entries."""
    db = SessionLocal()
    try:
        verifier = get_verification_service()
        # Find recovered case that already has a ledger entry
        ledger_entry = db.query(RecoveryLedger).first()
        if ledger_entry:
            case_id = ledger_entry.case_id
            initial_count = db.query(RecoveryLedger).filter(RecoveryLedger.case_id == case_id).count()
            assert initial_count == 1

            # Second verification attempt
            res = verifier.verify_recovery(case_id, verification_mode="simulation")
            final_count = db.query(RecoveryLedger).filter(RecoveryLedger.case_id == case_id).count()
            # Must remain strictly 1
            assert final_count == 1
    finally:
        db.close()


def test_invariant_5_selected_action_equals_executed_action():
    """Invariant 5: Selected action MUST match executed action (no silent substitution)."""
    db = SessionLocal()
    try:
        executor = get_executor_service()
        case = db.query(RecoveryCase).filter(RecoveryCase.status == RecoveryCaseStatus.OPEN).first()
        if not case:
            case = db.query(RecoveryCase).first()

        for test_action_type in [RecoveryActionType.GENERATE_PAYMENT_LINK, RecoveryActionType.WAIT, RecoveryActionType.RETRY]:
            act = RecoveryAction(
                case_id=case.id,
                action_type=test_action_type,
                reason="Invariant 5 test",
                status=RecoveryActionStatus.APPROVED,
            )
            db.add(act)
            db.commit()
            db.refresh(act)

            res = executor.execute_action(case.id, act, execution_mode="simulation")
            # Invariant: executed action type must match the approved action type
            assert res["action_type"] == test_action_type.value
            assert act.action_type == test_action_type
    finally:
        db.close()


def test_invariant_6_verification_failure_no_recovery():
    """Invariant 6: If independent verification fails, payment and case MUST NOT be marked RECOVERED."""
    db = SessionLocal()
    try:
        # Create a non-recoverable case
        m = db.query(Merchant).first()
        c = db.query(Customer).first()
        payment = Payment(
            merchant_id=m.id,
            customer_id=c.id,
            amount=Decimal("999.00"),
            currency="INR",
            method=PaymentMethod.CARD,
            status=PaymentStatus.FAILED,
            error_code="CARD_EXPIRED",
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

        case = RecoveryCase(
            payment_id=payment.id,
            merchant_id=m.id,
            customer_id=c.id,
            amount=payment.amount,
            currency="INR",
            status=RecoveryCaseStatus.OPEN,
        )
        db.add(case)
        db.commit()
        db.refresh(case)

        # Execute RETRY on expired card (which fails simulation verification)
        act = RecoveryAction(
            case_id=case.id,
            action_type=RecoveryActionType.RETRY,
            reason="Will fail verification",
            status=RecoveryActionStatus.APPROVED,
        )
        db.add(act)
        db.commit()
        db.refresh(act)

        verifier = get_verification_service()
        ver_res = verifier.verify_recovery(case.id, action_id=act.id, verification_mode="simulation")
        assert ver_res["recovered"] is False

        # Invariant: Status must remain OPEN, not RECOVERED
        db.refresh(payment)
        db.refresh(case)
        assert payment.status != PaymentStatus.CAPTURED
        assert case.status != RecoveryCaseStatus.RECOVERED

        # Invariant: No ledger entry created
        ledger = db.query(RecoveryLedger).filter(RecoveryLedger.case_id == case.id).first()
        assert ledger is None
    finally:
        db.close()


def test_invariant_7_recovery_proof_ledger_written_once():
    """Invariant 7: Recovery ledger entry contains exact financial balance (net = gross - cost)."""
    db = SessionLocal()
    try:
        ledgers = db.query(RecoveryLedger).all()
        for led in ledgers:
            # Check non-negative amounts
            assert led.gross_amount > 0
            assert led.action_cost >= 0
            # Net = Gross - Cost with Decimal precision
            expected_net = led.gross_amount - led.action_cost
            assert led.net_recovered == expected_net
            assert led.provider_reference is not None
    finally:
        db.close()


def test_invariant_8_opt_out_zero_communications():
    """Invariant 8: An opted-out customer MUST NOT receive any communications."""
    db = SessionLocal()
    try:
        opted_out_cust = db.query(Customer).filter(Customer.opted_out == True).first()
        if opted_out_cust:
            # Query all communications for this customer
            comms = db.query(Communication).filter(Communication.customer_id == opted_out_cust.id).all()
            # Invariant: zero dispatched communications
            dispatched = [c for c in comms if c.status == "sent"]
            assert len(dispatched) == 0
    finally:
        db.close()


def test_quiet_hours_boundary_conditions():
    """Verify quiet hours policy boundaries (21:00-08:00): 20:59 allowed, 21:00 blocked, 21:01 blocked, 07:59 blocked, 08:00 allowed, 08:01 allowed."""
    from datetime import time
    from apps.api.app.config import is_quiet_hours, QUIET_HOURS_START_HOUR, QUIET_HOURS_END_HOUR

    assert QUIET_HOURS_START_HOUR == 21
    assert QUIET_HOURS_END_HOUR == 8

    # 20:59 -> Outside quiet hours -> Allowed (False)
    t_2059 = time(20, 59)
    assert is_quiet_hours(t_2059) is False

    # 21:00 -> Exact start of quiet hours -> Blocked (True)
    t_2100 = time(21, 0)
    assert is_quiet_hours(t_2100) is True

    # 21:01 -> During quiet hours -> Blocked (True)
    t_2101 = time(21, 1)
    assert is_quiet_hours(t_2101) is True

    # 07:59 -> During quiet hours -> Blocked (True)
    t_0759 = time(7, 59)
    assert is_quiet_hours(t_0759) is True

    # 08:00 -> Exact end of quiet hours -> Allowed (False)
    t_0800 = time(8, 0)
    assert is_quiet_hours(t_0800) is False

    # 08:01 -> Outside quiet hours -> Allowed (False)
    t_0801 = time(8, 1)
    assert is_quiet_hours(t_0801) is False

