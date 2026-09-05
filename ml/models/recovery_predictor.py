"""
ML model for predicting action-conditioned recovery probability P(success | context, action).
Loads serialized artifacts (model.pkl, feature_pipeline.pkl) and scores candidate actions.
"""

import os
import sys
import logging
from typing import Dict, Any, List
import joblib
import numpy as np
import pandas as pd

from ..features.features import extract_features_from_case
from ..datasets.synthetic_generator import ACTIONS

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.dirname(os.path.abspath(__file__))


class RecoveryPredictor:
    def __init__(self):
        self.model = None
        self.feature_pipeline = None
        self.metadata = None
        self.is_trained = False
        self.action_types = ACTIONS
        self.load_artifacts()

    def load_artifacts(self) -> bool:
        """Load trained model and pipeline artifacts if available."""
        model_path = os.path.join(MODELS_DIR, "model.pkl")
        pipeline_path = os.path.join(MODELS_DIR, "feature_pipeline.pkl")
        metadata_path = os.path.join(MODELS_DIR, "metadata.json")

        if os.path.exists(model_path) and os.path.exists(pipeline_path):
            try:
                self.model = joblib.load(model_path)
                self.feature_pipeline = joblib.load(pipeline_path)
                if os.path.exists(metadata_path):
                    import json
                    with open(metadata_path, "r") as f:
                        self.metadata = json.load(f)
                self.is_trained = True
                logger.info(f"Successfully loaded ML model artifacts from {MODELS_DIR}")
                return True
            except Exception as e:
                logger.error(f"Failed to load model artifacts: {e}", exc_info=True)
                self.is_trained = False
                return False
        else:
            logger.warning(f"Model artifacts not found in {MODELS_DIR}. Inference will use fallback.")
            self.is_trained = False
            return False

    def predict_recovery_probabilities(self, case_context: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Produce mathematically sound probabilities for candidate actions:
        P(success | context, action) for all actions in ACTIONS.
        """
        # If trained model is present, score all actions via the calibrated model
        if self.is_trained and self.model is not None and self.feature_pipeline is not None:
            results = {}
            for action in self.action_types:
                df_single = extract_features_from_case(case_context, action)
                X_trans = self.feature_pipeline.transform(df_single)
                prob = float(self.model.predict_proba(X_trans)[0, 1])
                prob = float(np.clip(prob, 0.01, 0.99))
                results[action] = {
                    "probability": round(prob, 4),
                    "model_version": self.metadata.get("version", "2.0.0") if self.metadata else "2.0.0",
                    "source": "calibrated_ml_model",
                }
            return results

        # Explicitly named fallback only if model artifact not yet trained
        return self._heuristic_fallback(case_context)

    def _heuristic_fallback(self, case_context: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Documented deterministic fallback used strictly if model artifacts are uninitialized."""
        amount = float(case_context.get("amount", 2000.0))
        fc = str(case_context.get("failure_category", "insufficient_funds")).lower()

        base = {
            "retry_now": 0.35,
            "retry_later": 0.65,
            "payment_link": 0.70,
            "notification": 0.50,
            "escalate": 0.85,
            "wait": 0.40,
        }

        if fc == "expired_card":
            base["retry_now"] = 0.05
            base["retry_later"] = 0.05
            base["payment_link"] = 0.85
        elif fc == "bank_declined":
            base["retry_now"] = 0.15
            base["wait"] = 0.75

        return {
            act: {
                "probability": round(prob, 2),
                "model_version": "fallback_heuristic",
                "source": "fallback_heuristic",
            }
            for act, prob in base.items()
        }


# Singleton instance
recovery_predictor = RecoveryPredictor()


def get_recovery_predictor() -> RecoveryPredictor:
    return recovery_predictor
