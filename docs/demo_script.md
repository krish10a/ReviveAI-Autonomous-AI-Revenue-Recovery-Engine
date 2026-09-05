# ReviveAI — Judge Walkthrough & Demo Script

This document details the exact 5-minute judge demonstration script for ReviveAI, mapping directly to `python -m simulations.run_winning_demo`.

---

## Pre-Demo Quick Commands
```bash
# 1. Reset database to clean 8 benchmark scenarios
python -m simulations.reset_demo

# 2. Run the automated winning demonstration script
python -m simulations.run_winning_demo

# 3. Start Next.js Frontend Dashboard (optional visual companion)
cd apps/web && npm run dev
```

---

## The 5 Crucial Judge Moments

### MOMENT 1: Verified Recovery Loop -> Financial Ledger
- **Scenario**: `SCENARIO_1_RECOVERABLE` (Case #1, ₹2,499.00, HDFC Bank, soft decline).
- **AI Recommendation**: Calibrated ML predicts candidate probabilities (e.g. `generate_payment_link`: 69.3%).
- **Policy Engine**: Approves action (HDFC bank is healthy, customer active, within retry caps).
- **Bounded Executor**: Executes pre-approved action enum (`generate_payment_link`).
- **Independent Verification**: Checks ground-truth proof of payment capture (does not blindly trust executor success).
- **Ledger Entry**: Append-only entry written to `RecoveryLedger` with itemized costs: Gross: ₹2,499.00, Cost: ₹1.50, Net: ₹2,497.50.

---

### MOMENT 2: Bank Outage Degradation -> Policy Barrier Overrides AI -> Forces WAIT
- **Scenario**: `SCENARIO_5_BANK_OUTAGE` (Kotak Bank, ₹4,500.00).
- **Context**: Kotak rolling failure rate is 100% due to an active gateway outage.
- **AI Recommendation**: Blindly suggests `RETRY` (75% probability based purely on failure code).
- **Policy Barrier Check**: **ALLOWED = False**. Rule `bank_outage_detected` triggers a hard block.
- **Mandated Fallback**: Policy overrides AI and forces **`WAIT`**.
- **Execution**: Schedules deferred re-evaluation. Zero bank retries executed, preventing customer card lockouts and gateway penalty fees.

---

### MOMENT 3: Customer Opt-Out -> Zero Harassment Protection
- **Scenario**: `SCENARIO_3_OPTED_OUT` (Customer has `opted_out = True`).
- **Policy Barrier Check**: **ALLOWED = False**. Rule `customer_opt_out` triggers immediate hard stop.
- **Result**: Zero communications, zero payment links, zero SMS dispatched. Strict customer privacy and compliance maintained.

---

### MOMENT 4: Multi-Step Replanning Loop
- **Scenario**: `SCENARIO_2_MULTI_STEP_RECOVERY` (Expired Card failure).
- **Step 4a**: Action 1 (`RETRY`) executes $\to$ Independent verification confirms **Recovered: False** (expired card cannot be retried).
- **Replanning**: Engine re-evaluates case context with failed prior attempt $\to$ selects `GENERATE_PAYMENT_LINK` (requesting updated card).
- **Step 4b**: Action 2 (`GENERATE_PAYMENT_LINK`) executes $\to$ Verified **Recovered: True**. Ledger entry persisted.

---

### MOMENT 5: Business Impact & A/B Experimentation
- **Methodology**: Identical synthetic population of failed payments partitioned into Control and AI cohorts.
- **Control Strategy**: Naive static gateway retry (repeats the payment without intelligence).
  - Recovery Rate: ~14.0%
- **ReviveAI Strategy**: Closed-loop pipeline with action-conditioned ML & policy guardrails.
  - Recovery Rate: ~65.0% - 70.0%
- **Incremental Business Impact**:
  - **Recovery Improvement**: **+52 percentage points absolute improvement** (multi-seed average across 5 independent runs)
  - **Incremental Net Recovered**: **+₹140,000+**
