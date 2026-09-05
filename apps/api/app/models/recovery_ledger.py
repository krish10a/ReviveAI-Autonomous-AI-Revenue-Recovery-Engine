from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from ..database import Base


class RecoveryLedger(Base):
    __tablename__ = "recovery_ledger"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("recovery_cases.id"), nullable=False, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False, index=True)
    gross_amount = Column(Numeric(12, 2), nullable=False)
    action_cost = Column(Numeric(10, 2), nullable=False, default=0.00)
    net_recovered = Column(Numeric(12, 2), nullable=False)
    recovery_action = Column(String(50), nullable=False)
    provider_reference = Column(String(100), nullable=True)
    recovered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    details = Column(Text, nullable=True)

    # Relationships
    recovery_case = relationship("RecoveryCase", backref="ledger_entries")
    payment = relationship("Payment", backref="ledger_entries")

    def __repr__(self):
        return f"<RecoveryLedger case_id={self.case_id} net={self.net_recovered}>"
