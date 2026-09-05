from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Numeric, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from ..database import Base

class PaymentStatus(str, enum.Enum):
    CREATED = "created"
    ATTEMPTED = "attempted"
    CAPTURED = "captured"
    FAILED = "failed"

class PaymentMethod(str, enum.Enum):
    CARD = "card"
    UPI = "upi"
    NETBANKING = "netbanking"
    WALLET = "wallet"
    EMI = "emi"

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    razorpay_payment_id = Column(String(100), unique=True, index=True, nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="INR", nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.CREATED, nullable=False)
    method = Column(Enum(PaymentMethod), nullable=True)
    bank = Column(String(100), nullable=True)
    error_code = Column(String(50), nullable=True)
    error_description = Column(Text, nullable=True)
    attempt_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    merchant = relationship("Merchant", back_populates="payments")
    customer = relationship("Customer", back_populates="payments")
    payment_events = relationship("PaymentEvent", back_populates="payment")
    recovery_case = relationship("RecoveryCase", back_populates="payment", uselist=False)
