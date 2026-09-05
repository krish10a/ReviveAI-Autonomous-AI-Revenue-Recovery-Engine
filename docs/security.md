# ReviveAI — Security Architecture & Compliance Controls

ReviveAI is architected with financial-grade security, data hygiene, and privacy protections appropriate for processing payment exception events.

---

## 1. Webhook Signature Verification (HMAC SHA-256)

All inbound provider events (e.g. Razorpay webhooks) must arrive with an `X-Razorpay-Signature` header.
- **Raw-Body Verification**: Ingestion processes the exact raw request byte sequence (`await request.body()`) before JSON deserialization to avoid canonicalization attacks.
- **Timing-Safe Digest Comparison**: Computed HMAC-SHA256 hex digest is verified using Python's constant-time `hmac.compare_digest()` to eliminate timing attack vulnerabilities.
- **Header Secrets**: Secret keys are loaded strictly from the environment (`RAZORPAY_WEBHOOK_SECRET`). Unsigned or mis-signed payloads are immediately rejected with HTTP 400.

---

## 2. Idempotency & Out-of-Order State Machine Protection

- **Provider Event Deduplication**: Every event is checked against unique index on `payment_events.razorpay_event_id`. Duplicate deliveries return the existing processing status without re-executing actions or re-mutating case records.
- **One-Way State Transition**: Once a payment transitions to `PaymentStatus.CAPTURED`, it enters a terminal success state. Late-arriving failure events (e.g. out-of-order network latency) are strictly rejected from regressing the payment state back to `failed`.

---

## 3. Zero Cardholder Data (PCI-DSS Scoping)

- **No PAN Storage**: The application stores **zero primary account numbers (PANs)**, zero CVVs, and zero magnetic stripe/chip data.
- **Tokenized & Reference-Only Data**: Only masked tokens, provider payment references (`pay_...`), and standardized decline reason strings are persisted.
- **Database Hygiene**: All migrations enforce strict schema column types with zero sensitive fields.

---

## 4. Secret & Environment Variable Management

- **Git Secret Exclusion**: `.gitignore` strictly excludes `.env`, `.env.*`, `*.pem`, and `*.key`.
- **Placeholder Templates**: `.env.example` contains only benign descriptive placeholders (`your_razorpay_webhook_secret_here`).
- **No Secret Logging**: The logger masks and excludes API keys, secrets, and auth tokens from application logs.

---

## 5. Network, API Security & RBAC

- **CORS Allowlist**: Configured with explicit domain origins (`http://localhost:3000`). Wildcard `*` origins with credentials are fully prohibited.
- **Rate-Limiting Middleware**: Sliding-window IP rate limiter protects against abusive request bursts.
- **Role-Based Access Control (RBAC)**:
  - `VIEWER`: Read-only access to cases, timelines, and analytics. Mutation endpoints rejected with HTTP 403.
  - `OPERATIONS`: Authorized to execute manual case interventions and reviews.
  - `ADMIN`: Authorized to configure merchant policy settings and risk thresholds.
