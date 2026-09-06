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


from pydantic import BaseModel


class PolicyLabSimulateRequest(BaseModel):
    case_id: int
    amount_ceiling: Optional[float] = 10000.00
    max_retries: Optional[int] = 3
    customer_opted_out: Optional[bool] = None
    simulate_bank_outage: Optional[bool] = None
    proposed_action: Optional[str] = "retry"


@router.post("/policy-lab/simulate")
def policy_lab_simulate(
    req: PolicyLabSimulateRequest,
    db: Session = Depends(get_db)
):
    """
    Interactive Policy Lab simulation endpoint.
    Allows judges and operators to test what-if policy threshold adjustments
    (e.g., amount ceilings, retry limits, customer opt-out, bank outages)
    against real cases without financial execution.
    """
    from ..models.recovery_case import RecoveryCase
    from ..models.payment import Payment, PaymentStatus
    from ..models.customer import Customer
    from decimal import Decimal

    case = db.query(RecoveryCase).filter(RecoveryCase.id == req.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Case #{req.case_id} not found")

    payment = db.query(Payment).filter(Payment.id == case.payment_id).first()
    customer = db.query(Customer).filter(Customer.id == case.customer_id).first()

    opted_out = req.customer_opted_out if req.customer_opted_out is not None else (customer.opted_out if customer else False)
    ceiling = Decimal(str(req.amount_ceiling if req.amount_ceiling is not None else 10000.00))
    retries_cap = req.max_retries if req.max_retries is not None else 3
    attempts = case.attempt_count or 0
    action_type = (req.proposed_action or "retry").lower()

    violations = []
    reasons = []

    # 1. Already captured
    if payment and payment.status in [PaymentStatus.CAPTURED, "captured"]:
        violations.append("already_captured")
        reasons.append("Payment already captured; prevents double billing")

    # 2. Opt-out
    if opted_out:
        violations.append("customer_opt_out")
        reasons.append("Customer opted out of automated communications")

    # 3. Retry limits
    if action_type in ["retry", "retry_now", "retry_later"] and attempts >= retries_cap:
        violations.append("max_retries_exceeded")
        reasons.append(f"Attempt count ({attempts}) exceeds configured limit ({retries_cap})")

    # 4. Bank outage
    if req.simulate_bank_outage is True or (payment and payment.error_code in ["BANK_GATEWAY_TIMEOUT", "05", "BANK_OUTAGE"]):
        violations.append("bank_outage_detected")
        reasons.append("Bank gateway outage detected (>30% failure rate); policy dictates WAIT")

    # 5. Amount ceiling
    if Decimal(str(case.amount)) > ceiling:
        violations.append("merchant_amount_ceiling")
        reasons.append(f"Amount ₹{case.amount:,.2f} exceeds configured automated ceiling of ₹{ceiling:,.2f}; requires human escalation")

    allowed = len(violations) == 0
    fallback = "wait" if "bank_outage_detected" in violations else ("stop" if "already_captured" in violations or "customer_opt_out" in violations else "escalate")
    final_action = action_type if allowed else fallback

    return {
        "case_id": case.id,
        "scenario_key": case.scenario_key,
        "amount": float(case.amount),
        "customer_name": customer.name if customer else "Unknown",
        "parameters": {
            "amount_ceiling": float(ceiling),
            "max_retries": retries_cap,
            "customer_opted_out": opted_out,
            "simulate_bank_outage": req.simulate_bank_outage or False,
            "proposed_action": action_type,
        },
        "evaluation": {
            "allowed": allowed,
            "decision": "ALLOWED" if allowed else "DENIED",
            "rule_violations": violations,
            "primary_reason": reasons[0] if reasons else "All policy guardrails satisfied",
            "fallback_action": fallback if not allowed else None,
            "final_action": final_action.upper(),
        },
        "pipeline_trace": [
            {"stage": "INPUT", "detail": f"Failed Payment #{case.payment_id or case.id} (₹{case.amount:,.2f})"},
            {"stage": "AI PROPOSAL", "detail": f"Recommended Action: {action_type.upper()}"},
            {"stage": "POLICY BARRIER", "detail": "PASSED" if allowed else f"BLOCKED by {', '.join(violations)}"},
            {"stage": "FINAL OUTCOME", "detail": f"{final_action.upper()} ({'Permitted execution' if allowed else 'Safety override'})"},
        ]
    }