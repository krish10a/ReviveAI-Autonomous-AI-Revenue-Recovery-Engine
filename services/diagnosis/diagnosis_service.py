"""
Failure diagnosis service
"""
import logging

logger = logging.getLogger(__name__)

class FailureDiagnosisService:
    def diagnose_failure(self, payment_data):
        """
        Diagnose payment failure - simplified version
        """
        logger.info("Diagnosing payment failure")
        # Simplified diagnosis - in production would use rules + LLM
        return {
            "category": "insufficient_funds",
            "confidence": 0.8,
            "customer_action_required": True,
            "recommended_delay_minutes": 60,
            "source": "rule"
        }

# Singleton instance
failure_diagnosis_service = FailureDiagnosisService()

def get_failure_diagnosis_service():
    return failure_diagnosis_service
