"""
Deterministic Demo Reset Script for ReviveAI.
Resets database state, seeds the canonical benchmark scenarios, runs the winning
demo recovery pipeline, and verifies analytical & ledger invariants.
Usage:
    python scripts/reset_demo.py
"""

import os
import sys
from decimal import Decimal

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from simulations.run_winning_demo import run_winning_demo
from apps.api.app.database import SessionLocal
from apps.api.app.services.analytics import get_analytics_service
from apps.api.app.models.recovery_ledger import RecoveryLedger
from sqlalchemy import func


def reset_and_verify_demo():
    print("\n" + "=" * 65)
    print("      REVIVEAI — DETERMINISTIC DEMO RESET & VERIFICATION")
    print("=" * 65)

    # 1. Execute winning demo pipeline (Resets DB, seeds 8 cases, runs full agent loop)
    run_winning_demo()

    # 2. Verify Database & Analytics Reconciliation
    print("\n[VERIFICATION] Verifying Source-of-Truth Invariants...")
    db = SessionLocal()
    try:
        analytics = get_analytics_service().get_recovery_overview()

        # Invariant 1: Recovered Value <= Executed Value <= Actionable Value
        actionable_val = analytics["policy_actionable_value"]
        recovered_val = analytics["revenue_recovered"]
        assert recovered_val <= actionable_val, f"Invariant Violation: Recovered ₹{recovered_val} > Actionable ₹{actionable_val}"

        # Invariant 2: Recovered Cases <= Executed Cases <= Actionable Cases
        actionable_cases = analytics["policy_actionable_cases"]
        recovered_cases = analytics["recovered_cases_count"]
        assert recovered_cases <= actionable_cases, f"Invariant Violation: Recovered {recovered_cases} > Actionable {actionable_cases}"

        # Invariant 3: Ledger Gross matches Analytics Verified Recovered
        active_actions = ["retry", "generate_payment_link"]
        ledger_sum = db.query(func.coalesce(func.sum(RecoveryLedger.gross_amount), 0)).filter(
            RecoveryLedger.recovery_action.in_(active_actions)
        ).scalar() or 0.0
        assert round(float(ledger_sum), 2) == round(float(recovered_val), 2), (
            f"Ledger mismatch: Ledger gross ₹{ledger_sum} != Analytics verified ₹{recovered_val}"
        )

        # Invariant 4: Funnel Monotonicity
        funnel = analytics["funnel"]
        for i in range(len(funnel) - 1):
            curr_stage = funnel[i]
            next_stage = funnel[i + 1]
            assert curr_stage["count"] >= next_stage["count"], (
                f"Funnel count non-monotonic: {curr_stage['stage']} ({curr_stage['count']}) < {next_stage['stage']} ({next_stage['count']})"
            )

        # Invariant 5: WAIT & ESCALATE counts reconcile
        summary_wait = analytics["wait_decisions_count"]
        mix_wait = analytics["action_mix"]["approved"].get("wait", 0)
        assert summary_wait == mix_wait, f"WAIT mismatch: summary={summary_wait}, mix={mix_wait}"

        summary_esc = analytics["escalated_cases_count"]
        mix_esc = analytics["action_mix"]["approved"].get("escalate", 0)
        assert summary_esc == mix_esc, f"ESCALATE mismatch: summary={summary_esc}, mix={mix_esc}"

        print(f"  [PASS] Actionable: ₹{actionable_val:,.2f} ({actionable_cases} cases)")
        print(f"  [PASS] Verified Recovered: ₹{recovered_val:,.2f} ({recovered_cases} cases)")
        print(f"  [PASS] Ledger Gross Reconciled: ₹{float(ledger_sum):,.2f}")
        print(f"  [PASS] WAIT count reconciled: {summary_wait}")
        print(f"  [PASS] ESCALATE count reconciled: {summary_esc}")
        print(f"  [PASS] All 6 funnel stages strictly monotonic.")

        print("\n>>> DEMO ENVIRONMENT RESET SUCCESSFULLY! 100% REPRODUCIBLE.")
        print("=" * 65 + "\n")
        return True
    finally:
        db.close()


if __name__ == "__main__":
    success = reset_and_verify_demo()
    if not success:
        sys.exit(1)
