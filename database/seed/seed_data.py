"""
Seed data for ReviveAI demo.
This script creates deterministic demo data for the recovery engine.
"""

import asyncio
import os
from datetime import datetime, timedelta
from decimal import Decimal
import random
from faker import Faker

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Import your models
from apps.api.app.models import (
    Merchant,
    Customer,
    Payment,
    PaymentStatus,
    PaymentMethod,
    PaymentEvent,
    RecoveryCase,
    FailureDiagnosis,
    RecoveryPrediction,
    RecoveryAction,
    PolicyDecision,
    Communication,
    AuditLog,
)
from apps.api.app.database import Base, DATABASE_URL

# Override DATABASE_URL to use asyncpg for async operations
ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

fake = Faker()
Faker.seed(42)  # For deterministic results
random.seed(42)


async def init_db():
    """Initialize database connection."""
    engine = create_async_engine(ASYNC_DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_session


def get_demo_merchant(session: AsyncSession):
    """Create or get a demo merchant."""
    # In a real scenario, we would query for an existing merchant or create one.
    # For simplicity, we'll create a new one.
    merchant = Merchant(
        name="Demo Merchant",
        email="merchant@example.com",
        webhook_secret="demo_webhook_secret",
        max_retries=3,
        contact_start_hour=8,  # 8 AM
        contact_end_hour=20,   # 8 PM
        max_automated_amount=Decimal("5000.00"),
        human_escalation_threshold=Decimal("10000.00"),
        message_cooldown_hours=1,
        case_expiry_hours=24,
    )
    session.add(merchant)
    return merchant


def get_demo_customers(session: AsyncSession, merchant_id: int, count: int = 10):
    """Create demo customers."""
    customers = []
    for i in range(count):
        customer = Customer(
            merchant_id=merchant_id,
            customer_reference=f"CUST_{i:04d}",
            name=fake.name(),
            email=fake.email(),
            phone=fake.phone_number(),
            opted_out=(i == 2),  # Third customer is opted out
            tenure_days=random.randint(30, 365),
        )
        session.add(customer)
        customers.append(customer)
    return customers


def create_payments(session: AsyncSession, merchant_id: int, customers):
    """Create demo payments with various failure types and statuses."""
    payments = []
    failure_scenarios = [
        # (description, failure_category, error_code, is_recoverable, special_flag)
        ("Insufficient funds - recoverable", "insufficient_funds", "2045", True, "recoverable_failure"),
        ("Insufficient funds - non-recoverable", "insufficient_funds", "2045", False, "non_recoverable_failure"),
        ("Card expired", "expired_card", "65", False, "expired_card"),
        ("Network error - recoverable", "network_error", "NETWORK_ERROR", True, "network_error"),
        ("Bank outage", "bank_declined", "05", True, "bank_outage"),
        ("High-value transaction", "insufficient_funds", "2045", True, "high_value"),
        ("Already captured", None, None, False, "already_captured"),
        ("Multiple retry attempts", "insufficient_funds", "2045", True, "multiple_retries"),
        ("Human escalation case", "fraud_suspected", "FRAUD", True, "human_escalation"),
        ("Opted-out customer", "insufficient_funds", "2045", True, "opted_out"),  # Will be blocked by policy
    ]

    for i, (desc, failure_cat, error_code, is_recoverable, flag) in enumerate(failure_scenarios):
        customer_idx = i % len(customers)
        customer = customers[customer_idx]

        # Determine amount based on flags
        if flag == "high_value":
            amount = Decimal("15000.00")  # Above human escalation threshold
        else:
            amount = Decimal(str(random.randint(1000, 5000)))

        payment = Payment(
            merchant_id=merchant_id,
            customer_id=customer.id,
            amount=amount,
            currency="INR",
            status=PaymentStatus.FAILED,
            method=random.choice(list(PaymentMethod)),
            bank=fake.bank_country() if flag != "expired_card" else "Expired Bank",
            error_code=error_code,
            error_description=f"Simulated {desc}",
            attempt_count=0 if flag != "multiple_retries" else 2,
        )
        session.add(payment)
        payments.append((payment, desc, failure_cat, error_code, is_recoverable, flag, customer))

    return payments


async def seed_database():
    """Main seeding function."""
    async_session = await init_db()

    async with async_session() as session:
        # Create demo merchant
        merchant = get_demo_merchant(session)
        await session.flush()  # To get the merchant ID

        # Create demo customers
        customers = get_demo_customers(session, merchant.id, count=10)
        await session.flush()  # To get customer IDs

        # Create payments
        payments_data = create_payments(session, merchant.id, customers)
        await session.flush()  # To get payment IDs

        # For each payment, create related entities
        for payment, desc, failure_cat, error_code, is_recoverable, flag, customer in payments_data:
            # Create payment event (simulating the webhook event)
            payment_event = PaymentEvent(
                razorpay_event_id=f"evt_{fake.uuid4()}",
                razorpay_payment_id=payment.razorpay_payment_id or f"pay_{fake.uuid4()}",
                event_type="payment.failed",
                event_payload={"amount": str(payment.amount), "currency": payment.currency},
                created_at=datetime.utcnow() - timedelta(hours=2),
            )
            session.add(payment_event)

            # Link payment event to payment
            payment.payment_events.append(payment_event)

            # Create failure diagnosis
            diagnosis = FailureDiagnosis(
                payment_id=payment.id,
                failure_category=failure_cat or "unknown",
                confidence=0.9 if failure_cat else 0.5,
                customer_action_required=(flag == "expired_card"),
                recommended_delay_minutes=60 if flag == "network_error" else 0,
                source="rule" if failure_cat else "llm_fallback",
            )
            session.add(diagnosis)

            # Create recovery case
            recovery_case = RecoveryCase(
                payment_id=payment.id,
                merchant_id=merchant.id,
                customer_id=customer.id,
                amount=payment.amount,
                currency=payment.currency,
                status="FAILED",  # Initial status
            )
            session.add(recovery_case)
            await session.flush()  # To get the recovery case ID

            # Link recovery case to payment (one-to-one)
            payment.recovery_case = recovery_case

            # Create recovery prediction (if we have a failure category)
            if failure_cat:
                # Predict recovery probabilities for different actions
                action_probabilities = {
                    "retry_now": 0.3 if flag != "bank_outage" else 0.05,
                    "retry_later": 0.6 if flag != "bank_outage" else 0.1,
                    "payment_link": 0.7 if flag != "expired_card" else 0.8,
                    "notify": 0.5,
                    "escalate": 0.8 if flag == "human_escalation" else 0.3,
                    "wait": 0.65,
                }
                # Adjust for high-value
                if flag == "high_value":
                    action_probabilities["retry_now"] *= 0.5
                    action_probabilities["retry_later"] *= 0.5
                    action_probabilities["payment_link"] *= 0.8
                    action_probabilities["escalate"] *= 1.2

                # Normalize to ensure they are probabilities (optional)
                total = sum(action_probabilities.values())
                if total > 0:
                    action_probabilities = {k: v / total for k, v in action_probabilities.items()}

                prediction = RecoveryPrediction(
                    recovery_case_id=recovery_case.id,
                    action_probabilities=action_probabilities,
                    model_version="logistic_regression_v1",
                    features_used=["amount", "method", "bank", "failure_category", "hour_of_day", "day_of_week"],
                )
                session.add(prediction)

            # Create audit log for case creation
            audit_log = AuditLog(
                entity_type="recovery_case",
                entity_id=recovery_case.id,
                action="CREATE",
                changes={"status": "CREATED"},
                performed_by="system",
                performed_at=datetime.utcnow(),
            )
            session.add(audit_log)

        # Commit all changes
        await session.commit()

    await engine.dispose()
    print("Database seeded successfully!")


if __name__ == "__main__":
    # Note: This script requires the DATABASE_URL environment variable to be set.
    # Example: export DATABASE_URL="postgresql://reviveai_user:reviveai_pass@localhost:5432/reviveai"
    asyncio.run(seed_database())