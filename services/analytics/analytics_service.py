"""
Analytics service for tracking recovery metrics
"""
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from ..services.recovery_case import get_recovery_case_service
from ..database import SessionLocal
from ..models.recovery_case import RecoveryCase, RecoveryCaseStatus
from ..models.payment import Payment
from ..models.customer import Customer
from ..models.merchant import Merchant

logger = logging.getLogger(__name__)

class AnalyticsService:
    def get_recovery_overview(self) -> Dict[str, Any]:
        """
        Get overall recovery analytics for dashboard
        """
        db = SessionLocal()
        try:
            # Total amount at risk (open cases)
            at_risk_result = db.query(
                func.count(RecoveryCase.id).label('case_count'),
                func.sum(RecoveryCase.amount).label('total_amount')
            ).filter(
                RecoveryCase.status == RecoveryCaseStatus.OPEN
            ).first()
            
            # Total recovered amount
            recovered_result = db.query(
                func.count(RecoveryCase.id).label('recovered_count'),
                func.sum(RecoveryCase.amount).label('recovered_amount')
            ).filter(
                RecoveryCase.status == RecoveryCaseStatus.RECOVERED
            ).first()
            
            # Calculate recovery rate
            at_risk_amount = float(at_risk_result.total_amount) if at_risk_result.total_amount else 0
            recovered_amount = float(recovered_result.recovered_amount) if recovered_result.recovered_amount else 0
            
            recovery_rate = (recovered_amount / at_risk_amount * 100) if at_risk_amount > 0 else 0
            
            # Calculate cost per ₹ recovered (simplified)
            # In real system, would sum up costs of actions taken
            cost_per_recovered = 0.1  # Placeholder - 10 paise per ₹ recovered
            
            # Active cases count
            active_cases = at_risk_result.case_count if at_risk_result.case_count else 0
            
            return {
                "revenue_at_risk": at_risk_amount,
                "revenue_recovered": recovered_amount,
                "recovery_rate_percent": round(recovery_rate, 2),
                "active_cases": active_cases,
                "cost_per_rupee_recovered": cost_per_recovered,
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting recovery overview: {str(e)}")
            raise
        finally:
            db.close()
    
    def get_recovery_by_failure_reason(self) -> List[Dict[str, Any]]:
        """
        Get recovery rate broken down by failure reason
        """
        db = SessionLocal()
        try:
            results = db.query(
                RecoveryCase.failure_category,
                func.count(RecoveryCase.id).label('total_cases'),
                func.sum(case(
                    (RecoveryCase.status == RecoveryCaseStatus.RECOVERED, 1),
                    else_=0
                )).label('recovered_cases'),
                func.sum(case(
                    (RecoveryCase.status == RecoveryCaseStatus.RECOVERED, RecoveryCase.amount),
                    else_=0
                )).label('recovered_amount'),
                func.sum(RecoveryCase.amount).label('total_amount')
            ).group_by(
                RecoveryCase.failure_category
            ).all()
            
            breakdown = []
            for result in results:
                failure_reason = result.failure_category or "unknown"
                total_cases = result.total_cases
                recovered_cases = result.recovered_cases
                total_amount = float(result.total_amount) if result.total_amount else 0
                recovered_amount = float(result.recovered_amount) if result.recovered_amount else 0
                
                case_recovery_rate = (recovered_cases / total_cases * 100) if total_cases > 0 else 0
                amount_recovery_rate = (recovered_amount / total_amount * 100) if total_amount > 0 else 0
                
                breakdown.append({
                    "failure_reason": failure_reason,
                    "total_cases": total_cases,
                    "recovered_cases": recovered_cases,
                    "case_recovery_rate_percent": round(case_recovery_rate, 2),
                    "total_amount": total_amount,
                    "recovered_amount": recovered_amount,
                    "amount_recovery_rate_percent": round(amount_recovery_rate, 2)
                })
            
            return breakdown
            
        except Exception as e:
            logger.error(f"Error getting recovery by failure reason: {str(e)}")
            raise
        finally:
            db.close()
    
    def get_intervention_performance(self) -> List[Dict[str, Any]]:
        """
        Get performance of different intervention types
        """
        # This would join with recovery_actions table in a real implementation
        # For now, return placeholder data
        return [
            {
                "intervention_type": "retry",
                "attempts": 150,
                "successes": 45,
                "success_rate_percent": 30.0,
                "average_amount": 2500.0
            },
            {
                "intervention_type": "payment_link",
                "attempts": 120,
                "successes": 78,
                "success_rate_percent": 65.0,
                "average_amount": 3200.0
            },
            {
                "intervention_type": "notification",
                "attempts": 200,
                "successes": 30,
                "success_rate_percent": 15.0,
                "average_amount": 1800.0
            },
            {
                "intervention_type": "escalation",
                "attempts": 25,
                "successes": 20,
                "success_rate_percent": 80.0,
                "average_amount": 8500.0
            }
        ]

# Singleton instance
analytics_service = AnalyticsService()

def get_analytics_service():
    return analytics_service
