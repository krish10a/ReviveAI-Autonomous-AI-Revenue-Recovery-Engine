"""
Timeline event model for recording events in the recovery process.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base

class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("recovery_cases.id"), nullable=False)
    actor = Column(String(100), nullable=False)      # who/what performed the action (e.g., 'diagnosis_service', 'executor_service')
    action = Column(String(100), nullable=False)     # what action was performed (e.g., 'diagnose_failure', 'execute_retry')
    input_json = Column(Text, nullable=True)         # input data as JSON string
    decision_json = Column(Text, nullable=True)      # decision data as JSON string
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    case = relationship("RecoveryCase", back_populates="timeline_events")