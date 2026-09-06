"""
Simulation API endpoints for batch processing and scenario testing.
"""
import logging
import random
from typing import Dict, Any, List
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from ..services.recovery_case import get_recovery_case_service
from ..services.payment_event import get_payment_event_service
from ..services.agent_loop_service import get_agent_loop_service
from ..services.diagnosis import get_failure_diagnosis_service
from ..services.prediction import get_prediction_service
from ..services.policy import get_policy_engine_service
from ..services.executor import get_executor_service
from ..services.verification import get_verification_service
from ..database import SessionLocal
from ..models.payment import Payment, PaymentStatus, PaymentMethod
from ..models.merchant import Merchant
from ..models.customer import Customer
from ..models.recovery_case import RecoveryCase, RecoveryCaseStatus
from ..models.failure_diagnosis import FailureDiagnosis
from ..models.recovery_prediction import RecoveryPrediction
from ..models.recovery_action import RecoveryAction, RecoveryActionType, RecoveryActionStatus
from ..models.policy_decision import PolicyDecision, PolicyDecisionResult
from ..models.audit_log import AuditLog
from ..models.timeline_event import TimelineEvent
from ..models.recovery_ledger import RecoveryLedger
from ..models.communication import Communication
from ..models.payment_event import PaymentEvent
from ..database import Base, engine
import json

def clear_synthetic_simulation_cases(db: Session) -> int:
    """
    Remove all synthetic simulation cases (where scenario_key is None)
    and their associated records before running a new batch simulation.
    Canonical benchmark cases (scenario_key IS NOT NULL) are preserved.
    """
    sim_cases = db.query(RecoveryCase.id, RecoveryCase.payment_id).filter(
        RecoveryCase.scenario_key.is_(None)
    ).all()

    if not sim_cases:
        return 0

    sim_case_ids = [c.id for c in sim_cases]
    sim_payment_ids = [c.payment_id for c in sim_cases if c.payment_id is not None]

    db.query(RecoveryLedger).filter(RecoveryLedger.case_id.in_(sim_case_ids)).delete(synchronize_session=False)
    db.query(TimelineEvent).filter(TimelineEvent.case_id.in_(sim_case_ids)).delete(synchronize_session=False)
    db.query(AuditLog).filter(AuditLog.case_id.in_(sim_case_ids)).delete(synchronize_session=False)
    db.query(PolicyDecision).filter(PolicyDecision.case_id.in_(sim_case_ids)).delete(synchronize_session=False)
    db.query(RecoveryAction).filter(RecoveryAction.case_id.in_(sim_case_ids)).delete(synchronize_session=False)
    db.query(RecoveryPrediction).filter(RecoveryPrediction.case_id.in_(sim_case_ids)).delete(synchronize_session=False)
    db.query(FailureDiagnosis).filter(FailureDiagnosis.case_id.in_(sim_case_ids)).delete(synchronize_session=False)
    db.query(Communication).filter(Communication.case_id.in_(sim_case_ids)).delete(synchronize_session=False)

    db.query(RecoveryCase).filter(RecoveryCase.id.in_(sim_case_ids)).delete(synchronize_session=False)

    if sim_payment_ids:
        db.query(PaymentEvent).filter(PaymentEvent.payment_id.in_(sim_payment_ids)).delete(synchronize_session=False)
        db.query(Payment).filter(Payment.id.in_(sim_payment_ids)).delete(synchronize_session=False)

    db.commit()
    logger.info(f"Cleared {len(sim_case_ids)} previous synthetic simulation cases")
    return len(sim_case_ids)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulate", tags=["simulation"])

