"""
Timeline API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..services.timeline import get_timeline_service
from ..database import get_db
from ..models.timeline_event import TimelineEvent

router = APIRouter(prefix="/timeline", tags=["timeline"])


SCENARIO_INDEX_MAP = {
    "1": "SCENARIO_1_RECOVERABLE",
    "2": "SCENARIO_2_MULTI_STEP_RECOVERY",
    "3": "SCENARIO_3_OPTED_OUT",
    "4": "SCENARIO_4_HIGH_VALUE",
    "5": "SCENARIO_5_BANK_OUTAGE",
    "6": "SCENARIO_6_RETRY_LIMIT",
    "7": "SCENARIO_7_ALREADY_CAPTURED",
    "8": "SCENARIO_8_HUMAN_ESCALATION",
}


@router.get("/scenario/{scenario_key}")
def get_scenario_timeline(scenario_key: str):
    """
    Get timeline events for a canonical benchmark scenario by key.
    """
    timeline_service = get_timeline_service()
    try:
        events = timeline_service.get_timeline_for_scenario(scenario_key)
        return events
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/case/{case_identifier}")
def get_case_timeline(
    case_identifier: str,
    db: Session = Depends(get_db)
):
    """
    Get timeline events for a recovery case (by numeric case_id or scenario_key).
    """
    timeline_service = get_timeline_service()
    try:
        # Check if case_identifier is a scenario key directly
        if case_identifier.startswith("SCENARIO_"):
            events = timeline_service.get_timeline_for_scenario(case_identifier)
            if events:
                return events

        # Check if case_identifier maps to a canonical benchmark scenario key (1..8)
        canonical_key = SCENARIO_INDEX_MAP.get(str(case_identifier))
        if canonical_key:
            canonical_events = timeline_service.get_timeline_for_scenario(canonical_key)
            if canonical_events:
                return canonical_events

        # Fallback to direct integer case_id lookup
        try:
            cid = int(case_identifier)
            return timeline_service.get_timeline_for_case(cid)
        except ValueError:
            return []

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))