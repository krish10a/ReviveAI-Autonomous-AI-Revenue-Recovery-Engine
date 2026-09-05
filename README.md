# ReviveAI — Autonomous AI Revenue Recovery Engine

ReviveAI is a production-grade, closed-loop autonomous revenue recovery system for recurring billing and payment failures.

Instead of naive, blind retries or passive notifications, ReviveAI combines **action-conditioned calibrated machine learning**, an **impassable deterministic policy engine**, **bounded execution**, and **independent verification** to maximize net revenue recovery while strictly preventing harassment, bank penalty spams, and unauthorized actions.

---

## Key Pillars

1. **Secure Ingestion & State Machine Integrity**:
   - Razorpay webhook ingestion with raw-body HMAC SHA-256 signature verification.
   - Strict idempotency via `X-Razorpay-Event-Id` and distributed Redis locking.
   - Out-of-order event protection (a late `payment.failed` event never reverts a verified `payment.captured` state).

2. **Action-Conditioned Calibrated ML Pipeline**:
   - Predicts calibrated recovery probabilities $P(\text{recovery} \mid \text{state}, \text{action})$ across candidate actions: `retry`, `send_notification`, `generate_payment_link`, `escalate`, and `wait`.
   - Feature engineering pipeline (`features.py`) with numerical standardization, categorical one-hot encoding, and temporal features.
   - Calibrated classifier (`CalibratedClassifierCV`) providing a modest, realistic predictive signal (ROC-AUC ~0.658, Brier Loss 0.2235) evaluated with PR-AUC, ROC-AUC, and calibration reliability bins.

3. **Deterministic Policy Barrier (Impassable Guardrail)**:
   - The ML/LLM layer **cannot** directly execute actions; it can only propose them.
   - The policy engine enforces hard merchant guardrails:
     - **Bank Degradation Detection**: Rolling failure rate monitoring per bank (e.g. Kotak outage forces `WAIT` and suppresses retries).
     - **Customer Opt-Out**: Strict zero-contact enforcement.
     - **Max Retry Limits & Cooldowns**: Enforces retry caps and intervals.
     - **Night Quiet Hours**: Blocks customer communications between 21:00 and 08:00 local time.
     - **Amount Ceilings**: Mandatory human escalation for high-value transactions (> ₹25,000).

4. **Bounded Execution**:
   - Only pre-approved, strictly typed action enums (`RecoveryActionType`) are executable.
   - Explicit execution modes (`simulation`, `test_live`) with real payment links and schedule queues.

5. **Independent Verification & Financial Ledger**:
   - **Never trusts executor success blindly**: Verifies real fund movement via captured webhook receipts or ground-truth provider state.
   - Writes append-only entries to `RecoveryLedger` with itemized action costs and exact net recovered amounts ($Net = Gross - Cost$).

6. **Executive Business Analytics & Experimentation**:
   - Live PostgreSQL-backed metrics: Revenue at risk, recovered amount, net recovery, cost per rupee recovered, escalation rate, and policy denials.
   - Control vs. AI cohort evaluation demonstrating incremental recovery lift (+52 percentage points absolute improvement, +₹63,100+ net value).
---

## Quickstart & Reproducibility

### Prerequisites
- Python 3.10 - 3.12 (WSL2 / Linux recommended)
- PostgreSQL 15+
- Redis 7+
- Node.js 18+

### Setup
```bash
# Clone and enter directory
cd revive-ai

# Environment setup
cp .env.example .env

# PostgreSQL & Redis connection
# Ensure PostgreSQL is running on localhost:5432 and Redis on localhost:6379
export DATABASE_URL="postgresql://reviveai_user:reviveai_pass@localhost:5432/reviveai"

# Run database migrations
alembic upgrade head
```

---

## Running the Winning Demo Walkthrough

ReviveAI includes an end-to-end deterministic demonstration covering all 8 benchmark scenarios:

```bash
# 1. Reset demo environment to a pristine state
python -m simulations.reset_demo

# 2. Execute the full end-to-end winning demo
python -m simulations.run_winning_demo
```

