from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from ..database import Base

class PolicyDecisionResult(str, enum.Enum):
    ALLOWED = "allowed"
    DENIED = "denied"

class PolicyDecision(Base):
    __tablename__ = "policy_decisions"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("recovery_cases.id"), nullable=False)
    action_id = Column(Integer, ForeignKey("recovery_actions.id"), nullable=False)
    rule_name = Column(String(100), nullable=False)
    result = Column(Enum(PolicyDecisionResult), nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    case = relationship("RecoveryCase", back_populates="policy_decisions")
    action = relationship("RecoveryAction")
