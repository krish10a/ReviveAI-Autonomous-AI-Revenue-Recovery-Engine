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


@router.get("/case/{case_id}")
def get_case_timeline(
    case_id: int,
    db: Session = Depends(get_db)
):
    """
    Get timeline events for a recovery case.
    """
    timeline_service = get_timeline_service()
    try:
        events = timeline_service.get_timeline_for_case(case_id)
        return events
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))