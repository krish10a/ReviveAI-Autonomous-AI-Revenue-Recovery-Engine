# ReviveAI — Model Evaluation & Experimentation Methodology

This document outlines the machine learning architecture, dataset generation, probability calibration, and experimental evaluation methodology for ReviveAI.

> **Methodological Disclaimer**: All training data, ground-truth outcomes, and experimental evaluations described herein are generated using a controlled synthetic simulation framework with deterministic seeds. These results demonstrate algorithmic correctness, internal consistency, and closed-loop behavior in a simulated environment; they are **not a claim of production causal lift** on unobserved live merchant transactions.

---

## 1. Action-Conditioned Dataset Generation

- **Base Population**: 5,000 unique failed payment instances expanded across 6 candidate recovery actions = **30,000 action-conditioned training samples**.
- **Deterministic Seed**: Seed `42` (`ml/datasets/synthetic_generator.py`).
- **Feature Schema**:
  - *Numerical Features*: `amount`, `customer_tenure_months`, `prior_success_rate`, `attempt_count`, `hour_of_day`, `day_of_week`.
  - *Categorical Features*: `payment_method` (UPI, Card, NetBanking), `bank` (HDFC, SBI, ICICI, Kotak, Axis), `failure_category` (insufficient_funds, expired_card, technical_error, bank_outage, authentication_failed), `action` (retry, wait, send_notification, generate_payment_link, escalate, stop).
- **Ground-Truth Data Generating Process**:
  The outcome simulator models realistic financial mechanics independent of the training model:
  - Expired cards have 0% recovery via direct retry, but high recovery via payment link.
  - Bank outages (e.g. Kotak degradation) have near-zero recovery on immediate retry, but recover once the bank health stabilizes after a wait.
  - High customer tenure and high historical success rate increase baseline willingness to complete alternative payment links.

---

## 2. Model Architecture & Baselines

We compare three model architectures on the exact same held-out test split (20% split, 6,000 samples):

| Model Architecture | ROC-AUC | PR-AUC | Brier Loss | Precision | Recall | F1-Score | Notes |
|---|---|---|---|---|---|---|---|
| **Class Prior Baseline** | `0.5000` | `0.7821` | `0.2459` | `0.5642` | `1.0000` | `0.7214` | Naive majority class prediction |
| **Logistic Regression (Uncalibrated)** | `0.6601` | `0.6717` | `0.2220` | `0.6562` | `0.8384` | `0.7362` | Standard L2 regularized linear model |
| **Calibrated Logistic Regression (Production)** | `0.6580` | `0.6703` | `0.2235` | `0.6537` | `0.8372` | `0.7342` | 5-fold Sigmoid Platt scaling |

> **Predictive Signal Note**: An ROC-AUC of `0.6580` (~0.66) represents a modest, realistic predictive signal on transaction outcome data. Rather than overclaiming extreme discrimination accuracy, ReviveAI combines well-calibrated probabilities (Brier Loss: `0.2235`) with Expected Value optimization ($EV = P \times \text{Amount} - \text{Cost}$) and hard policy guardrails.

---

## 3. Probability Calibration Analysis

Because predicted probabilities directly drive Expected Value calculations:
$$\text{EV} = P(\text{recovery}) \times \text{Amount} - \text{Cost}$$
probabilities must reflect empirical observed frequency.

### Reliability Table (5 Probability Bins):
| Predicted Probability Bin | Empirical Observed Recovery Rate | Calibration Difference |
|---|---|---|
| **0.175** | **0.158** | -0.017 |
| **0.334** | **0.321** | -0.013 |
| **0.518** | **0.509** | -0.009 |
| **0.672** | **0.684** | +0.012 |
| **0.841** | **0.853** | +0.012 |

The maximum calibration error across all bins is less than 2 percentage points ($\Delta < 0.02$), validating that predicted probabilities are statistically reliable for financial optimization.

---

## 4. Multi-Seed Controlled Experiment

To avoid cherry-picking a single lucky trial, the Control vs. AI cohort evaluation was executed across 5 independent random seeds (Seeds 1 through 5) with 100 cases per group per run:

- **Control Strategy**: Naive static gateway retry (repeats the payment without context).
- **ReviveAI Strategy**: Full closed-loop engine (Diagnosis $\to$ Calibrated ML $\to$ Policy Barrier $\to$ Bounded Execution $\to$ Independent Verification).

### Multi-Seed Summary:
- **Mean Recovery Improvement**: **+52.0 percentage points absolute improvement**
- **Improvement Standard Deviation**: **±4.94 percentage points**
- **Improvement Range**: **45.0 to 56.0 percentage points**
- **Mean Incremental Revenue Recovered**: **₹142,390.44** (Std Dev: ₹14,619.32)

| Run (Seed) | Control Rate | AI Rate | Recovery Improvement (pp) | Incremental ₹ Recovered | Net Incremental Value |
|---|---|---|---|---|---|
| **Seed 1** | 14.0% | 70.0% | **+56.0 pp** | ₹165,812.11 | ₹165,736.11 |
| **Seed 2** | 11.0% | 67.0% | **+56.0 pp** | ₹143,199.48 | ₹143,120.98 |
| **Seed 3** | 9.0% | 65.0% | **+56.0 pp** | ₹146,517.42 | ₹146,438.42 |
| **Seed 4** | 14.0% | 59.0% | **+45.0 pp** | ₹135,292.65 | ₹135,219.65 |
| **Seed 5** | 14.0% | 61.0% | **+47.0 pp** | ₹121,130.56 | ₹121,059.06 |

---

## 5. Artifact Provenance & Versioning

- **Model Artifact**: `ml/models/model.pkl`
- **Feature Pipeline Artifact**: `ml/models/feature_pipeline.pkl`
- **Model Version**: `2.1.0`
- **Dataset Version**: `synthetic_v2`
- **Feature Version**: `v2.0`
- **Evaluation Outputs**: `ml/evaluation/results.json`, `ml/evaluation/model_metrics.json`, `ml/evaluation/multi_seed_experiment.json`, `ml/evaluation/report.md`.
