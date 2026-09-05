# ReviveAI Model Evaluation & Multi-Seed Experiment Report

**Evaluated on:** Held-out Test Set (600 action-conditioned samples)
**Model Version:** `2.1.0` | **Dataset Version:** `synthetic_v2` | **Feature Version:** `v2.0`

## 1. Model Baseline Comparison

| Model Architecture | ROC-AUC | PR-AUC | Brier Loss | Precision | Recall | F1-Score |
| --- | --- | --- | --- | --- | --- | --- |
| Simple Baseline (Class Prior) | `0.5` | `0.7833` | `0.2456` | `0.5667` | `1.0` | `0.7234` |
| Logistic Regression (Uncalibrated) | `0.7324` | `0.7629` | `0.2046` | `0.6739` | `0.8206` | `0.7401` |
| Calibrated Logistic Regression (Production) | `0.6415` | `0.6586` | `0.2237` | `0.6452` | `0.8235` | `0.7235` |

## 2. Probability Calibration Reliability Table

| Predicted Probability Bin | Empirical Observed Recovery Rate |
| --- | --- |
| 0.180 | 0.000 |
| 0.302 | 0.243 |
| 0.524 | 0.604 |
| 0.668 | 0.661 |

## 3. Confusion Matrix (Production Model)

- True Negatives (TN): 106
- False Positives (FP): 154
- False Negatives (FN): 60
- True Positives (TP): 280

## 4. Multi-Seed Controlled Experiment (5 Runs)

- **Mean Recovery Improvement**: `+52.0 percentage points absolute improvement`
- **Std Dev**: `±4.94 pp`
- **Improvement Range**: `45.0 pp` to `56.0 pp`
- **Mean Incremental ₹ Recovered**: `₹142,390.44`

| Run (Seed) | Control Rate | AI Rate | Improvement (pp) | Incremental ₹ |
| --- | --- | --- | --- | --- |
| Seed 1 | 14.0% | 70.0% | +56.0 pp | ₹165,812.11 |
| Seed 2 | 11.0% | 67.0% | +56.0 pp | ₹143,199.48 |
| Seed 3 | 9.0% | 65.0% | +56.0 pp | ₹146,517.42 |
| Seed 4 | 14.0% | 59.0% | +45.0 pp | ₹135,292.65 |
| Seed 5 | 14.0% | 61.0% | +47.0 pp | ₹121,130.56 |
