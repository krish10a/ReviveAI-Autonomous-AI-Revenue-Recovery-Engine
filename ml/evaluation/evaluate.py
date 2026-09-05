"""
Model evaluation script for ReviveAI.
Computes real statistical metrics on the held-out test dataset, compares against baseline models,
and executes multi-seed experiment simulations.
Persists results to:
  - ml/evaluation/results.json
  - ml/evaluation/model_metrics.json
  - ml/evaluation/multi_seed_experiment.json
  - ml/evaluation/report.md
"""

import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    roc_auc_score,
    precision_recall_curve,
    auc,
    brier_score_loss,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)
from sklearn.calibration import calibration_curve
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

EVAL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
os.makedirs(EVAL_DIR, exist_ok=True)


def evaluate_model():
    model_path = os.path.join(MODELS_DIR, "model.pkl")
    pipeline_path = os.path.join(MODELS_DIR, "feature_pipeline.pkl")
    test_data_path = os.path.join(MODELS_DIR, "test_dataset.pkl")

    if not (os.path.exists(model_path) and os.path.exists(pipeline_path) and os.path.exists(test_data_path)):
        print("Artifacts missing. Running training first...")
        from ml.training.train import train_recovery_model
        train_recovery_model()

    model = joblib.load(model_path)
    feature_pipeline = joblib.load(pipeline_path)
    X_test, y_test = joblib.load(test_data_path)

    X_test_trans = feature_pipeline.transform(X_test)
    y_pred_proba = model.predict_proba(X_test_trans)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)

    # 1. Discrimination Metrics
    roc_auc = float(roc_auc_score(y_test, y_pred_proba))
    precision_arr, recall_arr, _ = precision_recall_curve(y_test, y_pred_proba)
    pr_auc = float(auc(recall_arr, precision_arr))

    precision = float(precision_score(y_test, y_pred, zero_division=0))
    recall = float(recall_score(y_test, y_pred, zero_division=0))
    f1 = float(f1_score(y_test, y_pred, zero_division=0))

    # 2. Calibration & Proper Scoring Rules
    brier = float(brier_score_loss(y_test, y_pred_proba))
    prob_true, prob_pred = calibration_curve(y_test, y_pred_proba, n_bins=5)

    # 3. Confusion Matrix
    cm = confusion_matrix(y_test, y_pred).tolist()

    # 4. Per-action breakdown
    per_action_metrics = {}
    actions = X_test["action"].unique()
    for act in sorted(actions):
        mask = (X_test["action"] == act).values
        if np.sum(mask) > 0:
            y_t_act = y_test[mask]
            y_p_act = y_pred_proba[mask]
            per_action_metrics[act] = {
                "test_count": int(np.sum(mask)),
                "actual_recovery_rate": float(np.mean(y_t_act)),
                "predicted_mean_prob": float(np.mean(y_p_act)),
                "brier_score": float(brier_score_loss(y_t_act, y_p_act)) if len(np.unique(y_t_act)) > 1 else 0.0,
            }

    results = {
        "evaluation_timestamp": str(np.datetime64("now")),
        "model_version": "2.1.0",
        "dataset_version": "synthetic_v2",
        "feature_version": "v2.0",
        "test_sample_size": len(y_test),
        "metrics": {
            "roc_auc": round(roc_auc, 4),
            "pr_auc": round(pr_auc, 4),
            "brier_score": round(brier, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        },
        "confusion_matrix": {
            "tn": cm[0][0],
            "fp": cm[0][1],
            "fn": cm[1][0],
            "tp": cm[1][1],
        },
        "calibration": {
            "bin_predicted": [round(float(x), 4) for x in prob_pred],
            "bin_actual": [round(float(x), 4) for x in prob_true],
        },
        "per_action_performance": per_action_metrics,
    }

    # Save JSON results
    json_path = os.path.join(EVAL_DIR, "results.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)

    # 5. Baseline Comparisons (Section 10 Requirement)
    print("Evaluating baseline comparisons on identical test split...")
    # Baseline A: Dummy prior
    dummy = DummyClassifier(strategy="prior")
    dummy.fit(X_test_trans, y_test)
    y_dummy_prob = dummy.predict_proba(X_test_trans)[:, 1]
    y_dummy_pred = dummy.predict(X_test_trans)

    # Baseline B: Raw uncalibrated Logistic Regression
    uncal_lr = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
    uncal_lr.fit(X_test_trans, y_test)
    y_uncal_prob = uncal_lr.predict_proba(X_test_trans)[:, 1]
    y_uncal_pred = uncal_lr.predict(X_test_trans)

    prec_arr_d, rec_arr_d, _ = precision_recall_curve(y_test, y_dummy_prob)
    prec_arr_u, rec_arr_u, _ = precision_recall_curve(y_test, y_uncal_prob)

    model_metrics = {
        "models": [
            {
                "model_name": "Simple Baseline (Class Prior)",
                "ROC-AUC": round(float(roc_auc_score(y_test, y_dummy_prob)), 4),
                "PR-AUC": round(float(auc(rec_arr_d, prec_arr_d)), 4),
                "Brier": round(float(brier_score_loss(y_test, y_dummy_prob)), 4),
                "precision": round(float(precision_score(y_test, y_dummy_pred, zero_division=0)), 4),
                "recall": round(float(recall_score(y_test, y_dummy_pred, zero_division=0)), 4),
                "F1": round(float(f1_score(y_test, y_dummy_pred, zero_division=0)), 4),
            },
            {
                "model_name": "Logistic Regression (Uncalibrated)",
                "ROC-AUC": round(float(roc_auc_score(y_test, y_uncal_prob)), 4),
                "PR-AUC": round(float(auc(rec_arr_u, prec_arr_u)), 4),
                "Brier": round(float(brier_score_loss(y_test, y_uncal_prob)), 4),
                "precision": round(float(precision_score(y_test, y_uncal_pred, zero_division=0)), 4),
                "recall": round(float(recall_score(y_test, y_uncal_pred, zero_division=0)), 4),
                "F1": round(float(f1_score(y_test, y_uncal_pred, zero_division=0)), 4),
            },
            {
                "model_name": "Calibrated Logistic Regression (Production)",
                "ROC-AUC": round(roc_auc, 4),
                "PR-AUC": round(pr_auc, 4),
                "Brier": round(brier, 4),
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "F1": round(f1, 4),
            }
        ]
    }

    metrics_path = os.path.join(EVAL_DIR, "model_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(model_metrics, f, indent=2)

    # 6. Multi-Seed Simulation Experiment (Section 30 Requirement)
    print("Running multi-seed experiment simulation (seeds 1 through 5)...")
    from apps.api.app.routers.analytics import run_control_vs_ai_experiment
    seeds = [1, 2, 3, 4, 5]
    seed_results = []
    lifts = []
    incremental_revs = []

    for s in seeds:
        exp = run_control_vs_ai_experiment(cases_per_group=100, seed=s)
        lift = exp["impact_metrics"]["recovery_lift_percent"]
        inc_rev = exp["impact_metrics"]["incremental_revenue_recovered"]
        lifts.append(lift)
        incremental_revs.append(inc_rev)
        seed_results.append({
            "seed": s,
            "control_recovery_rate": exp["control_group"]["recovery_rate_percent"],
            "ai_recovery_rate": exp["ai_group"]["recovery_rate_percent"],
            "recovery_lift_percent": lift,
            "incremental_revenue_recovered": inc_rev,
            "net_incremental_revenue": exp["impact_metrics"]["net_incremental_revenue"],
        })

    multi_seed_summary = {
        "num_runs": len(seeds),
        "seeds": seeds,
        "sample_size_per_group_per_run": 100,
        "recovery_lift_percent": {
            "mean": round(float(np.mean(lifts)), 2),
            "std_dev": round(float(np.std(lifts)), 2),
            "min": round(float(np.min(lifts)), 2),
            "max": round(float(np.max(lifts)), 2),
        },
        "incremental_revenue": {
            "mean": round(float(np.mean(incremental_revs)), 2),
            "std_dev": round(float(np.std(incremental_revs)), 2),
            "min": round(float(np.min(incremental_revs)), 2),
            "max": round(float(np.max(incremental_revs)), 2),
        },
        "runs": seed_results,
    }

    multi_seed_path = os.path.join(EVAL_DIR, "multi_seed_experiment.json")
    with open(multi_seed_path, "w") as f:
        json.dump(multi_seed_summary, f, indent=2)

    # 7. Generate Comprehensive Markdown Report
    report_path = os.path.join(EVAL_DIR, "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# ReviveAI Model Evaluation & Multi-Seed Experiment Report\n\n")
        f.write(f"**Evaluated on:** Held-out Test Set ({len(y_test)} action-conditioned samples)\n")
        f.write(f"**Model Version:** `2.1.0` | **Dataset Version:** `synthetic_v2` | **Feature Version:** `v2.0`\n\n")
        f.write("## 1. Model Baseline Comparison\n\n")
        f.write("| Model Architecture | ROC-AUC | PR-AUC | Brier Loss | Precision | Recall | F1-Score |\n")
        f.write("| --- | --- | --- | --- | --- | --- | --- |\n")
        for m in model_metrics["models"]:
            f.write(f"| {m['model_name']} | `{m['ROC-AUC']}` | `{m['PR-AUC']}` | `{m['Brier']}` | `{m['precision']}` | `{m['recall']}` | `{m['F1']}` |\n")

        f.write("\n## 2. Probability Calibration Reliability Table\n\n")
        f.write("| Predicted Probability Bin | Empirical Observed Recovery Rate |\n")
        f.write("| --- | --- |\n")
        for pred, actual in zip(results['calibration']['bin_predicted'], results['calibration']['bin_actual']):
            f.write(f"| {pred:.3f} | {actual:.3f} |\n")

        f.write("\n## 3. Confusion Matrix (Production Model)\n\n")
        f.write(f"- True Negatives (TN): {cm[0][0]}\n")
        f.write(f"- False Positives (FP): {cm[0][1]}\n")
        f.write(f"- False Negatives (FN): {cm[1][0]}\n")
        f.write(f"- True Positives (TP): {cm[1][1]}\n\n")

        f.write("## 4. Multi-Seed Controlled Experiment (5 Runs)\n\n")
        f.write(f"- **Mean Recovery Improvement**: `+{multi_seed_summary['recovery_lift_percent']['mean']} percentage points absolute improvement`\n")
        f.write(f"- **Std Dev**: `±{multi_seed_summary['recovery_lift_percent']['std_dev']} pp`\n")
        f.write(f"- **Improvement Range**: `{multi_seed_summary['recovery_lift_percent']['min']} pp` to `{multi_seed_summary['recovery_lift_percent']['max']} pp`\n")
        f.write(f"- **Mean Incremental ₹ Recovered**: `₹{multi_seed_summary['incremental_revenue']['mean']:,.2f}`\n\n")
        f.write("| Run (Seed) | Control Rate | AI Rate | Improvement (pp) | Incremental ₹ |\n")
        f.write("| --- | --- | --- | --- | --- |\n")
        for r in seed_results:
            f.write(f"| Seed {r['seed']} | {r['control_recovery_rate']}% | {r['ai_recovery_rate']}% | +{r['recovery_lift_percent']} pp | ₹{r['incremental_revenue_recovered']:,.2f} |\n")

    print(f"\n=== EVALUATION RESULTS WRITTEN ===")
    print(f"Results JSON: {json_path}")
    print(f"Model Metrics JSON: {metrics_path}")
    print(f"Multi-Seed Experiment JSON: {multi_seed_path}")
    print(f"Report: {report_path}")
    print(f"ROC-AUC: {roc_auc:.4f} | PR-AUC: {pr_auc:.4f} | Brier: {brier:.4f} | F1: {f1:.4f}")
    return results


if __name__ == "__main__":
    evaluate_model()
