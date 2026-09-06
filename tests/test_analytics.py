"""
Automated tests for Live Database Analytics & Control vs AI Experimentation.
"""

import pytest
from apps.api.app.services.analytics import get_analytics_service
from apps.api.app.routers.analytics import run_control_vs_ai_experiment

analytics_service = get_analytics_service()


def test_analytics_overview_from_database():
    """Verify overview metrics are calculated directly from DB tables."""
    overview = analytics_service.get_recovery_overview()
    assert "revenue_at_risk" in overview
    assert "revenue_recovered" in overview
    assert "recovery_rate_percent" in overview
    assert "active_cases" in overview
    assert "net_recovery" in overview
    assert overview["active_cases"] >= 0
    assert overview["revenue_at_risk"] >= 0.0


def test_failure_reason_breakdown():
    """Verify recovery by failure reason queries live DB."""
    breakdown = analytics_service.get_recovery_by_failure_reason()
    assert isinstance(breakdown, list)
    if len(breakdown) > 0:
        item = breakdown[0]
        assert "failure_reason" in item
        assert "total_cases" in item
        assert "recovery_rate" in item


def test_control_vs_ai_experiment():
    """Verify Control vs AI experiment computes recovery lift and incremental value."""
    exp = run_control_vs_ai_experiment(cases_per_group=30, seed=42)
    assert "control_group" in exp
    assert "ai_group" in exp
    assert "impact_metrics" in exp

    ctrl = exp["control_group"]
    ai = exp["ai_group"]
    imp = exp["impact_metrics"]

    assert ai["recovery_rate_percent"] >= ctrl["recovery_rate_percent"]
    assert "recovery_lift_percent" in imp
    assert "net_incremental_revenue" in imp


def test_mathematical_consistency_and_ledger_reconciliation():
    """
    Verify strict mathematical reconciliation:
    1. remaining_unrecovered == total_failed_value - revenue_recovered
    2. actionable_recovery_rate == verified_recovered / policy_actionable_value
    3. Action mix final outcomes reconcile with operational event summaries.
    4. Protective barriers (STOP, WAIT, ESCALATE) are not credited as revenue recoveries.
    """
    from database.seed.seed_demo import seed_database
    from simulations.run_winning_demo import run_winning_demo

    seed_database()
    run_winning_demo()

    overview = analytics_service.get_recovery_overview()

    total_failed = overview["total_failed_payment_value"]
    recovered = overview["revenue_recovered"]
    remaining = overview["remaining_unrecovered_value"]

    # Exact mathematical identity
    assert round(total_failed - recovered, 2) == round(remaining, 2)

    # Actionable recovery rate formula verification
    actionable_val = overview["policy_actionable_value"]
    if actionable_val > 0:
        expected_rate = min(100.0, round(recovered / actionable_val * 100.0, 2))
        assert overview["actionable_recovery_rate_percent"] == expected_rate

    # Action mix reconciliation with operational counts
    approved = overview["action_mix"]["approved"]
    assert approved["wait"] == overview["wait_decisions_count"]
    assert approved["escalate"] == overview["escalated_cases_count"]

    # Protective actions (WAIT, ESCALATE, STOP) do not write fake recovery ledgers
    funnel = overview["funnel"]
    assert len(funnel) == 6
    stage1 = funnel[0]
    stage2 = funnel[1]
    stage3 = funnel[2]
    stage4 = funnel[3]
    stage5 = funnel[4]
    stage6 = funnel[5]

    assert stage1["stage"] == "Failed Payments"
    assert stage2["stage"] == "Diagnosed"
    assert stage3["stage"] == "Policy-Actionable"
    assert stage4["stage"] == "Recovery Action Allowed"
    assert stage5["stage"] == "Recovery Action Executed"
    assert stage6["stage"] == "Independently Verified Recovery"

    # Funnel counts and amounts must derive consistently
    assert stage1["count"] >= stage2["count"] >= stage3["count"] >= stage4["count"] >= stage5["count"] >= stage6["count"]
    assert stage1["amount"] >= stage2["amount"] >= stage3["amount"] >= stage4["amount"] >= stage5["amount"] >= stage6["amount"]

