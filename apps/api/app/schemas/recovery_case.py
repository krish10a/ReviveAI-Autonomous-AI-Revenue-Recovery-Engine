"""
Pydantic schemas for RecoveryCase
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class RecoveryCaseStatus(str, Enum):
    OPEN = "open"
    RECOVERED = "recovered"
    STOPPED = "stopped"
    EXPIRED = "expired"

class RecoveryCaseBase(BaseModel):
    merchant_id: int
    customer_id: int
    payment_id: int
    amount: float
    currency: str = "INR"
    status: Optional[RecoveryCaseStatus] = RecoveryCaseStatus.OPEN
    failure_category: Optional[str] = None
    recovery_probability: Optional[float] = None
    expected_recovery: Optional[float] = None
    risk_score: Optional[float] = None
    attempt_count: int = 0
    recovered_amount: Optional[float] = None

class RecoveryCaseCreate(RecoveryCaseBase):
    pass

class RecoveryCaseUpdate(BaseModel):
    status: Optional[RecoveryCaseStatus] = None
    failure_category: Optional[str] = None
    recovery_probability: Optional[float] = None
    expected_recovery: Optional[float] = None
    risk_score: Optional[float] = None
    attempt_count: Optional[int] = None
    recovered_amount: Optional[float] = None
    closed_at: Optional[datetime] = None

class RecoveryCaseResponse(RecoveryCaseBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        orm_mode = True