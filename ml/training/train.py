"""
Model training script for ReviveAI Action-Conditioned Recovery Predictor.
Trains a calibrated statistical model to predict P(success | context, action).
"""

import os
import sys
import json
from typing import Dict, Any
import joblib
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_auc_score, brier_score_loss, log_loss

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ml.datasets.synthetic_generator import generate_synthetic_recovery_dataset, ACTIONS
from ml.features.features import build_feature_pipeline, NUMERIC_FEATURES, CATEGORICAL_FEATURES


ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)


def train_recovery_model(n_samples: int = 5000, seed: int = 42) -> Dict[str, Any]:
    print(f"Generating synthetic dataset with {n_samples} base samples (seed={seed})...")
    df = generate_synthetic_recovery_dataset(n_samples=n_samples, seed=seed)
    total_records = len(df)
    print(f"Total action-conditioned records: {total_records}")

    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = df["recovered"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=seed, stratify=X["action"]
    )
    print(f"Train size: {len(X_train)}, Test size: {len(X_test)}")

    # 1. Fit Feature Transformer
    feature_pipeline = build_feature_pipeline()
    X_train_trans = feature_pipeline.fit_transform(X_train)
    X_test_trans = feature_pipeline.transform(X_test)

    # 2. Train Base Model & Probability Calibration
    print("Training calibrated classifier...")
    base_model = LogisticRegression(C=1.0, max_iter=1000, random_state=seed)
    calibrated_model = CalibratedClassifierCV(estimator=base_model, cv=5, method="sigmoid")
    calibrated_model.fit(X_train_trans, y_train)

    # 3. Validate on Test Set
    y_pred_proba = calibrated_model.predict_proba(X_test_trans)[:, 1]
    y_pred = calibrated_model.predict(X_test_trans)

    roc_auc = float(roc_auc_score(y_test, y_pred_proba))
    brier = float(brier_score_loss(y_test, y_pred_proba))
    loss = float(log_loss(y_test, y_pred_proba))

    print(f"Validation Metrics on Held-out Test Set:")
    print(f"  ROC-AUC: {roc_auc:.4f}")
    print(f"  Brier Score: {brier:.4f}")
    print(f"  Log Loss: {loss:.4f}")

    # 4. Serialize Artifacts
    model_path = os.path.join(ARTIFACTS_DIR, "model.pkl")
    pipeline_path = os.path.join(ARTIFACTS_DIR, "feature_pipeline.pkl")
    metadata_path = os.path.join(ARTIFACTS_DIR, "metadata.json")

    joblib.dump(calibrated_model, model_path)
    joblib.dump(feature_pipeline, pipeline_path)

    metadata = {
        "model_name": "ReviveAI_ActionConditionedPredictor",
        "version": "2.0.0",
        "algorithm": "CalibratedClassifierCV(LogisticRegression)",
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
        "training_seed": seed,
        "dataset_size": total_records,
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "actions": ACTIONS,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "test_roc_auc": round(roc_auc, 4),
        "test_brier_score": round(brier, 4),
        "model_path": model_path,
        "pipeline_path": pipeline_path,
    }

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Serialized artifacts to {ARTIFACTS_DIR}:")
    print(f"  - model.pkl ({os.path.getsize(model_path)} bytes)")
    print(f"  - feature_pipeline.pkl ({os.path.getsize(pipeline_path)} bytes)")
    print(f"  - metadata.json")

    # Save test partition for evaluation script
    test_data_path = os.path.join(ARTIFACTS_DIR, "test_dataset.pkl")
    joblib.dump((X_test, y_test), test_data_path)

    return metadata


if __name__ == "__main__":
    from typing import Dict, Any
    train_recovery_model()
