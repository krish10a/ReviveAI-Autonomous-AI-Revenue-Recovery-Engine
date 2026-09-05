"""
Recovery case API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import schemas
from ..services.recovery_case import get_recovery_case_service
from ..services.agent_loop_service import get_agent_loop_service
from ..database import get_db

router = APIRouter(prefix="/recovery", tags=["recovery"])


@router.post("/case", response_model=schemas.RecoveryCaseResponse)
def create_recovery_case_from_payment(
    payment_id: int,
    db: Session = Depends(get_db)
):
    """
    Create a recovery case from a failed payment.
    """
    recovery_case_service = get_recovery_case_service()
    try:
        recovery_case = recovery_case_service.create_recovery_case_from_payment(payment_id)
        return recovery_case
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/case/{case_id}", response_model=schemas.RecoveryCaseResponse)
def get_recovery_case(
    case_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a recovery case by ID.
    """
    recovery_case_service = get_recovery_case_service()
    recovery_case = recovery_case_service.get_recovery_case(case_id)
    if not recovery_case:
        raise HTTPException(status_code=404, detail="Recovery case not found")
    return recovery_case


@router.post("/case/{case_id}/run-agent-loop")
def run_agent_loop(
    case_id: int,
    background_tasks: BackgroundTasks,
    execution_mode: str = "simulation",
    db: Session = Depends(get_db)
):
    """
    Run the bounded agent loop for a recovery case.
    """
    # Verify the case exists
    recovery_case_service = get_recovery_case_service()
    recovery_case = recovery_case_service.get_recovery_case(case_id)
    if not recovery_case:
        raise HTTPException(status_code=404, detail="Recovery case not found")

    # Add the agent loop execution to background tasks
    agent_loop_service = get_agent_loop_service()
    background_tasks.add_task(
        agent_loop_service.run_agent_loop,
        case_id=case_id,
        execution_mode=execution_mode
    )

    return {"message": f"Agent loop started for case {case_id}"}


@router.get("/case/{case_id}/timeline")
def get_case_timeline(
    case_id: int,
    db: Session = Depends(get_db)
):
    """
    Get timeline events for a recovery case.
    """
    from ..services.timeline import get_timeline_service
    timeline_service = get_timeline_service()
    events = timeline_service.get_timeline_for_case(case_id)
    return events


@router.get("/cases", response_model=List[schemas.RecoveryCaseResponse])
def list_recovery_cases(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List recovery cases with pagination.
    """
    from ..models.recovery_case import RecoveryCase
    cases = db.query(RecoveryCase).offset(skip).limit(limit).all()
    return cases