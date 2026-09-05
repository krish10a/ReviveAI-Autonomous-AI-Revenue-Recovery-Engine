# ReviveAI — Autonomous AI Revenue Recovery Engine

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16%20Turbopack-black.svg)](https://nextjs.org/)
[![Tests](https://img.shields.io/badge/tests-42%20passed%20%7C%20100%25-brightgreen.svg)](https://docs.pytest.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **ReviveAI** is a production-grade, closed-loop autonomous revenue recovery system for recurring billing and payment failures.

Instead of naive blind retries or passive customer spam, ReviveAI combines **action-conditioned calibrated machine learning**, an **impassable deterministic policy engine**, **bounded execution**, and **independent financial verification** to maximize net revenue recovery while strictly preventing harassment, bank penalty spams, and unauthorized merchant actions.

---

## 📐 System Architecture

```
                                  [ Razorpay Webhook Ingestion ]
                                                │
                                                ▼
                                    [ HMAC Signature & Lock ]
                                                │
                                                ▼
                                    [ Failure Diagnosis Engine ]
                                                │
                                                ▼
                            [ Action-Conditioned ML Predictor ]
                        Calculates P(recovery | state, action) & EV
                                                │
                                                ▼
                             ⚠️ [ DETERMINISTIC POLICY BARRIER ] ⚠️
                           Enforces Merchant Limits, Bank Outages,
                             Quiet Hours, Opt-Outs & Ceilings
                                                │
                                                ▼
                                    [ Bounded Action Executor ]
                                 Strict Enums, Simulation/Live
                                                │
                                                ▼
                                 [ Independent Verification ]
                               Confirms Real Movement of Funds
                                                │
                                                ▼
                                    [ Append-Only Ledger ]
                            Net Recovery = Gross Amount - Costs
```

---

## 🌟 Key Architecture Pillars

### 1. Secure Ingestion & State Machine Integrity
* **Webhook Authentication**: Razorpay webhook ingestion with raw-body HMAC SHA-256 signature verification.
* **Strict Idempotency**: Distributed locking via `X-Razorpay-Event-Id` prevents duplicate processing.
* **State Machine Monotonicity**: Late or out-of-order `payment.failed` events are rejected if state is already `payment.captured`.

### 2. Action-Conditioned Calibrated ML Pipeline
* **Probabilistic Scoring**: Predicts calibrated recovery probability $P(\text{recovery} \mid \text{state}, \text{action})$ across candidate actions (`retry_now`, `retry_later`, `payment_link`, `notification`, `escalate`, `wait`).
* **Expected Net Value (EV) Optimization**:
  $$E[\text{Net Recovery}] = P(\text{recovery} \mid s, a) \times \text{Amount} - \text{Cost}(a)$$
* **Feature Engineering (`ml/features/features.py`)**: Standardized numeric features (amounts, customer tenure, history, bank failure rates) + one-hot encoded categorical features.
* **Calibrated Classification**: `CalibratedClassifierCV` ensures output probabilities reliably match true empirical recovery frequencies (ROC-AUC `0.6415`, PR-AUC `0.6586`, Brier Loss `0.2237`).

### 3. Impassable Deterministic Policy Engine (Guardrail Barrier)
* **Zero Direct ML/LLM Execution**: ML models propose actions; the policy engine has final veto power.
* **Hard Merchant Guardrails**:
  - **Bank Outage Detection**: Real-time rolling failure rate monitoring per bank (e.g. Kotak outage forces `WAIT` and suppresses retries).
  - **Customer Opt-Out**: Strict zero-contact policy enforcement.
  - **Retry Limits & Cooldowns**: Enforces retry attempt caps and minimum interval gaps.
  - **Night Quiet Hours**: Blocks customer-facing communications between 21:00 and 08:00 local merchant time.
  - **High-Value Ceilings**: Mandatory human escalation for high-value transactions (> ₹25,000).

### 4. Bounded Execution Environment
* Strictly typed action enums (`RecoveryActionType`) prevent arbitrary payload generation.
* Dual execution modes: `simulation` (deterministic demo) and `test_live` (real Razorpay test-mode API integration).

### 5. Independent Verification & Financial Ledger
* **Trust Nothing**: Never relies solely on executor return status.
* **Verification Engine**: Verifies actual movement of funds via webhook receipts or ground-truth provider state.
* **Immutable Accounting**: Append-only entries written to `RecoveryLedger` with itemized action costs and exact net recovered amounts ($Net = Gross - Cost$).

### 6. Control vs. AI Cohort Experimentation & Analytics
* Live PostgreSQL-backed metrics: Revenue at risk, recovered amount, net recovery, cost per rupee recovered, escalation rate, and policy denials.
* Controlled experiment framework demonstrating **+52 percentage points absolute recovery lift** (+₹63,100+ net value created per 1,000 cases).

---

## 📊 Benchmark & Multi-Seed Experiment Results

Evaluated across a 5-run controlled synthetic benchmark (600 held-out test cases per run):

| Run | Strategy | Recovery Rate | Incremental Lift | Net Revenue Recovered |
| :--- | :--- | :--- | :--- | :--- |
| **Control** | Static Gateway Retry | `14.0%` | Baseline | ₹25,609.80 |
| **ReviveAI** | Action-Conditioned AI Pipeline | **`66.0%`** | **`+52.0 pp`** | **`₹165,812.11`** |

### Probability Calibration Bins

| Predicted Probability Bin | Observed Empirical Recovery Rate |
| :---: | :---: |
| `0.180` | `0.000` |
| `0.302` | `0.243` |
| `0.524` | `0.604` |
| `0.668` | `0.661` |

---

## ⚡ Quickstart Guide

### Prerequisites
- **Python**: 3.10 – 3.12
- **Node.js**: 18+
- **Database**: PostgreSQL 15+ or SQLite (local testing)
- **Cache/Queue**: Redis 7+

### 1. Installation & Environment Setup
```bash
# Clone the repository
git clone https://github.com/krish10a/ReviveAI-Autonomous-AI-Revenue-Recovery-Engine.git
cd ReviveAI-Autonomous-AI-Revenue-Recovery-Engine/revive-ai

# Create environment configuration
cp .env.example .env
```

### 2. Database Migrations & Seeding
```bash
# Run database migrations
alembic upgrade head

# Reset and seed the pristine 8-scenario demo dataset
python -m simulations.reset_demo
```

### 3. Run the Winning Demo Walkthrough
Execute the end-to-end judge demonstration script covering all 8 benchmark scenarios:

```bash
python -m simulations.run_winning_demo
```

---

## 🧪 Automated Test Suite

Run the full pytest suite (42 unit, integration, and invariant tests):

```bash
pytest tests/ -v
```

### Test Coverage Summary:
- **`tests/test_webhook.py`**: HMAC SHA-256 signature verification, invalid signature rejection, idempotency locking, out-of-order event protection.
- **`tests/test_policy.py`**: Bank outage detection, customer opt-out block, retry limits, amount ceilings, night quiet hours.
- **`tests/test_ml.py`**: Synthetic data generator, model training, calibrated prediction probabilities, deterministic reproducibility, adverse context behavior.
- **`tests/test_executor_verification.py`**: Action enum enforcement, execution mode logging, independent verification ledger generation.
- **`tests/test_analytics.py`**: Overview metrics, failure reason breakdown, Control vs. AI cohort evaluation.
- **`tests/test_invariants.py`**: Policy veto invariants, monotonic state transitions, duplicate recovery prevention.
- **`tests/test_e2e_scenarios.py`**: End-to-end closed-loop scenario validation.

---

## 💻 Running the Services Locally

### Backend API (FastAPI)
```bash
# Start backend API server on http://localhost:8000
python -m uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8000 --reload
```

- **Interactive API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check Endpoint**: [http://localhost:8000/health](http://localhost:8000/health)

### Frontend Dashboard (Next.js 16)
```bash
cd apps/web
npm install
npm run dev
```

- **Dashboard UI**: [http://localhost:3000](http://localhost:3000)

---

## 📂 Project Directory Structure

```
revive-ai/
├── apps/
│   ├── api/                     # FastAPI Modular Backend
│   │   ├── app/
│   │   │   ├── models/          # SQLAlchemy ORM (Payment, RecoveryCase, RecoveryLedger)
│   │   │   ├── routers/         # Webhook, Recovery, Analytics, Timeline, Simulation
│   │   │   ├── schemas/         # Pydantic validation schemas
│   │   │   ├── services/        # PolicyEngine, Executor, Verification, Prediction, Analytics
│   │   │   └── main.py          # FastAPI application entrypoint
│   │   └── requirements.txt
│   └── web/                     # Next.js 16 Dashboard (Turbopack + Tailwind CSS)
│       └── src/
│           ├── app/             # Next.js App Router pages
│           └── components/      # Metrics, Audit Timeline, Decision Explainer, Batch Simulator
├── database/
│   ├── alembic/                 # Alembic Database Migrations
│   └── seed/                    # Deterministic Demo Seeding (8 canonical scenarios)
├── ml/
│   ├── datasets/                # Action-conditioned dataset generator
│   ├── features/                # ColumnTransformer & feature extraction
│   ├── training/                # CalibratedClassifierCV training
│   ├── evaluation/              # Metrics JSON, classification report, calibration tables
│   └── models/                  # Serialized calibrated model artifacts
├── simulations/
│   ├── reset_demo.py            # Pristine demo state reset script
│   └── run_winning_demo.py      # End-to-end 8-scenario judge demonstration
├── tests/                       # 42-test automated pytest suite
├── docker-compose.yml           # Production container composition
├── README.md                    # Project documentation
└── LICENSE                      # MIT License
```

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.
