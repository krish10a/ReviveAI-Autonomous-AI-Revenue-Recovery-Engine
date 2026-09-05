"""
Automated tests for Machine Learning Pipeline.
Tests synthetic dataset generation, training, artifact serialization, inference sanity, and evaluation metrics.
"""

import os
import json
import pytest
import numpy as np
from ml.datasets.synthetic_generator import generate_synthetic_recovery_dataset, ACTIONS
from ml.models.recovery_predictor import get_recovery_predictor
from ml.training.train import train_recovery_model
from ml.evaluation.evaluate import evaluate_model


def test_synthetic_data_generation():
    """Verify synthetic dataset properties."""
    df = generate_synthetic_recovery_dataset(n_samples=200, seed=42)
    assert len(df) == 200 * len(ACTIONS)
    assert "amount" in df.columns
    assert "action" in df.columns
    assert "recovered" in df.columns
    assert df["recovered"].isin([0, 1]).all()


def test_model_training_and_artifacts():
    """Verify model training produces required artifacts."""
    meta = train_recovery_model(n_samples=500, seed=42)
    assert meta["model_name"] == "ReviveAI_ActionConditionedPredictor"
    assert os.path.exists(meta["model_path"])
    assert os.path.exists(meta["pipeline_path"])


def test_prediction_probabilities_validity():
    """Sanity test: all action predictions must be valid probabilities in [0, 1]."""
    predictor = get_recovery_predictor()
    context = {
        "amount": 3500.0,
        "payment_method": "card",
        "bank": "HDFC",
        "failure_category": "insufficient_funds",
        "merchant_category": "ecommerce",
        "hour": 14,
        "day_of_week": 2,
        "customer": {"tenure_days": 120, "previous_successful_payments": 10, "previous_failed_payments": 1}
    }
    probs = predictor.predict_recovery_probabilities(context)
    for act in ACTIONS:
        assert act in probs
        p = probs[act]["probability"]
        assert 0.0 <= p <= 1.0


def test_deterministic_reproducibility():
    """Identical input context must produce identical probability predictions."""
    predictor = get_recovery_predictor()
    context = {
        "amount": 2000.0,
        "payment_method": "upi",
        "bank": "ICICI",
        "failure_category": "insufficient_funds",
        "merchant_category": "saas_subscription",
        "hour": 10,
        "day_of_week": 1,
        "customer": {"tenure_days": 300, "previous_successful_payments": 25, "previous_failed_payments": 0}
    }
    p1 = predictor.predict_recovery_probabilities(context)
    p2 = predictor.predict_recovery_probabilities(context)
    for act in ACTIONS:
        assert p1[act]["probability"] == p2[act]["probability"]


def test_adverse_context_behavior():
    """Extreme adverse context (expired card) must severely lower retry probability compared to payment link."""
    predictor = get_recovery_predictor()
    context_expired = {
        "amount": 2500.0,
        "payment_method": "card",
        "bank": "HDFC",
        "failure_category": "expired_card",
        "merchant_category": "ecommerce",
        "hour": 14,
        "day_of_week": 2,
        "customer": {"tenure_days": 50, "previous_successful_payments": 0, "previous_failed_payments": 5}
    }
    probs = predictor.predict_recovery_probabilities(context_expired)
    assert probs["payment_link"]["probability"] > probs["retry_now"]["probability"]


def test_evaluation_metrics_persisted():
    """Verify that evaluate_model persists valid ROC-AUC and calibration results."""
    eval_results = evaluate_model()
    metrics = eval_results["metrics"]
    assert "roc_auc" in metrics
    assert "brier_score" in metrics
    assert metrics["roc_auc"] > 0.50
    assert metrics["brier_score"] < 0.35
