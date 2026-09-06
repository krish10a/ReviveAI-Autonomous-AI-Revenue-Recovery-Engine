"""
Regression tests for deterministic benchmark scenarios, scenario_key isolation,
idempotency, and audit timeline data integrity.
"""
import asyncio
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.app.database import DATABASE_URL
from apps.api.app.models import RecoveryCase, TimelineEvent, Communication
from database.seed.seed_demo import seed_database
from simulations.run_winning_demo import run_winning_demo
from apps.api.app.services.timeline import get_timeline_service
from apps.api.app.services.analytics import get_analytics_service
from apps.api.app.routers.analytics import run_control_vs_ai_experiment
from apps.api.app.routers.simulation import run_batch_simulation

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_clean_seed():
    seed_database()


def test_canonical_scenario_count():
    db = SessionLocal()
    try:
        cases = db.query(RecoveryCase).filter(RecoveryCase.scenario_key.isnot(None)).all()
        assert len(cases) == 8, f"Expected exactly 8 canonical benchmark cases, found {len(cases)}"
    finally:
        db.close()


def test_repeated_winning_demo_execution_idempotency():
    run_winning_demo()
    ts = get_timeline_service()
    events_sc1_before = len(ts.get_timeline_for_scenario("SCENARIO_1_RECOVERABLE"))
    analytics_before = get_analytics_service().get_recovery_overview()

    run_winning_demo()

    events_sc1_after = len(ts.get_timeline_for_scenario("SCENARIO_1_RECOVERABLE"))
    analytics_after = get_analytics_service().get_recovery_overview()

    assert events_sc1_before == events_sc1_after == 5, f"Expected 5 events for Scenario 1, got before={events_sc1_before}, after={events_sc1_after}"
    assert analytics_before["eligible_revenue"] == analytics_after["eligible_revenue"]
    assert analytics_before["revenue_recovered"] == analytics_after["revenue_recovered"]
    assert analytics_before["recovery_rate_percent"] == analytics_after["recovery_rate_percent"]


def test_scenario_1_exact_single_execution():
    run_winning_demo()
    ts = get_timeline_service()
    events = ts.get_timeline_for_scenario("SCENARIO_1_RECOVERABLE")
    actions = [e.action for e in events]
    assert actions.count("EXECUTE_RETRY") == 1, f"Expected exactly 1 EXECUTE_RETRY in Scenario 1, got {actions}"
    assert actions.count("VERIFY_RECOVERY_SUCCESS") == 1
    assert len(events) == 5, f"Expected 5 timeline events for Scenario 1, got {len(events)}: {actions}"


def test_scenario_3_exact_single_execution():
    run_winning_demo()
    ts = get_timeline_service()
    events = ts.get_timeline_for_scenario("SCENARIO_3_OPTED_OUT")
    actions = [e.action for e in events]
    assert actions.count("EXECUTE_STOP") == 1, f"Expected exactly 1 EXECUTE_STOP in Scenario 3, got {actions}"
    assert actions.count("VERIFY_CUSTOMER_PROTECTED") == 1
    assert len(events) == 5, f"Expected 5 timeline events for Scenario 3, got {len(events)}: {actions}"

    db = SessionLocal()
    try:
        case = db.query(RecoveryCase).filter(RecoveryCase.scenario_key == "SCENARIO_3_OPTED_OUT").first()
        comms = db.query(Communication).filter(Communication.case_id == case.id).all()
        assert len(comms) == 0, f"Expected 0 communications for opted-out customer, found {len(comms)}"
    finally:
        db.close()


def test_scenario_4_exact_single_execution():
    run_winning_demo()
    ts = get_timeline_service()
    events = ts.get_timeline_for_scenario("SCENARIO_4_HIGH_VALUE")
    actions = [e.action for e in events]
    assert actions.count("EXECUTE_ESCALATE") == 1, f"Expected exactly 1 EXECUTE_ESCALATE in Scenario 4, got {actions}"
    assert actions.count("VERIFY_RECOVERY_UNRESOLVED") == 1
    assert len(events) == 5, f"Expected 5 timeline events for Scenario 4, got {len(events)}: {actions}"


def test_scenario_5_exact_single_execution():
    run_winning_demo()
    ts = get_timeline_service()
    events = ts.get_timeline_for_scenario("SCENARIO_5_BANK_OUTAGE")
    actions = [e.action for e in events]
    assert actions.count("EXECUTE_WAIT") == 1, f"Expected exactly 1 EXECUTE_WAIT in Scenario 5, got {actions}"
    assert actions.count("VERIFY_RECOVERY_DEFERRED") == 1
    assert len(events) == 5, f"Expected 5 timeline events for Scenario 5, got {len(events)}: {actions}"


def test_batch_simulation_does_not_mutate_canonical_scenarios():
    run_winning_demo()
    ts = get_timeline_service()
    sc1_events_before = len(ts.get_timeline_for_scenario("SCENARIO_1_RECOVERABLE"))

    res = asyncio.run(run_batch_simulation(total_cases=5))
    assert res["success"] is True

    sc1_events_after = len(ts.get_timeline_for_scenario("SCENARIO_1_RECOVERABLE"))
    assert sc1_events_before == sc1_events_after == 5

    db = SessionLocal()
    try:
        canonical_cases = db.query(RecoveryCase).filter(RecoveryCase.scenario_key.isnot(None)).all()
        assert len(canonical_cases) == 8, "Canonical scenario count changed after batch simulation!"
    finally:
        db.close()


def test_controlled_experiment_determinism():
    res1 = run_control_vs_ai_experiment(cases_per_group=50, seed=42)
    res2 = run_control_vs_ai_experiment(cases_per_group=50, seed=42)

    assert res1["impact_metrics"]["recovery_lift_percent"] == res2["impact_metrics"]["recovery_lift_percent"]
    assert res1["control_group"]["recovered_revenue"] == res2["control_group"]["recovered_revenue"]
    assert res1["ai_group"]["recovered_revenue"] == res2["ai_group"]["recovered_revenue"]


def test_operational_kpi_isolated_from_experiment():
    run_winning_demo()
    overview = get_analytics_service().get_recovery_overview()
    experiment = run_control_vs_ai_experiment(cases_per_group=50, seed=42)

    assert overview["total_cases"] == 8
    assert experiment["metadata"]["sample_size_per_group"] == 50


def test_timeline_router_canonical_resolution():
    run_winning_demo()
    from apps.api.app.routers.timeline import get_case_timeline
    db = SessionLocal()
    try:
        res1 = get_case_timeline("1", db=db)
        actions1 = [e.action for e in res1]
        assert "EXECUTE_RETRY" in actions1, f"Case 1 resolution failed: {actions1}"

        res3 = get_case_timeline("3", db=db)
        actions3 = [e.action for e in res3]
        assert "EXECUTE_STOP" in actions3, f"Case 3 resolution failed: {actions3}"

        res4 = get_case_timeline("4", db=db)
        actions4 = [e.action for e in res4]
        assert "EXECUTE_ESCALATE" in actions4, f"Case 4 resolution failed: {actions4}"

        res5 = get_case_timeline("5", db=db)
        actions5 = [e.action for e in res5]
        assert "EXECUTE_WAIT" in actions5, f"Case 5 resolution failed: {actions5}"
    finally:
        db.close()