# Helper function to generate synthetic payment data
def generate_synthetic_payment(db: Session, merchant_id: int, customer_id: int, index: int) -> Dict[str, Any]:
    """Generate a synthetic failed payment for simulation."""

    # Different failure scenarios with realistic distributions
    failure_scenarios = [
        {"category": "insufficient_funds", "weight": 0.25},
        {"category": "expired_card", "weight": 0.20},
        {"category": "authentication_failed", "weight": 0.15},
        {"category": "technical_error", "weight": 0.15},
        {"category": "bank_declined", "weight": 0.15},
        {"category": "transaction_not_allowed", "weight": 0.10}
    ]

    # Select failure category based on weights
    rand_val = random.random()
    cumulative_weight = 0
    selected_failure = "insufficient_funds"  # default

    for scenario in failure_scenarios:
        cumulative_weight += scenario["weight"]
        if rand_val <= cumulative_weight:
            selected_failure = scenario["category"]
            break

    # Generate payment amount based on failure type (more realistic distributions)
    if selected_failure == "insufficient_funds":
        amount = round(random.uniform(500, 5000), 2)
    elif selected_failure == "expired_card":
        amount = round(random.uniform(1000, 10000), 2)
    elif selected_failure == "authentication_failed":
        amount = round(random.uniform(500, 15000), 2)
    elif selected_failure == "technical_error":
        amount = round(random.uniform(1000, 8000), 2)
    elif selected_failure == "bank_declined":
        amount = round(random.uniform(2000, 20000), 2)
    else:  # transaction_not_allowed
        amount = round(random.uniform(1000, 15000), 2)

    # Generate payment method
    payment_methods = [PaymentMethod.CARD, PaymentMethod.UPI, PaymentMethod.NETBANKING, PaymentMethod.WALLET]
    method = random.choice(payment_methods)

    # Generate bank name based on method
    banks = {
        PaymentMethod.CARD: ["HDFC", "ICICI", "SBI", "Axis", "Kotak"],
        PaymentMethod.UPI: ["PhonePe", "Google Pay", "Paytm", "Amazon Pay"],
        PaymentMethod.NETBANKING: ["HDFC NetBanking", "ICICI NetBanking", "SBI NetBanking"],
        PaymentMethod.WALLET: ["Paytm Wallet", "PhonePe Wallet", "Amazon Pay Balance"]
    }
    bank = random.choice(banks.get(method, ["Unknown Bank"]))

    # Create payment record
    payment = Payment(
        merchant_id=merchant_id,
        customer_id=customer_id,
        amount=amount,
        currency="INR",
        status=PaymentStatus.FAILED,
        method=method,
        bank=bank,
        error_code=f"FAIL_{selected_failure.upper()}",
        error_description=f"Payment failed due to {selected_failure.replace('_', ' ')}",
        attempt_count=1
    )

    db.add(payment)
    db.flush()

    return {
        "payment": payment,
        "failure_category": selected_failure,
        "amount": amount,
        "method": method.value,
        "bank": bank
    }

# Helper function to get or create merchant for simulation
def get_or_create_simulation_merchant(db: Session) -> Merchant:
    """Get or create a test merchant for simulation."""
    merchant = db.query(Merchant).filter(Merchant.merchant_reference == "SIM_MERCH_001").first()
    if not merchant:
        merchant = db.query(Merchant).first()
    if not merchant:
        merchant = Merchant(
            merchant_reference="SIM_MERCH_001",
            name="Simulation Merchant",
            email="merchant@simulation.com",
            phone="+919876543210",
            website="https://simulationmerchant.com",
            razorpay_key_id="test_key_id",
            razorpay_key_secret="test_key_secret",
            webhook_secret="test_webhook_secret",
            max_retries=3,
            contact_start_hour=8,
            contact_end_hour=21,
            max_automated_amount=5000.00,
            human_escalation_threshold=10000.00,
            message_cooldown_hours=1,
            case_expiry_hours=24,
            timezone="UTC",
            is_active=True,
            is_test_mode=True
        )
        db.add(merchant)
        db.commit()
        db.refresh(merchant)
    return merchant

