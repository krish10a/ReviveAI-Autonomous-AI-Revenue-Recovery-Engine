from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base

class RecoveryPrediction(Base):
    __tablename__ = "recovery_predictions"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("recovery_cases.id"), nullable=False)
    action_type = Column(String(50), nullable=False)  # retry_now, retry_later, payment_link, etc.
    probability = Column(Numeric(3, 2), nullable=False)  # 0.00 to 1.00
    confidence = Column(Numeric(3, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    case = relationship("RecoveryCase", back_populates="recovery_predictions")
