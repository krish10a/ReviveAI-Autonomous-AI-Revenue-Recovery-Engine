"""
Merchant model for storing merchant information and policy settings.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Numeric, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from ..database import Base

class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(Integer, primary_key=True, index=True)
    # Merchant identifiers
    merchant_reference = Column(String(100), unique=True, nullable=False)  # e.g., "MERCH_001"
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    website = Column(String(255), nullable=True)

    # Razorpay configuration
    razorpay_key_id = Column(String(100), nullable=True)  # For API authentication
    razorpay_key_secret = Column(String(100), nullable=True)  # For API authentication
    webhook_secret = Column(String(100), nullable=True)  # For webhook signature verification

    # Policy settings (can override platform defaults)
    max_retries = Column(Integer, default=3)
    contact_start_hour = Column(Integer, default=8)  # 8 AM (08:00)
    contact_end_hour = Column(Integer, default=21)   # 9 PM (21:00)
    max_automated_amount = Column(Numeric(10, 2), default=5000.00)  # Maximum amount for automated recovery
    human_escalation_threshold = Column(Numeric(10, 2), default=10000.00)  # Amount requiring human escalation
    message_cooldown_hours = Column(Integer, default=1)  # Hours between customer contacts
    case_expiry_hours = Column(Integer, default=24)  # Hours after which a case expires
    timezone = Column(String(50), default="UTC")

    # Status
    is_active = Column(Boolean, default=True)
    is_test_mode = Column(Boolean, default=True)  # Whether to use Razorpay test mode

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    recovery_cases = relationship("RecoveryCase", back_populates="merchant")
    payments = relationship("Payment", back_populates="merchant")
    customers = relationship("Customer", back_populates="merchant")