from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Numeric, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from ..database import Base

class RecoveryActionType(str, enum.Enum):
    WAIT = "wait"
    SEND_NOTIFICATION = "send_notification"
    GENERATE_PAYMENT_LINK = "generate_payment_link"
    RETRY = "retry"
    ESCALATE = "escalate"
    STOP = "stop"

class RecoveryActionStatus(str, enum.Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    DENIED = "denied"
    EXECUTED = "executed"
    VERIFIED = "verified"

class RecoveryAction(Base):
    __tablename__ = "recovery_actions"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("recovery_cases.id"), nullable=False)
    action_type = Column(Enum(RecoveryActionType), nullable=False)
    reason = Column(Text, nullable=True)
    predicted_success_probability = Column(Numeric(3, 2), nullable=True)
    expected_value = Column(Numeric(10, 2), nullable=True)
    status = Column(Enum(RecoveryActionStatus), default=RecoveryActionStatus.PROPOSED, nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    result = Column(Text, nullable=True)  # JSON stored as text
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    case = relationship("RecoveryCase", back_populates="recovery_actions")
