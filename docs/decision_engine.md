# ReviveAI — Decision Engine & Policy Guardrail Specification

The ReviveAI Decision Engine selects and authorizes recovery interventions by balancing statistical recovery probability, financial cost, customer friction, and merchant business guardrails.

---

## 1. Expected Value (EV) Formulation

For every payment exception, the engine computes the Net Expected Value for each candidate action $a \in \mathcal{A}$:

$$\text{EV}(a) = \left( P(\text{recovery} \mid \mathbf{x}, a) \times \text{Recoverable Amount} \right) - C(a) - F(a) - R(a)$$

Where:
- $P(\text{recovery} \mid \mathbf{x}, a)$: Calibrated ML probability given case context $\mathbf{x}$ and candidate action $a$.
- $\text{Recoverable Amount}$: The gross principal value of the failed payment.
- $C(a)$: Direct financial execution cost of the action:
  - `RETRY`: ₹0.50 (gateway processing fee)
  - `SEND_NOTIFICATION`: ₹0.20 (SMS/WhatsApp delivery cost)
  - `GENERATE_PAYMENT_LINK`: ₹1.50 (hosted link generation & notification)
  - `ESCALATE`: ₹25.00 (estimated merchant support labor)
  - `WAIT` / `STOP`: ₹0.00
- $F(a)$: Friction penalty (customer annoyance discount, highest for unsolicited repeated messages).
- $R(a)$: Risk penalty (chargeback or card network penalty discount).

---

## 2. Deterministic Policy Guardrail Engine

The Policy Engine serves as an **impassable barrier**. Even if an action yields the highest mathematical EV, it cannot be executed if it violates any of the following deterministic rules:

1. **Captured Payment Guard**: If the payment is already captured, all recovery actions are blocked.
2. **Customer Opt-Out (Zero Harassment)**: If `customer.opted_out == True`, any communication or link action is strictly denied (`HARD_BLOCK`).
3. **Bank Outage & Degradation Detection**:
   - Rolling failure rate is tracked per issuing/acquiring bank.
   - If a bank's rolling failure rate exceeds threshold (e.g. Kotak Bank failure rate = 100%), automated retries are denied and the engine mandates `WAIT`.
4. **Retry Limits & Interval Cooldowns**:
   - Maximum of 3 retry attempts per payment case.
   - Cooldown interval of at least 4 hours between retry executions.
5. **Amount Ceilings & Human Escalation**:
   - Transactions exceeding ₹25,000 cannot be automatically processed via unverified retry; mandatory escalation to human operations is enforced.
6. **Night Contact Window**:
   - Customer communications are suppressed between 21:00 and 08:00 local merchant time.

---

## 3. Replanning Loop on Verification Failure

When an executed action does not result in confirmed fund capture:
1. Executor returns execution details.
2. Independent Verification validates provider state $\to$ finds no capture event.
3. Case status remains `OPEN` or transitions to replanning state.
4. Engine re-diagnoses and generates secondary action plan (e.g., if `RETRY` failed due to an expired card, replanning selects `GENERATE_PAYMENT_LINK`).
5. Upon successful second action capture, recovery is verified and logged to `RecoveryLedger`.
