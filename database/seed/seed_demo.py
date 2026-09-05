"""
Deterministic seed data for ReviveAI demo.
Creates the 8 canonical benchmark scenarios with stable keys for testing and demonstration.
"""

import os
import json
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import random
from faker import Faker

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from apps.api.app.models import (
    Merchant,
    Customer,
    Payment,
    PaymentStatus,
    PaymentMethod,
    PaymentEvent,
    RecoveryCase,
    RecoveryCaseStatus,
    FailureDiagnosis,
    RecoveryPrediction,
    RecoveryAction,
    RecoveryActionType,
    RecoveryActionStatus,
    PolicyDecision,
    PolicyDecisionResult,
    Communication,
    CommunicationChannel,
    AuditLog,
    TimelineEvent,
    RecoveryLedger,
)
from apps.api.app.database import Base, DATABASE_URL

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Faker.seed(42)
random.seed(42)

SCENARIO_KEYS = {
    0: "SCENARIO_1_RECOVERABLE",
    1: "SCENARIO_2_MULTI_STEP_RECOVERY",
    2: "SCENARIO_3_OPTED_OUT",
    3: "SCENARIO_4_HIGH_VALUE",
    4: "SCENARIO_5_BANK_OUTAGE",
    5: "SCENARIO_6_RETRY_LIMIT",
    6: "SCENARIO_7_ALREADY_CAPTURED",
    7: "SCENARIO_8_HUMAN_ESCALATION",
}


def reset_and_clean_db(db):
    """Clean all tables in reverse dependency order."""
    tables = [
        "recovery_ledger",
        "timeline_events",
        "audit_logs",
        "communications",
        "policy_decisions",
        "recovery_actions",
        "recovery_predictions",
        "failure_diagnoses",
        "recovery_cases",
        "payment_events",
        "payments",
        "customers",
        "merchants",
    ]
    for table in tables:
        try:
            db.execute(text(f"TRUNCATE TABLE {table} CASCADE;"))
        except Exception:
            db.rollback()
            try:
                db.execute(text(f"DELETE FROM {table};"))
            except Exception:
                db.rollback()
    db.commit()


def get_demo_merchant(session):
    """Create demo merchant with explicit policy limits."""
    merchant = Merchant(
        merchant_reference="DEMO_MERCHANT_001",
        name="ReviveAI Demo Merchant",
        email="merchant@reviveai.demo",
        webhook_secret=os.getenv("RAZORPAY_WEBHOOK_SECRET", "demo_webhook_secret"),
        max_retries=3,
        contact_start_hour=8,   # 8 AM (08:00)
        contact_end_hour=21,    # 9 PM (21:00)
        max_automated_amount=Decimal("10000.00"),
        human_escalation_threshold=Decimal("25000.00"),
        message_cooldown_hours=2,
        case_expiry_hours=48,
    )
    session.add(merchant)
    return merchant


def get_demo_customers(session, merchant_id, count=10):
    """Create deterministic demo customers."""
    customers = []
    for i in range(count):
        is_opted_out = (i == 2)  # Customer index 2 is explicitly opted out
        customer = Customer(
            merchant_id=merchant_id,
            customer_reference=f"CUST_{i:04d}",
            name=f"Customer {i+1} Demo",
            email=f"customer{i+1}@demo.reviveai.com",
            phone=f"+9198765432{i:02d}",
            opted_out=is_opted_out,
            tenure_days=180 + i * 20,
            previous_successful_payments=25 if i != 1 else 0,
            previous_failed_payments=1 if i != 1 else 5,
        )
        session.add(customer)
        customers.append(customer)
    return customers


