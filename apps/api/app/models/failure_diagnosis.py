from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base

class FailureDiagnosis(Base):
    __tablename__ = "failure_diagnosis"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("recovery_cases.id"), nullable=False)
    category = Column(String(100), nullable=False)
    confidence = Column(Numeric(3, 2), nullable=False)  # 0.00 to 1.00
    customer_action_required = Column(Boolean, default=False, nullable=False)
    recommended_delay_minutes = Column(Integer, nullable=True)
    source = Column(String(20), nullable=False)  # 'rule' or 'llm'
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    case = relationship("RecoveryCase", back_populates="failure_diagnosis")
