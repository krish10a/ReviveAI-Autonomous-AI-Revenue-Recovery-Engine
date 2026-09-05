# ReviveAI — Architectural Design & Defensibility

ReviveAI is built as a closed-loop autonomous revenue recovery system. This document details the architectural decisions, design rationale, and invariants that make the platform defensible under rigorous technical scrutiny.

---

## 1. Architectural Design Choices & "Why" Rationales

### Why Modular Monolith?
Instead of a fragmented microservices setup with distributed state, network latency, and eventual consistency failures, ReviveAI is structured as a **modular monolith** with clear internal service boundaries (Ingestion, Diagnosis, Prediction, Policy, Execution, Verification, Ledger, Analytics). All transactions, audit timelines, and financial entries share a single ACID-compliant PostgreSQL database, guaranteeing immediate consistency, transactional integrity, and zero distributed-transaction overhead.

### Why Action-Conditioned ML?
Traditional churn or recovery models predict a single passive probability $P(\text{recovery} \mid \text{features})$. This is inadequate for decision-making because recovery likelihood depends heavily on **which action is taken**. ReviveAI's action-conditioned pipeline explicitly predicts $P(\text{recovery} \mid \text{state}, \text{action})$ across candidate actions (`retry`, `generate_payment_link`, `send_notification`, `wait`, `escalate`), allowing the optimizer to evaluate the differential lift of each intervention.

### Why Probability Calibration?
Standard classification models (e.g. uncalibrated logistic regression or boosted trees) frequently output overconfident probabilities near 0 or 1. Because ReviveAI uses probabilities directly in downstream financial calculations ($\text{Expected Value} = P \times \text{Amount} - \text{Cost}$), miscalibrated probabilities distort financial decision-making. Using `CalibratedClassifierCV` (sigmoid scaling) ensures that when the model predicts 70% probability, approximately 70% of historical transactions actually recovered in empirical reality.

### Why Expected Value (EV) Optimization?
Recovering a ₹10,000 transaction justifies a higher intervention cost (e.g., human escalation or SMS link) than recovering a ₹100 transaction. ReviveAI optimizes for:
$$\text{EV} = (P(\text{recovery} \mid \text{action}) \times \text{Recoverable Amount}) - \text{Action Cost} - \text{Friction Penalty} - \text{Risk Penalty}$$
This ensures the system acts only when an action has positive net expected value.

### Why Deterministic Policy Engine as an Impassable Barrier?
Machine learning models and LLMs are probabilistic by nature; they cannot guarantee safety constraints 100% of the time. The Policy Engine is an **impassable deterministic barrier**. The ML model only *proposes* actions; it can never directly execute. Every proposed action must pass strict, non-bypassable guardrails:
- Bank degradation detection (rolling failure rate spikes trigger `WAIT`)
- Customer opt-out (zero contact enforcement)
- Retry limits and intervals
- Mandatory human escalation for high-value transactions (> ₹25,000)
- Night quiet hours (21:00 to 08:00)

### Why Bounded Executor?
The executor is strictly restricted to a finite, typed enum (`RecoveryActionType`: `WAIT`, `SEND_NOTIFICATION`, `GENERATE_PAYMENT_LINK`, `RETRY`, `ESCALATE`, `STOP`). Any arbitrary command, refund invocation, or unexpected action payload is instantly rejected with an execution error and logged to the audit timeline.

### Why Independent Verification?
A critical failure of naive recovery systems is trusting `executor.result.success == True` as proof of money. The executor merely reports that an API call or task was dispatched. The **Independent Verification Service** checks independent, ground-truth evidence:
- Real payment provider capture receipts (`payment.captured` webhook)
- Provider state confirmation
Only after verified capture does the system mark the case `RECOVERED`.

### Why Append-Only Recovery Ledger?
Financial numbers must never be overwritten, mutated, or fabricated. Once independent verification confirms recovery, an append-only entry is created in `RecoveryLedger` containing gross recovered amount, itemized execution costs, and exact net recovered amount ($Net = Gross - Cost$), complete with provider reference and timestamp.

### Why Control vs. AI Experiment?
To prevent cherry-picked claims, ReviveAI provides a built-in cohort evaluation that tests the AI recovery strategy against a standard merchant baseline (naive static retry) drawn from the exact same synthetic population. Incremental revenue and recovery lift are calculated mathematically, with multi-seed variance reporting.

---

## 2. Core Execution Pipeline

```
PAYMENT FAILURE
      ↓
[1. SECURE INGESTION]
  • Raw-body HMAC SHA-256 verification
  • X-Razorpay-Event-Id deduplication
  • Out-of-order state machine protection
      ↓
[2. INTELLIGENCE & EV OPTIMIZATION]
  • Rule-based & LLM diagnosis
  • Action-conditioned calibrated ML model
  • Explicit EV computation per candidate action
      ↓
[3. DETERMINISTIC POLICY BARRIER]
  • Bank health evaluation (e.g. Kotak outage forces WAIT)
  • Opt-out & quiet hours check
  • Retry ceiling check
      ↓
[4. BOUNDED EXECUTION]
  • Typed action enum dispatch
  • Explicit mode logging (razorpay_test vs simulation)
      ↓
[5. INDEPENDENT VERIFICATION]
  • Never trusts executor success
  • Validates independent proof of capture
      ↓
[6. APPEND-ONLY FINANCIAL LEDGER]
  • Net = Gross - Cost accounting
  • Persistent audit timeline
      ↓
[7. LIVE ANALYTICS & COHORT IMPACT]
  • PostgreSQL-backed operational overview
  • Control vs. AI incremental lift
```

---

## 3. Supported Execution Modes

1. **`razorpay_test`**: Provider-backed mode using real Razorpay test API credentials and live webhook events.
2. **`simulation`**: High-fidelity, deterministic controlled simulation environment for local judging, testing, and benchmark scenarios.
3. **`manual`**: Operations-assisted human intervention for escalated cases.
