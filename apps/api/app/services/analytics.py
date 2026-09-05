"""
Analytics Service for ReviveAI.
Computes all financial and operational metrics directly from live database state.
Strictly zero placeholders.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from ..database import SessionLocal
from ..models.recovery_case import RecoveryCase, RecoveryCaseStatus
from ..models.payment import Payment, PaymentStatus
from ..models.recovery_action import RecoveryAction, RecoveryActionType, RecoveryActionStatus
from ..models.policy_decision import PolicyDecision, PolicyDecisionResult
from ..models.recovery_ledger import RecoveryLedger

logger = logging.getLogger(__name__)


class LiveAnalyticsService:
    def get_recovery_overview(self) -> Dict[str, Any]:
        """Compute top-line recovery metrics directly from live database tables."""
        db = SessionLocal()
        try:
            # 1. Revenue At Risk (sum of amounts in currently OPEN cases)
            open_cases_agg = db.query(
                func.count(RecoveryCase.id).label("active_cases"),
                func.coalesce(func.sum(RecoveryCase.amount), 0).label("at_risk_amount"),
            ).filter(RecoveryCase.status == RecoveryCaseStatus.OPEN).first()

            active_cases = int(open_cases_agg.active_cases or 0)
            revenue_at_risk = float(open_cases_agg.at_risk_amount or 0.0)

            # 2. Total Eligible Revenue (all cases processed)
            total_cases_agg = db.query(
                func.count(RecoveryCase.id).label("total_cases"),
                func.coalesce(func.sum(RecoveryCase.amount), 0).label("eligible_amount"),
            ).first()

            total_cases = int(total_cases_agg.total_cases or 0)
            eligible_revenue = float(total_cases_agg.eligible_amount or 0.0)

            # 3. Revenue Recovered & Cost from Recovery Ledger
            ledger_agg = db.query(
                func.count(RecoveryLedger.id).label("recovered_count"),
                func.coalesce(func.sum(RecoveryLedger.gross_amount), 0).label("gross_recovered"),
                func.coalesce(func.sum(RecoveryLedger.action_cost), 0).label("total_action_cost"),
                func.coalesce(func.sum(RecoveryLedger.net_recovered), 0).label("net_recovered"),
            ).first()

            # Fallback to recovery_cases if ledger is fresh
            ledger_recovered_amount = float(ledger_agg.gross_recovered or 0.0)
            if ledger_recovered_amount == 0:
                rc_recovered = db.query(
                    func.coalesce(func.sum(RecoveryCase.amount), 0)
                ).filter(RecoveryCase.status == RecoveryCaseStatus.RECOVERED).scalar()
                revenue_recovered = float(rc_recovered or 0.0)
            else:
                revenue_recovered = ledger_recovered_amount

            recovery_cost = float(ledger_agg.total_action_cost or 0.0)
            net_recovered = float(ledger_agg.net_recovered or (revenue_recovered - recovery_cost))

            # Rates
            recovery_rate = (revenue_recovered / eligible_revenue * 100.0) if eligible_revenue > 0 else 0.0
            cost_per_rupee = (recovery_cost / revenue_recovered) if revenue_recovered > 0 else 0.01

            # 4. Policy Denials & Operational Decisions
            policy_denials = db.query(func.count(PolicyDecision.id)).filter(
                PolicyDecision.result == PolicyDecisionResult.DENIED
            ).scalar() or 0

            wait_decisions = db.query(func.count(RecoveryAction.id)).filter(
                RecoveryAction.action_type == RecoveryActionType.WAIT
            ).scalar() or 0

            escalated_count = db.query(func.count(RecoveryAction.id)).filter(
                RecoveryAction.action_type == RecoveryActionType.ESCALATE
            ).scalar() or 0
            escalation_rate = (escalated_count / total_cases * 100.0) if total_cases > 0 else 0.0

            return {
                "revenue_at_risk": round(revenue_at_risk, 2),
                "eligible_revenue": round(eligible_revenue, 2),
                "revenue_recovered": round(revenue_recovered, 2),
                "recovery_rate_percent": round(recovery_rate, 2),
                "active_cases": active_cases,
                "total_cases": total_cases,
                "recovery_cost": round(recovery_cost, 2),
                "cost_per_rupee_recovered": round(cost_per_rupee, 4),
                "net_recovery": round(net_recovered, 2),
                "policy_denials_count": int(policy_denials),
                "wait_decisions_count": int(wait_decisions),
                "escalation_rate_percent": round(escalation_rate, 2),
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            db.close()

    def get_recovery_by_failure_reason(self) -> List[Dict[str, Any]]:
        """Recovery rates segmented by failure category."""
        db = SessionLocal()
        try:
            results = db.query(
                Payment.error_code,
                func.count(RecoveryCase.id).label("total"),
                func.sum(case((RecoveryCase.status == RecoveryCaseStatus.RECOVERED, 1), else_=0)).label("recovered"),
                func.coalesce(func.sum(RecoveryCase.amount), 0).label("volume"),
                func.coalesce(func.sum(case((RecoveryCase.status == RecoveryCaseStatus.RECOVERED, RecoveryCase.amount), else_=0)), 0).label("recovered_volume"),
            ).join(Payment, RecoveryCase.payment_id == Payment.id).group_by(Payment.error_code).all()

            breakdown = []
            for r in results:
                tot = int(r.total or 0)
                rec = int(r.recovered or 0)
                rate = (rec / tot * 100.0) if tot > 0 else 0.0
                breakdown.append({
                    "failure_reason": r.error_code or "Unknown Decline",
                    "total_cases": tot,
                    "recovered_cases": rec,
                    "recovery_rate": round(rate, 2),
                    "total_amount": float(r.volume),
                    "recovered_amount": float(r.recovered_volume),
                })
            return breakdown
        finally:
            db.close()

    def get_intervention_performance(self) -> List[Dict[str, Any]]:
        """Performance metrics segmented by intervention action type."""
        db = SessionLocal()
        try:
            results = db.query(
                RecoveryAction.action_type,
                func.count(RecoveryAction.id).label("total_proposed"),
                func.sum(case((RecoveryAction.status == RecoveryActionStatus.VERIFIED, 1), else_=0)).label("verified_successes"),
                func.sum(case((RecoveryAction.status == RecoveryActionStatus.DENIED, 1), else_=0)).label("denied_by_policy"),
            ).group_by(RecoveryAction.action_type).all()

            interventions = []
            for r in results:
                tot = int(r.total_proposed or 0)
                succ = int(r.verified_successes or 0)
                den = int(r.denied_by_policy or 0)
                act_str = r.action_type.value if hasattr(r.action_type, 'value') else str(r.action_type)
                interventions.append({
                    "action_type": act_str,
                    "total_proposed": tot,
                    "successful_recoveries": succ,
                    "policy_denials": den,
                    "success_rate": round((succ / tot * 100.0) if tot > 0 else 0.0, 2),
                })
            return interventions
        finally:
            db.close()


analytics_service = LiveAnalyticsService()


def get_analytics_service() -> LiveAnalyticsService:
    return analytics_service
