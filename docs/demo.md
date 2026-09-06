# ReviveAI — Deterministic Demo Guide

This guide describes how to run and verify the ReviveAI demo environment in a 100% deterministic, reproducible state.

---

## 1. Quick Start Commands

```bash
# 1. Reset the demo environment to deterministic known state (cleans DB, seeds scenarios, runs pipeline)
python scripts/reset_demo.py

# 2. Start the Backend API (FastAPI)
cd apps/api && uvicorn app.main:app --reload --port 8000

# 3. Start the Frontend Dashboard (Next.js)
cd apps/web && npm run dev
```

Visit the dashboard at `http://localhost:3000`.

---

## 2. Key Demo Benchmark Scenarios

The system deterministically provisions 8 canonical benchmark payment failure scenarios:

| # | Scenario Key | Category | Amount | Key Guardrail / Expected Outcome |
|---|---|---|---|---|
| **1** | `SCENARIO_1_RECOVERABLE` | Insufficient Funds | ₹2,499.00 | Soft decline $\rightarrow$ ML recommended retry $\rightarrow$ Allowed $\rightarrow$ Verified Recovered $\rightarrow$ Ledger written |
| **2** | `SCENARIO_2_MULTI_STEP_RECOVERY` | Expired Card | ₹1,299.00 | Multi-step loop: Retry fails $\rightarrow$ Replanned to Payment Link $\rightarrow$ Verified Recovered |
| **3** | `SCENARIO_3_OPTED_OUT` | Customer Opt-Out | ₹1,999.00 | Zero harassment guardrail: Contact strictly blocked $\rightarrow$ Forced STOP |
| **4** | `SCENARIO_4_HIGH_VALUE` | Risk / High-Value | ₹32,000.00 | Exceeds ₹10,000 automated ceiling $\rightarrow$ Forced ESCALATE to human ops |
| **5** | `SCENARIO_5_BANK_OUTAGE` | Bank Gateway Outage | ₹4,500.00 | Kotak rolling failure rate 100% $\rightarrow$ Policy overrides AI retry $\rightarrow$ Forced WAIT |
| **6** | `SCENARIO_6_RETRY_LIMIT` | Retry Limit Cap | ₹2,100.00 | Max retries reached $\rightarrow$ Terminal STOP to prevent card blocking |
| **7** | `SCENARIO_7_ALREADY_CAPTURED` | Already Captured | ₹5,000.00 | Double-charge prevention: Payment captured $\rightarrow$ Instant STOP |
| **8** | `SCENARIO_8_HUMAN_ESCALATION` | Suspicious Activity | ₹28,500.00 | Risk anomaly flag $\rightarrow$ Forced ESCALATE to compliance |

---

## 3. Financial & Operational Invariants

ReviveAI strictly enforces financial accounting and monotonic invariants:
* **Actionable Value $\ge$ Executed Value $\ge$ Verified Value**
* **Actionable Cases $\ge$ Executed Cases $\ge$ Verified Cases**
* **Funnel Stages are Monotonic** (Stage 1 to Stage 6)
* **Operational Summary WAIT / ESCALATE matches Final Action Mix**
* **Ledger Verified Gross equals Dashboard Verified Recoveries**

---

## 4. Synthetic Data Disclosure

> **Synthetic Demo Environment**: All demo scenarios and payment data are synthetic. No real customer funds or production payment credentials are processed.
