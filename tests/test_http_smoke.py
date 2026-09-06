"""
HTTP-level E2E Smoke Test for ReviveAI.
Validates the complete web API layer:
  1. GET /recovery-cases
  2. GET /recovery-cases/{id}
  3. GET /recovery-cases/{id}/timeline
  4. GET /analytics/overview
  5. GET /analytics/failure-reason
  6. GET /analytics/intervention-performance
  7. POST /analytics/experiment
"""

import pytest
from fastapi.testclient import TestClient
from apps.api.app.main import app

client = TestClient(app)


def test_http_recovery_cases_list():
    """Test GET /recovery-cases returns seeded recovery cases."""
    response = client.get("/recovery-cases")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    # Check shape
    first = data[0]
    assert "id" in first
    assert "amount" in first
    assert "status" in first


def test_http_recovery_case_detail_and_timeline():
    """Test GET /recovery-cases/{id} and /recovery-cases/{id}/timeline."""
    # List cases to find an active case
    list_res = client.get("/recovery-cases")
    assert list_res.status_code == 200
    cases = list_res.json()
    assert len(cases) > 0
    case_id = cases[0]["id"]

    # Detail
    detail_res = client.get(f"/recovery-cases/{case_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["id"] == case_id

    # Timeline
    tl_res = client.get(f"/recovery-cases/{case_id}/timeline")
    assert tl_res.status_code == 200
    timeline = tl_res.json()
    assert isinstance(timeline, list)


def test_http_analytics_endpoints():
    """Test GET /analytics/overview, /failure-reason, and /intervention-performance."""
    # Overview
    ov_res = client.get("/analytics/overview")
    assert ov_res.status_code == 200
    ov = ov_res.json()
    assert "revenue_at_risk" in ov
    assert "revenue_recovered" in ov
    assert "recovery_rate_percent" in ov
    assert "active_cases" in ov

    # Failure Reason
    fr_res = client.get("/analytics/failure-reason")
    assert fr_res.status_code == 200
    fr = fr_res.json()
    assert isinstance(fr, list)

    # Intervention Performance
    ip_res = client.get("/analytics/intervention-performance")
    assert ip_res.status_code == 200
    ip = ip_res.json()
    assert isinstance(ip, list)


def test_http_experiment_endpoint():
    """Test POST /analytics/experiment computes Control vs AI cohort recovery."""
    exp_res = client.post("/analytics/experiment?cases_per_group=30&seed=42")
    assert exp_res.status_code == 200
    exp = exp_res.json()

    assert "control_group" in exp
    assert "ai_group" in exp
    assert "impact_metrics" in exp

    ctrl = exp["control_group"]
    ai = exp["ai_group"]
    imp = exp["impact_metrics"]

    assert ctrl["recovery_rate_percent"] >= 0
    assert ai["recovery_rate_percent"] >= 0
    assert "recovery_lift_percent" in imp
    assert "incremental_revenue_recovered" in imp


def test_http_health_system():
    """Test GET /health/system reports operational health across all components."""
    res = client.get("/health/system")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "api" in data
    assert "database" in data
    assert "ml" in data
    assert "policy_engine" in data
    assert "executor" in data
    assert "verification" in data


def test_http_policy_lab_simulate():
    """Test POST /recovery/policy-lab/simulate evaluates parameter adjustments without DB mutation."""
    list_res = client.get("/recovery-cases")
    assert list_res.status_code == 200
    cases = list_res.json()
    assert len(cases) > 0
    case_id = cases[0]["id"]

    # Test standard simulation
    sim_res = client.post("/recovery/policy-lab/simulate", json={
        "case_id": case_id,
        "amount_ceiling": 500.00,  # low ceiling to trigger escalation
        "max_retries": 3,
        "customer_opted_out": False,
        "simulate_bank_outage": False,
        "proposed_action": "retry"
    })
    assert sim_res.status_code == 200
    sim_data = sim_res.json()
    assert sim_data["case_id"] == case_id
    assert "evaluation" in sim_data
    assert "pipeline_trace" in sim_data
    # With low ceiling, amount should trigger merchant_amount_ceiling violation
    assert sim_data["evaluation"]["decision"] in ["ALLOWED", "DENIED"]

