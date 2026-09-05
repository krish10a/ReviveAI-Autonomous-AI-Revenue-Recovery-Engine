"""
Bounded agent loop service that orchestrates the recovery process:
Diagnose → Predict → Plan → Policy → Execute → Verify
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..services.recovery_case import get_recovery_case_service
from ..services.diagnosis import get_failure_diagnosis_service
from ..services.prediction import get_prediction_service
from ..services.policy import get_policy_engine_service
from ..services.executor import get_executor_service
from ..services.verification import get_verification_service
from ..database import SessionLocal
from ..models.recovery_case import RecoveryCase
from ..models.payment import Payment
from ..models.customer import Customer
from ..models.merchant import Merchant
from ..models.recovery_action import RecoveryAction, RecoveryActionType, RecoveryActionStatus
from ..models.audit_log import AuditLog
from ..services.timeline import get_timeline_service

logger = logging.getLogger(__name__)

class AgentLoopService:
    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        # Bounded set of actions as per requirements
        self.bounded_actions = ["wait", "send_notification", "generate_payment_link", "retry", "escalate", "stop"]

    def run_agent_loop(self, case_id: int, execution_mode: str = "simulation") -> Dict[str, Any]:
        """
        Run the bounded agent loop for a recovery case.

        Args:
            case_id: ID of the recovery case
            execution_mode: Either "simulation" or "razorpay_test" for execution

        Returns:
            dict: Final result of the agent loop execution
        """
        logger.info(f"Starting agent loop for case {case_id} with max {self.max_iterations} iterations")

        db = SessionLocal()
        try:
            # Get the recovery case
            recovery_case = db.query(RecoveryCase).filter(
                RecoveryCase.id == case_id
            ).first()

            if not recovery_case:
                raise ValueError(f"Recovery case {case_id} not found")

            # Initialize loop result
            loop_result = {
                "success": False,
                "case_id": case_id,
                "iterations": 0,
                "final_status": None,
                "recovered": False,
                "actions_taken": [],
                "timeline_events": [],
                "error": None
            }

            # Run the bounded agent loop
            for iteration in range(self.max_iterations):
                logger.info(f"Agent loop iteration {iteration + 1} for case {case_id}")

                # Check if case is already resolved
                if recovery_case.status in ["recovered", "stopped", "expired"]:
                    loop_result["final_status"] = recovery_case.status
                    loop_result["recovered"] = (recovery_case.status == "recovered")
                    break

                # Execute one iteration of the loop: Diagnose → Predict → Plan → Policy → Execute → Verify
                iteration_result = self._run_single_iteration(
                    case_id, iteration + 1, execution_mode, db
                )

                loop_result["iterations"] += 1
                loop_result["actions_taken"].extend(iteration_result.get("actions_taken", []))

                # If we recovered money, we can exit early
                if iteration_result.get("recovered", False):
                    loop_result["recovered"] = True
                    loop_result["final_status"] = "recovered"
                    break

                # If we got a terminal action (stop, escalate) or waited and verified, we might exit
                if iteration_result.get("should_break", False):
                    loop_result["final_status"] = iteration_result.get("terminal_status")
                    break

            # Update final results
            loop_result["success"] = True
            loop_result["final_status"] = loop_result["final_status"] or recovery_case.status

            # Record the completion in timeline
            timeline_service = get_timeline_service()
            timeline_service.add_event_to_timeline(
                case_id=case_id,
                actor="agent_loop_service",
                action="agent_loop_completed",
                input_data={
                    "max_iterations": self.max_iterations,
                    "execution_mode": execution_mode
                },
                decision_data={
                    "iterations": loop_result["iterations"],
                    "final_status": loop_result["final_status"],
                    "recovered": loop_result["recovered"],
                    "actions_taken": loop_result["actions_taken"]
                }
            )

            db.commit()
            return loop_result

        except Exception as e:
            db.rollback()
            logger.error(f"Error in agent loop for case {case_id}: {str(e)}")
            return {
                "success": False,
                "case_id": case_id,
                "iterations": 0,
                "final_status": None,
                "recovered": False,
                "actions_taken": [],
                "timeline_events": [],
                "error": str(e)
            }
        finally:
            db.close()

    def _run_single_iteration(self, case_id: int, iteration_num: int,
                            execution_mode: str, db: Session) -> Dict[str, Any]:
        """
        Run a single iteration of the agent loop: Diagnose → Predict → Plan → Policy → Execute → Verify

        Returns:
            dict: Results of the iteration including whether to break and recovery status
        """
        iteration_result = {
            "actions_taken": [],
            "recovered": False,
            "should_break": False,
            "terminal_status": None
        }

        try:
            # Get services
            diagnosis_service = get_failure_diagnosis_service()
            prediction_service = get_prediction_service()
            policy_service = get_policy_engine_service()
            executor_service = get_executor_service()
            verification_service = get_verification_service()
            timeline_service = get_timeline_service()

            # Get current case state
            recovery_case = db.query(RecoveryCase).filter(
                RecoveryCase.id == case_id
            ).first()

            if not recovery_case:
                raise ValueError(f"Recovery case {case_id} not found")

            payment = db.query(Payment).filter(
                Payment.id == recovery_case.payment_id
            ).first()

            customer = db.query(Customer).filter(
                Customer.id == recovery_case.customer_id
            ).first()

            merchant = db.query(Merchant).filter(
                Merchant.id == recovery_case.merchant_id
            ).first()

            if not all([payment, customer, merchant]):
                raise ValueError("Related entities not found")

            # STEP 1: DIAGNOSE - Determine why payment failed
            logger.info(f"Iteration {iteration_num}: Diagnosing failure for case {case_id}")
            diagnosis_result = diagnosis_service.diagnose_failure(
                case_id=case_id,
                diagnosis_mode="rule_based"  # Start with rule-based, could fallback to LLM
            )

            if not diagnosis_result["success"]:
                logger.error(f"Diagnosis failed for case {case_id}: {diagnosis_result.get('error')}")
                return iteration_result

            failure_category = diagnosis_result["failure_category"]
            diagnosis_confidence = diagnosis_result["confidence"]

            # Record diagnosis in timeline
            timeline_service.add_event_to_timeline(
                case_id=case_id,
                actor="diagnosis_service",
                action="diagnose_failure",
                input_data={"diagnosis_mode": "rule_based"},
                decision_data={
                    "failure_category": failure_category,
                    "confidence": diagnosis_confidence
                }
            )

            # Update case with diagnosis
            recovery_case.failure_category = failure_category
            recovery_case.updated_at = datetime.utcnow()

            # STEP 2: PREDICT - ML-based recovery probability estimation
            logger.info(f"Iteration {iteration_num}: Predicting recovery for case {case_id}")
            prediction_result = prediction_service.predict_recovery(
                case_id=case_id,
                prediction_mode="ml_model"
            )

            if not prediction_result["success"]:
                logger.error(f"Prediction failed for case {case_id}: {prediction_result.get('error')}")
                return iteration_result

            predictions = prediction_result["predictions"]

            # Record prediction in timeline
            timeline_service.add_event_to_timeline(
                case_id=case_id,
                actor="prediction_service",
                action="predict_recovery",
                input_data={"prediction_mode": "ml_model"},
                decision_data={"predictions": predictions}
            )

            # Update case with best prediction
            if predictions:
                best_action = max(
                    predictions.items(),
                    key=lambda x: x[1]["probability"]
                )
                recovery_case.recovery_probability = best_action[1]["probability"]
                recovery_case.expected_recovery = recovery_case.amount * best_action[1]["probability"]
                recovery_case.updated_at = datetime.utcnow()

            # STEP 3: PLAN - Generate candidate actions based on predictions
            logger.info(f"Iteration {iteration_num}: Planning actions for case {case_id}")

            # Filter actions to only those in our bounded set
            candidate_actions = []
            for action_type_str, pred_data in predictions.items():
                # Convert string to enum
                try:
                    action_type = RecoveryActionType(action_type_str)
                    if action_type.value in self.bounded_actions:
                        candidate_actions.append({
                            "action_type": action_type,
                            "probability": pred_data["probability"],
                            "confidence": pred_data.get("confidence", 0.8),
                            "reasoning": f"ML prediction: {pred_data['probability']*100:.1f}% success probability"
                        })
                except ValueError:
                    # Skip invalid action types
                    continue

            # If no valid actions from ML, use default bounded actions with equal probability
            if not candidate_actions:
                for action_str in self.bounded_actions:
                    try:
                        action_type = RecoveryActionType(action_str)
                        candidate_actions.append({
                            "action_type": action_type,
                            "probability": 0.5,  # Default probability
                            "confidence": 0.5,
                            "reasoning": "Default action (no ML prediction available)"
                        })
                    except ValueError:
                        continue

            # STEP 4: POLICY - Evaluate each candidate action against business rules
            logger.info(f"Iteration {iteration_num}: Evaluating actions against policy for case {case_id}")

            approved_actions = []
            for candidate in candidate_actions:
                action_type = candidate["action_type"]

                # Create a temporary action object for policy evaluation
                temp_action = RecoveryAction(
                    case_id=case_id,
                    action_type=action_type,
                    reason=candidate["reasoning"],
                    predicted_success_probability=candidate["probability"],
                    status=RecoveryActionStatus.PROPOSED
                )

                # Evaluate against policy
                policy_result = policy_service.evaluate_action(
                    case_id=case_id,
                    action=temp_action,
                    merchant=merchant
                )

                if policy_result["allowed"]:
                    # Add policy information to candidate
                    candidate["policy_result"] = policy_result
                    approved_actions.append(candidate)
                else:
                    logger.info(f"Action {action_type.value} denied by policy: {policy_result['denied_reason']}")

                    # Record policy denial in timeline
                    timeline_service.add_event_to_timeline(
                        case_id=case_id,
                        actor="policy_engine_service",
                        action="policy_denial",
                        input_data={
                            "action_type": action_type.value,
                            "reason": candidate["reasoning"]
                        },
                        decision_data={
                            "denied": True,
                            "denied_reason": policy_result["denied_reason"],
                            "rule_violations": policy_result["rule_violations"]
                        }
                    )

            # STEP 5: EXECUTE - Select and execute the best approved action
            logger.info(f"Iteration {iteration_num}: Selecting action to execute for case {case_id}")

            action_executed = False
            if approved_actions:
                # Select the action with highest probability
                best_candidate = max(
                    approved_actions,
                    key=lambda x: x["probability"]
                )

                action_type = best_candidate["action_type"]
                logger.info(f"Selected action: {action_type.value} with probability {best_candidate['probability']}")

                # Create the actual action record
                recovery_action = RecoveryAction(
                    case_id=case_id,
                    action_type=action_type,
                    reason=best_candidate["reasoning"],
                    predicted_success_probability=best_candidate["probability"],
                    status=RecoveryActionStatus.APPROVED
                )

                db.add(recovery_action)
                db.flush()  # Get the ID without committing

                # Execute the action
                execution_result = executor_service.execute_action(
                    case_id=case_id,
                    action=recovery_action,
                    execution_mode=execution_mode
                )

                if execution_result["success"]:
                    # Update action status
                    recovery_action.status = RecoveryActionStatus.EXECUTED
                    recovery_action.executed_at = datetime.utcnow()
                    recovery_action.result = str(execution_result["details"])

                    # Record execution in timeline
                    timeline_service.add_event_to_timeline(
                        case_id=case_id,
                        actor="executor_service",
                        action=f"execute_{action_type.value}",
                        input_data={
                            "execution_mode": execution_mode,
                            "parameters": best_candidate["reasoning"]
                        },
                        decision_data={
                            "success": True,
                            "details": execution_result["details"]
                        }
                    )

                    iteration_result["actions_taken"].append({
                        "action_type": action_type.value,
                        "execution_mode": execution_mode,
                        "success": True,
                        "details": execution_result["details"]
                    })

                    action_executed = True

                    # Special handling for certain actions
                    if action_type == RecoveryActionType.STOP:
                        iteration_result["should_break"] = True
                        iteration_result["terminal_status"] = "stopped"
                    elif action_type == RecoveryActionType.ESCALATE:
                        iteration_result["should_break"] = True
                        iteration_result["terminal_status"] = "escalated"

                else:
                    # Execution failed
                    recovery_action.status = RecoveryActionStatus.DENIED  # Or FAILED?
                    recovery_action.result = str({"error": execution_result.get("error")})

                    logger.error(f"Action execution failed: {execution_result.get('error')}")

                    # Record execution failure in timeline
                    timeline_service.add_event_to_timeline(
                        case_id=case_id,
                        actor="executor_service",
                        action=f"execute_{action_type.value}",
                        input_data={
                            "execution_mode": execution_mode,
                            "parameters": best_candidate["reasoning"]
                        },
                        decision_data={
                            "success": False,
                            "error": execution_result.get("error")
                        }
                    )

                    iteration_result["actions_taken"].append({
                        "action_type": action_type.value,
                        "execution_mode": execution_mode,
                        "success": False,
                        "error": execution_result.get("error")
                    })
            else:
                logger.warning(f"No approved actions for case {case_id} - all actions denied by policy")

                # If no actions are approved, we should wait or stop
                # Create a wait action as fallback
                wait_action = RecoveryAction(
                    case_id=case_id,
                    action_type=RecoveryActionType.WAIT,
                    reason="No actions approved by policy - waiting",
                    predicted_success_probability=0.0,
                    status=RecoveryActionStatus.APPROVED
                )

                db.add(wait_action)
                db.flush()

                # Execute wait action
                execution_result = executor_service.execute_action(
                    case_id=case_id,
                    action=wait_action,
                    execution_mode=execution_mode
                )

                if execution_result["success"]:
                    wait_action.status = RecoveryActionStatus.EXECUTED
                    wait_action.executed_at = datetime.utcnow()
                    wait_action.result = str(execution_result["details"])

                    iteration_result["actions_taken"].append({
                        "action_type": "wait",
                        "execution_mode": execution_mode,
                        "success": True,
                        "details": execution_result["details"],
                        "reason": "No actions approved by policy - waiting"
                    })

                    # After waiting, we should verify in next iteration
                    # But if we've waited too many times, we might want to stop
                    if iteration_num >= 3:  # After 3 waits, consider stopping
                        iteration_result["should_break"] = True
                        iteration_result["terminal_status"] = "stopped_after_waits"

            # STEP 6: VERIFY - Check if the action resulted in money recovery
            logger.info(f"Iteration {iteration_num}: Verifying recovery for case {case_id}")

            # Only verify if we executed an action that could lead to recovery
            if action_executed and recovery_action and recovery_action.status == RecoveryActionStatus.EXECUTED:
                # Skip verification for wait, stop, escalate as they don't directly recover money
                if recovery_action.action_type not in [
                    RecoveryActionType.WAIT,
                    RecoveryActionType.STOP,
                    RecoveryActionType.ESCALATE
                ]:
                    verification_result = verification_service.verify_recovery(
                        case_id=case_id,
                        action_id=recovery_action.id,
                        verification_mode="simulation"  # Start with simulation
                    )

                    if verification_result["success"]:
                        # Update action status
                        recovery_action.status = RecoveryActionStatus.VERIFIED
                        recovery_action.verified_at = datetime.utcnow()
                        recovery_action.result = str({
                            "recovered": verification_result["recovered"],
                            "details": verification_result["details"]
                        })

                        # Record verification in timeline
                        timeline_service.add_event_to_timeline(
                            case_id=case_id,
                            actor="verification_service",
                            action="verify_recovery",
                            input_data={
                                "action_id": recovery_action.id,
                                "verification_mode": "simulation"
                            },
                            decision_data={
                                "recovered": verification_result["recovered"],
                                "details": verification_result["details"]
                            }
                        )

                        iteration_result["actions_taken"][-1]["verified"] = True
                        iteration_result["actions_taken"][-1]["recovered"] = verification_result["recovered"]

                        if verification_result["recovered"]:
                            iteration_result["recovered"] = True
                            iteration_result["should_break"] = True
                            iteration_result["terminal_status"] = "recovered"

                            # Update case status
                            recovery_case.status = RecoveryCaseStatus.RECOVERED
                            recovery_case.closed_at = datetime.utcnow()
                        else:
                            # Not recovered - continue loop unless this was a terminal action
                            pass
                    else:
                        logger.error(f"Verification failed: {verification_result.get('error')}")

                        # Record verification failure in timeline
                        timeline_service.add_event_to_timeline(
                            case_id=case_id,
                            actor="verification_service",
                            action="verify_recovery",
                            input_data={
                                "action_id": recovery_action.id,
                                "verification_mode": "simulation"
                            },
                            decision_data={
                                "success": False,
                                "error": verification_result.get("error")
                            }
                        )

                        iteration_result["actions_taken"][-1]["verified"] = False
                        iteration_result["actions_taken"][-1]["verification_error"] = verification_result.get("error")
                else:
                    # For wait, stop, escalate - just record that we executed them
                    iteration_result["actions_taken"][-1]["verified"] = False  # Not applicable
                    iteration_result["actions_taken"][-1]["verification_skipped"] = True

                    # If we executed a wait and we've done several iterations, consider stopping
                    if (recovery_action.action_type == RecoveryActionType.WAIT and
                        iteration_num >= 2):
                        iteration_result["should_break"] = True
                        iteration_result["terminal_status"] = "stopped_after_waits"

            # Update the case
            recovery_case.updated_at = datetime.utcnow()

            # If we've exhausted reasonable attempts, consider stopping
            if recovery_case.attempt_count >= merchant.max_retries:
                logger.info(f"Case {case_id} has exceeded max retries ({merchant.max_retries})")
                iteration_result["should_break"] = True
                iteration_result["terminal_status"] = "stopped_max_retries"

        except Exception as e:
            logger.error(f"Error in agent loop iteration {iteration_num}: {str(e)}")
            iteration_result["error"] = str(e)

        return iteration_result

# Singleton instance
agent_loop_service = AgentLoopService()

def get_agent_loop_service():
    return agent_loop_service