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
