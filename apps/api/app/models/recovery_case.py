from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Numeric, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from ..database import Base

class RecoveryCaseStatus(str, enum.Enum):
    OPEN = "open"
    RECOVERED = "recovered"
    STOPPED = "stopped"
    EXPIRED = "expired"

class RecoveryCase(Base):
    __tablename__ = "recovery_cases"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="INR", nullable=False)
    status = Column(Enum(RecoveryCaseStatus), default=RecoveryCaseStatus.OPEN, nullable=False)
    failure_category = Column(String(100), nullable=True)
    recovery_probability = Column(Numeric(3, 2), nullable=True)  # 0.00 to 1.00
    expected_recovery = Column(Numeric(10, 2), nullable=True)
    risk_score = Column(Numeric(3, 2), nullable=True)
    attempt_count = Column(Integer, default=0, nullable=False)
    recovered_amount = Column(Numeric(10, 2), nullable=True)  # Track actual recovered amount
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    merchant = relationship("Merchant", back_populates="recovery_cases")
    customer = relationship("Customer", back_populates="recovery_cases")
    payment = relationship("Payment", back_populates="recovery_case")
    failure_diagnosis = relationship("FailureDiagnosis", back_populates="case", uselist=False)
    recovery_predictions = relationship("RecoveryPrediction", back_populates="case")
    recovery_actions = relationship("RecoveryAction", back_populates="case")
    policy_decisions = relationship("PolicyDecision", back_populates="case")
    communications = relationship("Communication", back_populates="case")
    audit_logs = relationship("AuditLog", back_populates="recovery_case")
    timeline_events = relationship("TimelineEvent", back_populates="case")
