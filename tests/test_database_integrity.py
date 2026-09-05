"""
Database integrity and constraint verification tests for ReviveAI.
"""

import pytest
from apps.api.app.database import SessionLocal
from apps.api.app.models import (
    RecoveryCase,
    RecoveryCaseStatus,
    Payment,
    PaymentStatus,
    PaymentEvent,
    RecoveryLedger,
)


def test_payment_has_valid_status_enum():
    """Verify that only valid PaymentStatus values are assigned."""
    db = SessionLocal()
    try:
        payments = db.query(Payment).all()
        for p in payments:
            assert isinstance(p.status, PaymentStatus) or p.status in ["created", "authorized", "captured", "refunded", "failed"]
    finally:
        db.close()


def test_recovery_case_status_validity():
    """Verify all recovery cases have valid statuses."""
    db = SessionLocal()
    try:
        cases = db.query(RecoveryCase).all()
        for c in cases:
            assert isinstance(c.status, RecoveryCaseStatus) or c.status in ["open", "recovered", "stopped", "expired"]
    finally:
        db.close()


def test_ledger_entries_have_positive_amounts():
    """Ledger entries must have gross_amount >= net_recovered >= 0."""
    db = SessionLocal()
    try:
        ledgers = db.query(RecoveryLedger).all()
        for l in ledgers:
            assert l.gross_amount >= l.net_recovered
            assert l.action_cost >= 0
    finally:
        db.close()
