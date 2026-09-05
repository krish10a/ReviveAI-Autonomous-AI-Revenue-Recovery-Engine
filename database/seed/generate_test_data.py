"""
Generate test data for ReviveAI.
This script creates random test data for development and testing purposes.
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


async def init_db():
    """Initialize database connection."""
    engine = create_async_engine(ASYNC_DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_session


def create_merchant(session: AsyncSession):
    """Create a random merchant."""
    merchant = Merchant(
        name=fake.company(),
        email=fake.company_email(),
        webhook_secret=fake.uuid4(),
        max_retries=random.randint(1, 5),
        contact_start_hour=random.randint(8, 10),
        contact_end_hour=random.randint(18, 22),
        max_automated_amount=Decimal(str(random.randint(1000, 10000))),
        human_escalation_threshold=Decimal(str(random.randint(5000, 50000))),
        message_cooldown_hours=random.randint(1, 6),
        case_expiry_hours=random.randint(12, 72),
        is_active=True,
        is_test_mode=random.choice([True, False]),
    )
    session.add(merchant)
    return merchant


def create_customers(session: AsyncSession, merchant_id: int, count: int = 50):
    """Create random customers."""
    customers = []
    for i in range(count):
        customer = Customer(
            merchant_id=merchant_id,
            customer_reference=f"CUST_{fake.uuid4()[:8]}",
            name=fake.name(),
            email=fake.email(),
            phone=fake.phone_number(),
            opted_out=fake.boolean(chance_of_getting_true=10),
            preferred_contact_method=random.choice(['email', 'sms', 'whatsapp', 'in_app']),
            language=fake.language_code(),
            risk_score=Decimal(str(round(random.uniform(0.1, 0.9), 2))),
            tenure_days=random.randint(0, 1000),
            previous_successful_payments=random.randint(0, 100),
            previous_failed_payments=random.randint(0, 20),
            previous_recoveries=random.randint(0, 10),
        )
        session.add(customer)
        customers.append(customer)
    return customers


def create_payments(session: AsyncSession, merchant_id: int, customers, count: int = 100):
    """Create random payments."""
    payments = []
    for _ in range(count):
        customer = random.choice(customers)
        amount = Decimal(str(round(random.uniform(10.0, 10000.0), 2)))
        status = random.choice(list(PaymentMethod))
        payment = Payment(
            merchant_id=merchant_id,
            customer_id=customer.id,
            amount=amount,
            currency="INR",
            status=random.choice(list(PaymentStatus)),
            method=random.choice(list(PaymentMethod)),
            bank=fake.bank_country(),
            error_code=random.choice(['2045', '65', '05', 'NETWORK_ERROR', None]) if random.random() > 0.7 else None,
            error_description=fake.sentence() if random.random() > 0.8 else None,
            attempt_count=random.randint(0, 5),
        )
        session.add(payment)
        payments.append(payment)
    return payments


async def seed_database():
    """Main seeding function."""
    async_session = await init_db()

    async with async_session() as session:
        # Create merchant
        merchant = create_merchant(session)
        await session.flush()

        # Create customers
        customers = create_customers(session, merchant.id, count=50)
        await session.flush()

        # Create payments
        payments = create_payments(session, merchant.id, customers, count=100)
        await session.flush()

        # For each payment, create related entities (simplified)
        for payment in payments:
            # Skip if payment is already captured or created (no failure)
            if payment.status in [PaymentStatus.CREATED, PaymentStatus.CAPTURED]:
                continue

            # Create payment event
            payment_event = PaymentEvent(
                razorpay_event_id=fake.uuid4(),
                razorpay_payment_id=payment.razorpay_payment_id or fake.uuid4(),
                event_type="payment.failed" if payment.status == PaymentStatus.FAILED else "payment.processed",
                event_payload={"amount": str(payment.amount), "currency": payment.currency},
                created_at=datetime.utcnow() - timedelta(hours=random.randint(1, 24)),
            )
            session.add(payment_event)
            payment.payment_events.append(payment_event)

            # Create failure diagnosis if failed
            if payment.status == PaymentStatus.FAILED:
                diagnosis = FailureDiagnosis(
                    payment_id=payment.id,
                    failure_category=random.choice(['insufficient_funds', 'expired_card', 'network_error', 'bank_declined', 'fraud_suspected', 'unknown']),
                    confidence=round(random.uniform(0.1, 0.9), 2),
                    customer_action_required=fake.boolean(chance_of_getting_true=30),
                    recommended_delay_minutes=random.randint(0, 1440) if random.random() > 0.5 else None,
                    source=random.choice(['rule', 'llm']),
                )
                session.add(diagnosis)

                # Create recovery case
                recovery_case = RecoveryCase(
                    payment_id=payment.id,
                    merchant_id=merchant.id,
                    customer_id=payment.customer_id,
                    amount=payment.amount,
                    currency=payment.currency,
                    status=random.choice(['OPEN', 'RECOVERED', 'STOPPED', 'EXPIRED']),
                    failure_category=diagnosis.failure_category,
                    recovery_probability=Decimal(str(round(random.uniform(0.1, 0.9), 2))),
                    expected_recovery=Decimal(str(round(random.uniform(0.0, float(payment.amount)), 2))),
                    risk_score=Decimal(str(round(random.uniform(0.1, 0.9), 2))),
                    attempt_count=payment.attempt_count,
                )
                session.add(recovery_case)
                await session.flush()

                # Create recovery prediction
                prediction = RecoveryPrediction(
                    recovery_case_id=recovery_case.id,
                    action_type=random.choice(['retry_now', 'retry_later', 'payment_link', 'notify', 'escalate', 'wait']),
                    probability=round(random.uniform(0.1, 0.9), 2),
                    confidence=round(random.uniform(0.1, 0.9), 2),
                )
                session.add(prediction)

                # Create recovery action
                action = RecoveryAction(
                    case_id=recovery_case.id,
                    action_type=random.choice(['wait', 'send_notification', 'generate_payment_link', 'retry', 'escalate', 'stop']),
                    reason=fake.sentence(),
                    predicted_success_probability=round(random.uniform(0.1, 0.9), 2),
                    expected_value=Decimal(str(round(random.uniform(0.0, float(payment.amount)), 2))),
                    status=random.choice(['proposed', 'approved', 'denied', 'executed', 'verified']),
                )
                session.add(action)

                # Create policy decision
                policy_decision = PolicyDecision(
                    case_id=recovery_case.id,
                    action_id=action.id,
                    rule_name=random.choice(['high_value_rule', 'velocity_rule', 'fraud_rule', 'bank_outage_rule']),
                    result=random.choice(['ALLOWED', 'DENIED']),
                    reason=fake.sentence() if random.random() > 0.5 else None,
                )
                session.add(policy_decision)

                # Create communication
                communication = Communication(
                    case_id=recovery_case.id,
                    customer_id=payment.customer_id,
                    channel=random.choice(['email', 'sms', 'whatsapp', 'in_app']),
                    message_body=fake.paragraph(),
                    sent_at=datetime.utcnow() - timedelta(hours=random.randint(0, 24)) if random.random() > 0.5 else None,
                    delivered=fake.boolean(chance_of_getting_true=80),
                )
                session.add(communication)

                # Create audit log
                audit_log = AuditLog(
                    entity_type='recovery_case',
                    entity_id=recovery_case.id,
                    case_id=recovery_case.id,
                    actor=random.choice(['system', 'admin', 'user']),
                    action=random.choice(['CREATE', 'UPDATE', 'DELETE']),
                    input_json='{}',
                    decision_json='{}',
                    policy_result=random.choice(['ALLOWED', 'DENIED']),
                )
                session.add(audit_log)

        # Commit all changes
        await session.commit()

    await engine.dispose()
    print("Test data generated successfully!")


if __name__ == "__main__":
    # Note: This script requires the DATABASE_URL environment variable to be set.
    # Example: export DATABASE_URL="postgresql://reviveai_user:reviveai_pass@localhost:5432/reviveai"
    asyncio.run(seed_database())