### Demo Sequence:
- **Step 0**: Deterministic seeding of all 8 canonical benchmark scenarios.
- **Step 1**: AI decision → Policy approval → Bounded execution → Independent verification → `RecoveryLedger` persistence.
- **Step 2**: Bank outage degradation detection on Kotak → AI RETRY rejected → Policy forces `WAIT`.
- **Step 3**: Opted-out customer → Contact policy block → Zero harassment.
- **Step 4**: Multi-step replanning loop (Action 1 fails verification → Contextual replan → Action 2 succeeds).
- **Step 5**: Control vs. AI cohort experiment (+52 percentage points absolute improvement).
- **Step 6**: Live financial and operational analytics read directly from PostgreSQL.

---

## Automated Test Suite

Run the full automated pytest suite (28 test cases covering all subsystems):

```bash
pytest tests/ -v
```

### Test Coverage Breakdown:
- `tests/test_webhook.py`: Valid HMAC, invalid HMAC rejection, duplicate event idempotency, out-of-order safety.
- `tests/test_policy.py`: Bank outage detection, customer opt-out block, retry limits, amount ceilings, captured payment guard.
- `tests/test_ml.py`: Synthetic generator, model training, calibrated prediction probabilities, deterministic reproducibility, adverse context behavior.
- `tests/test_executor_verification.py`: Action enum enforcement, execution mode logging, independent verification ledger generation.
- `tests/test_analytics.py`: Database-backed overview, failure reason breakdown, Control vs. AI experiment metrics.
- `tests/test_e2e_scenarios.py`: All 4 end-to-end canonical closed-loop paths.
- `tests/test_database_integrity.py`: Schema constraints, enum validations, financial ledger correctness.

---

## ML Pipeline: Training & Evaluation

```bash
# 1. Generate synthetic action-conditioned dataset (30,000 records)
python -m ml.datasets.synthetic_generator

# 2. Train calibrated recovery models
python -m ml.training.train

# 3. Generate evaluation report and calibration metrics
python -m ml.evaluation.evaluate
```

Evaluation artifacts are stored in `ml/evaluation/results.json` and `ml/evaluation/report.md`.

---

## Frontend Web Application

The modern Next.js dashboard visualizes live recovery cases, audit timelines, policy decisions, and analytics.

```bash
cd apps/web
npm install
npm run build
npm run dev
```

Dashboard runs at `http://localhost:3000` with API proxying to `http://localhost:8000`.

---

## Project Structure

```
revive-ai/
├── apps/
│   ├── api/                     # FastAPI Modular Backend
│   │   ├── app/
│   │   │   ├── models/          # SQLAlchemy ORM (Payment, RecoveryCase, RecoveryLedger, etc.)
│   │   │   ├── routers/         # Webhook, Recovery, Analytics, Timeline, Simulation
│   │   │   ├── schemas/         # Pydantic validation schemas
│   │   │   ├── services/        # PolicyEngine, Executor, Verification, Prediction, Analytics
│   │   │   └── utils/           # Auth, Security, Helpers
│   │   └── requirements.txt
│   └── web/                     # Next.js 15 Tailwind Dashboard
│       └── src/
│           ├── app/             # App Router pages
│           └── components/      # UI components, Metric cards, Timelines
├── database/
│   ├── alembic/                 # Database migrations (including 07d8491bb812_add_recovery_ledger)
│   └── seed/                    # Deterministic benchmark seed (8 canonical scenarios)
├── ml/
│   ├── datasets/                # Synthetic action-conditioned dataset generator
│   ├── features/                # ColumnTransformer & feature extraction
│   ├── training/                # CalibratedClassifierCV training
│   ├── evaluation/              # Results JSON, classification report, Brier score
│   └── models/                  # Serialized calibrated model artifacts
├── simulations/
│   ├── reset_demo.py            # Pristine demo state reset
│   └── run_winning_demo.py      # End-to-end judge demonstration script
└── tests/                       # 28-test automated pytest suite
```

---

## License

MIT License.
