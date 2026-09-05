"""
Customer model for storing customer information.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Numeric, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from ..database import Base

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    # Customer identifiers
    customer_reference = Column(String(100), unique=True, nullable=False)  # e.g., "CUST_001"
    merchant_id = Column(Integer, ForeignKey("merchants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)

    # Preferences and status
    opted_out = Column(Boolean, default=False)  # Whether customer has opted out of recovery contacts
    preferred_contact_method = Column(String(50), nullable=True)  # e.g., 'email', 'sms', 'phone'
    language = Column(String(10), default="en")  # Language preference

    # Risk and history
    risk_score = Column(Numeric(3, 2), nullable=True)  # 0.00 to 1.00
    tenure_days = Column(Integer, nullable=True)  # Days since first transaction
    previous_successful_payments = Column(Integer, default=0)
    previous_failed_payments = Column(Integer, default=0)
    previous_recoveries = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    merchant = relationship("Merchant", back_populates="customers")
    payments = relationship("Payment", back_populates="customer")
    recovery_cases = relationship("RecoveryCase", back_populates="customer")