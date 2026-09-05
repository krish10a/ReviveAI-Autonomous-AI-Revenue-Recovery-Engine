"""
Audit log model for tracking all critical events in the recovery process.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from ..database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    # For generic audit logging (can be linked to different entities)
    entity_type = Column(String(50), nullable=True)  # e.g., 'recovery_case', 'payment'
    entity_id = Column(Integer, nullable=True)       # ID of the entity
    # Alternatively, direct foreign key to recovery_case for simplicity in this context
    case_id = Column(Integer, ForeignKey("recovery_cases.id"), nullable=True)
    actor = Column(String(100), nullable=False)      # who/what performed the action (e.g., 'system', 'agent_loop_service', 'human')
    action = Column(String(100), nullable=False)     # what action was performed (e.g., 'CREATE', 'DIAGNOSIS_COMPLETED')
    input_json = Column(Text, nullable=True)         # input data as JSON string
    decision_json = Column(Text, nullable=True)      # decision data as JSON string
    policy_result = Column(String(50), nullable=True) # e.g., 'ALLOWED', 'DENIED'
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    recovery_case = relationship("RecoveryCase", back_populates="audit_logs")

# Add relationship to RecoveryCase (we'll update RecoveryCase model later if needed)