# Helper function to get or create synthetic customers for simulation
def get_or_create_simulation_customers(db: Session, merchant_id: int, count: int = 5) -> List[Customer]:
    """Get or create a pool of synthetic customers for simulation."""
    customers = db.query(Customer).filter(Customer.merchant_id == merchant_id).limit(count).all()
    if len(customers) < count:
        profiles = [
            {"ref": "SIM_CUST_001", "name": "Simulation Customer 1", "email": "cust1@simulation.com", "phone": "+919876543211", "opted_out": False, "risk": 0.30, "tenure": 365},
            {"ref": "SIM_CUST_002", "name": "Opted Out Customer", "email": "cust2@simulation.com", "phone": "+919876543212", "opted_out": True, "risk": 0.50, "tenure": 180},
            {"ref": "SIM_CUST_003", "name": "High Risk Customer", "email": "cust3@simulation.com", "phone": "+919876543213", "opted_out": False, "risk": 0.85, "tenure": 30},
            {"ref": "SIM_CUST_004", "name": "VIP Customer", "email": "cust4@simulation.com", "phone": "+919876543214", "opted_out": False, "risk": 0.10, "tenure": 720},
            {"ref": "SIM_CUST_005", "name": "New Customer", "email": "cust5@simulation.com", "phone": "+919876543215", "opted_out": False, "risk": 0.40, "tenure": 10},
        ]
        existing_refs = {c.customer_reference for c in customers}
        for p in profiles:
            if len(customers) >= count:
                break
            if p["ref"] not in existing_refs:
                cust = Customer(
                    customer_reference=p["ref"],
                    merchant_id=merchant_id,
                    name=p["name"],
                    email=p["email"],
                    phone=p["phone"],
                    opted_out=p["opted_out"],
                    preferred_contact_method="email",
                    language="en",
                    risk_score=p["risk"],
                    tenure_days=p["tenure"],
                    previous_successful_payments=10,
                    previous_failed_payments=2,
                    previous_recoveries=1
                )
                db.add(cust)
                db.commit()
                db.refresh(cust)
                customers.append(cust)

    return customers

