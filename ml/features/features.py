"""
Feature transformation pipeline for ReviveAI Recovery Engine.
"""

from typing import List, Dict, Any
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline


NUMERIC_FEATURES = [
    "amount",
    "hour",
    "day_of_week",
    "customer_tenure",
    "previous_successful_payments",
    "previous_failed_payments",
    "previous_recoveries",
    "retry_count",
    "time_since_failure",
    "failure_streak",
    "amount_relative_to_customer_history",
    "recent_bank_failure_rate",
    "historical_success_rate",
]

CATEGORICAL_FEATURES = [
    "payment_method",
    "bank",
    "failure_category",
    "merchant_category",
    "action",
]


def build_feature_pipeline() -> ColumnTransformer:
    """Build a composable scikit-learn feature preprocessor."""
    transformer = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
        ],
        remainder="drop",
    )
    return transformer


def extract_features_from_case(case_context: Dict[str, Any], action: str) -> pd.DataFrame:
    """Transform raw recovery case context and candidate action into a single-row DataFrame."""
    amount = float(case_context.get("amount", 2000.0))
    customer_history = case_context.get("customer", {})

    prev_success = float(customer_history.get("previous_successful_payments", 5))
    prev_failed = float(customer_history.get("previous_failed_payments", 1))
    total = prev_success + prev_failed + 1.0

    row = {
        "amount": amount,
        "payment_method": str(case_context.get("payment_method", "card")).lower(),
        "bank": str(case_context.get("bank", "HDFC")),
        "failure_category": str(case_context.get("failure_category", "insufficient_funds")),
        "merchant_category": str(case_context.get("merchant_category", "ecommerce")),
        "hour": int(case_context.get("hour", 14)),
        "day_of_week": int(case_context.get("day_of_week", 2)),
        "customer_tenure": float(customer_history.get("tenure_days", 180)),
        "previous_successful_payments": prev_success,
        "previous_failed_payments": prev_failed,
        "previous_recoveries": float(customer_history.get("previous_recoveries", 1)),
        "retry_count": int(case_context.get("retry_count", 0)),
        "time_since_failure": float(case_context.get("time_since_failure", 15.0)),
        "failure_streak": int(case_context.get("failure_streak", 1)),
        "amount_relative_to_customer_history": float(case_context.get("amount_relative", 1.0)),
        "recent_bank_failure_rate": float(case_context.get("recent_bank_failure_rate", 0.08)),
        "historical_success_rate": (prev_success + 1.0) / (total + 1.0),
        "action": str(action).lower(),
    }
    return pd.DataFrame([row])