def seed_database():
    """Main deterministic seeding function."""
    if "sqlite" in str(engine.url):
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        reset_and_clean_db(db)

        merchant = get_demo_merchant(db)
        db.flush()

        customers = get_demo_customers(db, merchant.id, count=10)
        db.flush()

        # Seed healthy historical baseline payments for HDFC (so HDFC failure rate < 15%)
        for h in range(5):
            db.add(Payment(
                merchant_id=merchant.id,
                customer_id=customers[0].id,
                amount=Decimal("1500.00"),
                currency="INR",
                status=PaymentStatus.CAPTURED,
                method=PaymentMethod.UPI,
                bank="HDFC",
                error_code=None,
                error_description="Successful baseline transaction",
                attempt_count=1,
            ))

        # Seed multiple degraded failed payments for Kotak (so Kotak failure rate > 70%)
        for k in range(4):
            db.add(Payment(
                merchant_id=merchant.id,
                customer_id=customers[4].id,
                amount=Decimal("3000.00"),
                currency="INR",
                status=PaymentStatus.FAILED,
                method=PaymentMethod.NETBANKING,
                bank="Kotak",
                error_code="BANK_GATEWAY_TIMEOUT",
                error_description="Kotak gateway timeout spike",
                attempt_count=1,
            ))
        db.flush()

        scenarios = [
            # 1. Recoverable failure (insufficient funds with good history)
            {
                "key": SCENARIO_KEYS[0],
                "description": "Recoverable failure - insufficient funds with good history",
                "amount": Decimal("2499.00"),
                "error_code": "BAD_REQUEST_INSUFFICIENT_FUNDS",
                "failure_category": "insufficient_funds",
                "is_recoverable": True,
                "customer_idx": 0,
                "flags": ["good_history"],
                "bank": "HDFC",
            },
            # 2. Non-recoverable failure (expired card)
            {
                "key": SCENARIO_KEYS[1],
                "description": "Non-recoverable failure - expired card",
                "amount": Decimal("1299.00"),
                "error_code": "CARD_EXPIRED",
                "failure_category": "expired_card",
                "is_recoverable": False,
                "customer_idx": 1,
                "flags": ["expired_card"],
                "bank": "ICICI",
            },
            # 3. Opted-out customer
            {
                "key": SCENARIO_KEYS[2],
                "description": "Opted-out customer (policy block on contact)",
                "amount": Decimal("1999.00"),
                "error_code": "BAD_REQUEST_INSUFFICIENT_FUNDS",
                "failure_category": "insufficient_funds",
                "is_recoverable": True,
                "customer_idx": 2,
                "flags": ["opted_out"],
                "bank": "SBI",
            },
            # 4. High-value transaction (>₹25,000 ceiling requiring human intervention)
            {
                "key": SCENARIO_KEYS[3],
                "description": "High-value transaction exceeds automated amount limit",
                "amount": Decimal("32000.00"),
                "error_code": "HIGH_VALUE_SECURITY_HOLD",
                "failure_category": "risk_check_failed",
                "is_recoverable": True,
                "customer_idx": 3,
                "flags": ["high_value"],
                "bank": "Axis",
            },
            # 5. Bank outage (bank health degraded)
            {
                "key": SCENARIO_KEYS[4],
                "description": "Bank outage - failure rate spike triggers WAIT policy",
                "amount": Decimal("4500.00"),
                "error_code": "BANK_GATEWAY_TIMEOUT",
                "failure_category": "bank_outage",
                "is_recoverable": True,
                "customer_idx": 4,
                "flags": ["bank_outage"],
                "bank": "Kotak",
            },
            # 6. Multiple retry attempts (case with attempt_count = 3 hitting max)
            {
                "key": SCENARIO_KEYS[5],
                "description": "Multiple retry attempts exhausted (attempt_count = 3)",
                "amount": Decimal("2100.00"),
                "error_code": "BAD_REQUEST_INSUFFICIENT_FUNDS",
                "failure_category": "insufficient_funds",
                "is_recoverable": True,
                "customer_idx": 5,
                "flags": ["max_retries_exhausted"],
                "attempt_count": 3,
                "bank": "HDFC",
            },
            # 7. Already-captured payment (idempotency guard)
            {
                "key": SCENARIO_KEYS[6],
                "description": "Already-captured payment - policy blocks further actions",
                "amount": Decimal("5000.00"),
                "error_code": None,
                "failure_category": None,
                "is_recoverable": False,
                "customer_idx": 6,
                "flags": ["already_captured"],
                "status": PaymentStatus.CAPTURED,
                "bank": "HDFC",
            },
            # 8. Human escalation (complex failure requiring ops team review)
            {
                "key": SCENARIO_KEYS[7],
                "description": "Human escalation - repeated fraud dispute alert",
                "amount": Decimal("28500.00"),
                "error_code": "MANUAL_REVIEW_REQUIRED",
                "failure_category": "suspicious_activity",
                "is_recoverable": True,
                "customer_idx": 7,
                "flags": ["human_escalation"],
                "bank": "SBI",
            },
        ]

        seeded_summary = []

        for i, sc in enumerate(scenarios):
            customer = customers[sc["customer_idx"]]

            is_captured = sc.get("status") == PaymentStatus.CAPTURED
            payment = Payment(
                merchant_id=merchant.id,
                customer_id=customer.id,
                amount=sc["amount"],
                currency="INR",
                status=sc.get("status", PaymentStatus.FAILED),
                method=PaymentMethod.CARD if i % 2 == 0 else PaymentMethod.UPI,
                bank=sc["bank"],
                error_code=sc["error_code"],
                error_description=sc["description"],
                attempt_count=sc.get("attempt_count", 1 if not is_captured else 0),
            )
            db.add(payment)
            db.flush()

            # Payment Event
            event_type = "payment.captured" if is_captured else "payment.failed"
            event = PaymentEvent(
                razorpay_event_id=f"evt_seed_{sc['key'].lower()}",
                payment_id=payment.id,
                event_type=event_type,
                raw_payload=json.dumps({
                    "entity": "event",
                    "account_id": merchant.merchant_reference,
                    "event": event_type,
                    "payload": {
                        "payment": {
                            "entity": {
                                "id": f"pay_seed_{payment.id}",
                                "amount": int(payment.amount * 100),
                                "currency": payment.currency,
                                "status": payment.status.value,
                                "bank": payment.bank,
                                "error_code": payment.error_code,
                            }
                        }
                    }
                }),
                processed=True,
                received_at=datetime.now(timezone.utc) - timedelta(hours=3),
            )
            db.add(event)
            db.flush()

            # Recovery Case
            case_status = RecoveryCaseStatus.RECOVERED if is_captured else RecoveryCaseStatus.OPEN
            if sc["key"] in ["SCENARIO_6_RETRY_LIMIT", "SCENARIO_8_HUMAN_ESCALATION"]:
                case_status = RecoveryCaseStatus.STOPPED

            recovery_case = RecoveryCase(
                payment_id=payment.id,
                merchant_id=merchant.id,
                customer_id=customer.id,
                amount=payment.amount,
                currency=payment.currency,
                status=case_status,
                attempt_count=payment.attempt_count,
            )
            db.add(recovery_case)
            db.flush()

            # Diagnosis
            confidence = Decimal("0.95")
            if "human_escalation" in sc["flags"] or "high_value" in sc["flags"]:
                confidence = Decimal("0.45")

            diagnosis = FailureDiagnosis(
                case_id=recovery_case.id,
                category=sc["failure_category"] or "captured_clean",
                confidence=confidence,
                customer_action_required=(sc["failure_category"] in ["expired_card", "insufficient_funds"]),
                recommended_delay_minutes=120 if sc["failure_category"] == "bank_outage" else 0,
                source="rule_engine" if sc["failure_category"] else "system_capture",
            )
            db.add(diagnosis)

            # Predictions for each scenario
            action_map = {
                0: (RecoveryActionType.RETRY, Decimal("0.85")),
                1: (RecoveryActionType.STOP, Decimal("0.95")),
                2: (RecoveryActionType.SEND_NOTIFICATION, Decimal("0.60")),
                3: (RecoveryActionType.ESCALATE, Decimal("0.90")),
                4: (RecoveryActionType.WAIT, Decimal("0.75")),
                5: (RecoveryActionType.STOP, Decimal("0.90")),
                6: (RecoveryActionType.STOP, Decimal("1.00")),
                7: (RecoveryActionType.ESCALATE, Decimal("0.92")),
            }
            action_type, prob = action_map[i]

            prediction = RecoveryPrediction(
                case_id=recovery_case.id,
                action_type=action_type.value,
                probability=prob,
                confidence=confidence,
            )
            db.add(prediction)

            # Recovery Action
            act_status = RecoveryActionStatus.APPROVED if i not in [2, 4, 6] else RecoveryActionStatus.DENIED

            action = RecoveryAction(
                case_id=recovery_case.id,
                action_type=action_type,
                reason=f"Optimal intervention according to prediction ({prob*100:.0f}%)",
                predicted_success_probability=prob,
                expected_value=payment.amount * prob,
                status=act_status,
            )
            db.add(action)
            db.flush()

            # Policy Decision
            denied = (i in [2, 4, 6])
            denied_reason = None
            if i == 2:
                denied_reason = "Customer has opted out of recovery communications"
            elif i == 4:
                denied_reason = "Bank degradation detected: rolling failure rate 72% > 30% threshold. Forcing WAIT."
            elif i == 6:
                denied_reason = "Payment already in captured status. Duplicate action blocked."

            policy_decision = PolicyDecision(
                case_id=recovery_case.id,
                action_id=action.id,
                rule_name=sc["key"],
                result=PolicyDecisionResult.DENIED if denied else PolicyDecisionResult.ALLOWED,
                reason=denied_reason or "All policy guardrails satisfied",
            )
            db.add(policy_decision)

            # Timeline event
            timeline = TimelineEvent(
                case_id=recovery_case.id,
                actor="ReviveAI::PolicyEngine",
                action="EVALUATE_POLICY",
                input_json=json.dumps({
                    "scenario": sc["key"],
                    "action": action_type.value,
                    "amount": float(payment.amount),
                }),
                decision_json=json.dumps({
                    "result": "DENIED" if denied else "ALLOWED",
                    "reason": denied_reason or "Policy approved",
                }),
                timestamp=datetime.now(timezone.utc) - timedelta(minutes=45),
            )
            db.add(timeline)

            seeded_summary.append({
                "scenario_index": i + 1,
                "scenario_key": sc["key"],
                "case_id": recovery_case.id,
                "payment_id": payment.id,
                "amount": float(payment.amount),
                "status": payment.status.value,
                "decision": "DENIED" if denied else "ALLOWED",
            })

        db.commit()
        print("\n=== REVIVEAI DETERMINISTIC DEMO SEED COMPLETED ===")
        print(f"Merchant ID: {merchant.id} ({merchant.merchant_reference})")
        print(f"Total Scenarios Seeded: {len(seeded_summary)}")
        for item in seeded_summary:
            print(f"  [{item['scenario_index']}] {item['scenario_key']}: Case #{item['case_id']}, ₹{item['amount']:.2f}, {item['decision']}")
        print("===================================================\n")
        return seeded_summary
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()