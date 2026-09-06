"""
Regression tests for deterministic benchmark scenarios, scenario_key isolation,
and audit timeline data integrity.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.app.database import DATABASE_URL
from apps.api.app.models import RecoveryCase, TimelineEvent, Communication
from database.seed.seed_demo import seed_database
from apps.api.app.services.timeline import get_timeline_service
from apps.api.app.routers.timeline import SCENARIO_INDEX_MAP

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_seed():
    seed_database()


def test_seed_populates_scenario_keys():
    db = SessionLocal()
    try:
        cases = db.query(RecoveryCase).filter(RecoveryCase.scenario_key.isnot(None)).all()
        assert len(cases) == 8, f"Expected 8 canonical benchmark cases, found {len(cases)}"
        scenario_keys = {c.scenario_key for c in cases}
        assert "SCENARIO_1_RECOVERABLE" in scenario_keys
        assert "SCENARIO_3_OPTED_OUT" in scenario_keys
        assert "SCENARIO_4_HIGH_VALUE" in scenario_keys
        assert "SCENARIO_5_BANK_OUTAGE" in scenario_keys
    finally:
        db.close()


def test_scenario_1_timeline_events():
    ts = get_timeline_service()
    events = ts.get_timeline_for_scenario("SCENARIO_1_RECOVERABLE")
    assert len(events) >= 3, f"Expected at least 3 timeline events for Scenario 1, got {len(events)}"
    actions = [e.action for e in events]
    assert "EXECUTE_RETRY" in actions, f"Scenario 1 timeline missing EXECUTE_RETRY: {actions}"
    assert "VERIFY_RECOVERY_SUCCESS" in actions, f"Scenario 1 timeline missing VERIFY_RECOVERY_SUCCESS: {actions}"


def test_scenario_3_opt_out_zero_communication_and_stop():
    db = SessionLocal()
    try:
        case = db.query(RecoveryCase).filter(RecoveryCase.scenario_key == "SCENARIO_3_OPTED_OUT").first()
        assert case is not None
        comms = db.query(Communication).filter(Communication.case_id == case.id).all()
        assert len(comms) == 0, f"Expected 0 communications for opted-out customer, found {len(comms)}"

        ts = get_timeline_service()
        events = ts.get_timeline_for_scenario("SCENARIO_3_OPTED_OUT")
        actions = [e.action for e in events]
        assert "EXECUTE_STOP" in actions, f"Scenario 3 timeline missing EXECUTE_STOP: {actions}"
        assert "VERIFY_CUSTOMER_PROTECTED" in actions, f"Scenario 3 timeline missing VERIFY_CUSTOMER_PROTECTED: {actions}"
    finally:
        db.close()


def test_scenario_4_high_value_escalation():
    ts = get_timeline_service()
    events = ts.get_timeline_for_scenario("SCENARIO_4_HIGH_VALUE")
    actions = [e.action for e in events]
    assert "EXECUTE_ESCALATE" in actions, f"Scenario 4 timeline missing EXECUTE_ESCALATE: {actions}"


def test_scenario_5_bank_outage_wait():
    ts = get_timeline_service()
    events = ts.get_timeline_for_scenario("SCENARIO_5_BANK_OUTAGE")
    actions = [e.action for e in events]
    assert "EXECUTE_WAIT" in actions, f"Scenario 5 timeline missing EXECUTE_WAIT: {actions}"
    assert "VERIFY_RECOVERY_DEFERRED" in actions, f"Scenario 5 timeline missing VERIFY_RECOVERY_DEFERRED: {actions}"


def test_timeline_router_canonical_resolution():
    from apps.api.app.routers.timeline import get_case_timeline, get_scenario_timeline
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