@router.post("/batch")
async def run_batch_simulation(
    total_cases: int = 100
) -> Dict[str, Any]:
    """
    Run a batch simulation of failed payments through the complete recovery pipeline.

    This endpoint:
    1. Generates synthetic failed payments
    2. Creates recovery cases for each payment
    3. Runs the agent loop for each case (diagnosis → prediction → policy → execution → verification)
    4. Returns aggregated results
    """
    logger.info(f"Starting batch simulation for {total_cases} cases")

    db = SessionLocal()
    try:
        # Clear previous synthetic simulation cases so batch runs start fresh from 0
        cleared_count = clear_synthetic_simulation_cases(db)
        if cleared_count > 0:
            logger.info(f"Reset {cleared_count} synthetic cases to 0 before starting new batch simulation")

        # Get or create merchant and customers for simulation
        merchant = get_or_create_simulation_merchant(db)
        customers = get_or_create_simulation_customers(db, merchant.id, count=5)

        merchant_id = merchant.id
        customer_ids = [c.id for c in customers]

        # Initialize services
        recovery_case_service = get_recovery_case_service()
        payment_event_service = get_payment_event_service()
        agent_loop_service = get_agent_loop_service()
        diagnosis_service = get_failure_diagnosis_service()
        prediction_service = get_prediction_service()
        policy_service = get_policy_engine_service()
        executor_service = get_executor_service()
        verification_service = get_verification_service()

        # Results tracking
        results = {
            "total_injected": 0,
            "diagnosed": 0,
            "actions_chosen": 0,
            "executed": 0,
            "verified": 0,
            "amount_recovered": 0.0,
            "recovered_cases": 0,
            "failed_cases": 0,
            "policy_denied_actions": 0,
            "llm_fallback_used": 0
        }

        logs = []

        def add_log(message: str):
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {message}"
            logs.append(log_entry)
            # Keep only last 100 logs to prevent memory issues
            if len(logs) > 100:
                logs.pop(0)
            logger.info(message)

        add_log(f"Starting batch simulation for {total_cases} synthetic failed payments")

        # Process each synthetic payment
        for i in range(total_cases):
            try:
                cust_id = customer_ids[i % len(customer_ids)]
                # Generate synthetic payment
                payment_data = generate_synthetic_payment(db, merchant_id, cust_id, i)
                payment = payment_data["payment"]

                results["total_injected"] += 1
                add_log(f"Generated payment {payment.id} for {payment_data['amount']} INR ({payment_data['failure_category']})")

                # Create recovery case from the failed payment
                recovery_case = recovery_case_service.create_recovery_case_from_payment(payment.id, db=db)
                db.commit()

                add_log(f"Created recovery case {recovery_case.id} for payment {payment.id}")

                # 1. Diagnosis
                diagnosis_result = diagnosis_service.diagnose_failure(
                    case_id=recovery_case.id,
                    diagnosis_mode="rule_based",
                    db=db
                )

                if diagnosis_result["success"]:
                    results["diagnosed"] += 1
                    add_log(f"Diagnosed case {recovery_case.id}: {diagnosis_result['failure_category']} (confidence: {diagnosis_result['confidence']:.2f})")
                else:
                    add_log(f"Failed to diagnose case {recovery_case.id}: {diagnosis_result.get('error')}")
                    results["failed_cases"] += 1
                    continue

                # 2. Prediction
                prediction_result = prediction_service.predict_recovery(
                    case_id=recovery_case.id,
                    prediction_mode="ml_model",
                    db=db
                )

                if prediction_result["success"]:
                    results["actions_chosen"] += 1
                    best_action = max(
                        prediction_result["predictions"].items(),
                        key=lambda x: x[1]["probability"]
                    )
                    add_log(f"Predicted best action for case {recovery_case.id}: {best_action[0]} (probability: {best_action[1]['probability']:.2f})")
                else:
                    add_log(f"Failed to predict for case {recovery_case.id}: {prediction_result.get('error')}")
                    results["failed_cases"] += 1
                    continue

                # 3. Policy evaluation and action selection
                if prediction_result["success"]:
                    best_action_type_str, best_action_data = max(
                        prediction_result["predictions"].items(),
                        key=lambda x: x[1]["probability"]
                    )

                    try:
                        best_action_type = RecoveryActionType(best_action_type_str)
                        action_prob = best_action_data["probability"]
                        action_reason = f"ML prediction: {action_prob * 100:.1f}% success probability"

                        temp_action = RecoveryAction(
                            case_id=recovery_case.id,
                            action_type=best_action_type,
                            reason=action_reason,
                            predicted_success_probability=action_prob,
                            status=RecoveryActionStatus.PROPOSED
                        )

                        policy_result = policy_service.evaluate_action(
                            case_id=recovery_case.id,
                            action=temp_action,
                            merchant=merchant,
                            db=db
                        )

                        if policy_result["allowed"]:
                            recovery_action = RecoveryAction(
                                case_id=recovery_case.id,
                                action_type=best_action_type,
                                reason=action_reason,
                                predicted_success_probability=action_prob,
                                status=RecoveryActionStatus.APPROVED
                            )

                            db.add(recovery_action)
                            db.flush()

                            execution_result = executor_service.execute_action(
                                case_id=recovery_case.id,
                                action=recovery_action,
                                execution_mode="simulation",
                                db=db
                            )

                            if execution_result["success"]:
                                recovery_action.status = RecoveryActionStatus.EXECUTED
                                recovery_action.executed_at = datetime.utcnow()
                                recovery_action.result = json.dumps(execution_result["details"])

                                results["executed"] += 1

                                verification_result = verification_service.verify_recovery(
                                    case_id=recovery_case.id,
                                    action_id=recovery_action.id,
                                    verification_mode="simulation",
                                    db=db
                                )

                                if verification_result["success"]:
                                    recovery_action.status = RecoveryActionStatus.VERIFIED
                                    recovery_action.verified_at = datetime.utcnow()
                                    recovery_action.result = json.dumps({
                                        "recovered": verification_result["recovered"],
                                        "details": verification_result["details"]
                                    })

                                    results["verified"] += 1

                                    if verification_result["recovered"]:
                                        recovery_case.status = RecoveryCaseStatus.RECOVERED
                                        recovery_case.closed_at = datetime.utcnow()
                                        recovery_case.recovered_amount = payment.amount
                                        payment.status = PaymentStatus.CAPTURED

                                        results["recovered_cases"] += 1
                                        results["amount_recovered"] += float(payment.amount)

                                        add_log(f"Case {recovery_case.id} recovered ₹{payment.amount} via {best_action_type.value}")
                                    else:
                                        add_log(f"Case {recovery_case.id} verification completed - non-recoverable condition")
                                else:
                                    add_log(f"Verification failed for case {recovery_case.id}: {verification_result.get('error')}")
                                    recovery_action.status = RecoveryActionStatus.DENIED
                            else:
                                add_log(f"Execution failed for case {recovery_case.id}: {execution_result.get('error')}")
                                recovery_action.status = RecoveryActionStatus.DENIED
                                results["policy_denied_actions"] += 1
                        else:
                            results["policy_denied_actions"] += 1
                            add_log(f"Action {best_action_type.value} denied by policy for case {recovery_case.id}: {policy_result['denied_reason']}")

                            from ..services.timeline import get_timeline_service
                            timeline_service = get_timeline_service()
                            timeline_service.add_event_to_timeline(
                                case_id=recovery_case.id,
                                actor="policy_engine_service",
                                action="policy_denial",
                                input_data={
                                    "action_type": best_action_type.value,
                                    "reason": action_reason
                                },
                                decision_data={
                                    "denied": True,
                                    "denied_reason": policy_result["denied_reason"],
                                    "rule_violations": policy_result["rule_violations"]
                                },
                                db=db
                            )

                    except ValueError as e:
                        add_log(f"Invalid action type {best_action_type_str}: {str(e)}")
                        results["failed_cases"] += 1
                        continue

                db.commit()

            except Exception as e:
                db.rollback()
                results["failed_cases"] += 1
                add_log(f"Error processing case {i}: {str(e)}")
                logger.error(f"Error in batch simulation case {i}: {str(e)}", exc_info=True)
                continue

        # Final commit
        db.commit()

        # Calculate recovery rate
        recovery_rate = (results["recovered_cases"] / results["total_injected"] * 100) if results["total_injected"] > 0 else 0

        add_log(f"Batch simulation complete! Simulated recovery of ₹{results['amount_recovered']:.2f} across {results['recovered_cases']}/{results['total_injected']} synthetic cases ({recovery_rate:.1f}% simulated recovery rate)")

        return {
            "success": True,
            "results": results,
            "logs": logs,
            "summary": {
                "total_cases": results["total_injected"],
                "recovered_cases": results["recovered_cases"],
                "recovery_rate_percent": round(recovery_rate, 2),
                "total_amount_recovered": round(results["amount_recovered"], 2),
                "average_recovery_per_case": round(results["amount_recovered"] / results["recovered_cases"], 2) if results["recovered_cases"] > 0 else 0,
                "policy_denial_rate": round((results["policy_denied_actions"] / results["total_injected"]) * 100, 2) if results["total_injected"] > 0 else 0
            }
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error in batch simulation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch simulation failed: {str(e)}")
    finally:
        db.close()

# Scenario-based simulation endpoints
@router.post("/scenario/{scenario_name}")
async def run_scenario_simulation(
    scenario_name: str,
    case_count: int = 10
) -> Dict[str, Any]:
    """
    Run a specific scenario simulation (insufficient funds, bank outage, opt-out, etc.)
    """
    logger.info(f"Starting scenario simulation: {scenario_name} with {case_count} cases")

    # This would implement specific scenario logic
    # For now, we'll redirect to the batch simulation with scenario-specific parameters
    scenario_configs = {
        "insufficient_funds": {"failure_bias": "insufficient_funds", "count": case_count},
        "bank_outage": {"failure_bias": "technical_error", "count": case_count},
        "opt_out": {"customer_opt_out": True, "count": case_count},
        "high_value": {"min_amount": 15000, "count": case_count},
        "multi_step": {"count": case_count}  # Cases that require multiple actions
    }

    if scenario_name not in scenario_configs:
        raise HTTPException(status_code=400, detail=f"Unknown scenario: {scenario_name}")

    # For simplicity, we'll use the batch simulation but could enhance with scenario-specific logic
    result = await run_batch_simulation(case_count)
    result["scenario"] = scenario_name
    result["scenario_config"] = scenario_configs[scenario_name]

    return result