from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base

class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id = Column(Integer, primary_key=True, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)
    razorpay_event_id = Column(String(100), unique=True, index=True, nullable=False)
    event_type = Column(String(50), nullable=False)
    raw_payload = Column(String, nullable=False)  # JSON stored as text
    processed = Column(Boolean, default=False, nullable=False)
    received_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    payment = relationship("Payment", back_populates="payment_events")
