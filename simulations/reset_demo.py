"""
Reset script for ReviveAI demo environment.
Wipes demo state, applies migrations, seeds canonical scenarios, and ensures trained models exist.
"""

import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.seed.seed_demo import seed_database
from ml.training.train import train_recovery_model
from ml.evaluation.evaluate import evaluate_model


def reset_demo_environment():
    print("\n=======================================================")
    print("      RESETTING REVIVEAI DEMO ENVIRONMENT")
    print("=======================================================\n")

    # 1. Seed database with deterministic scenarios
    print("[1/3] Resetting and seeding PostgreSQL database...")
    seed_database()

    # 2. Check / Train ML Model
    model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ml", "models", "model.pkl")
    if not os.path.exists(model_path):
        print("[2/3] Training action-conditioned ML predictor...")
        train_recovery_model(n_samples=5000, seed=42)
    else:
        print("[2/3] ML model verified at:", model_path)

    # 3. Ensure evaluation report exists
    eval_report = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ml", "evaluation", "results.json")
    if not os.path.exists(eval_report):
        print("[3/3] Generating evaluation report...")
        evaluate_model()
    else:
        print("[3/3] Evaluation metrics verified.")

    print("\n>>> DEMO ENVIRONMENT RESET SUCCESSFULLY! Ready for judging walkthrough.")


if __name__ == "__main__":
    reset_demo_environment()
