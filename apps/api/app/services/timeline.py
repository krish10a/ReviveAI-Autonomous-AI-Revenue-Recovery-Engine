"""
Timeline service for recording events in the recovery process.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models.timeline_event import TimelineEvent
from ..models.recovery_case import RecoveryCase

logger = logging.getLogger(__name__)

class TimelineService:
    def add_event_to_timeline(self, case_id: int, actor: str, action: str,
                             input_data: Optional[Dict[str, Any]] = None,
                             decision_data: Optional[Dict[str, Any]] = None,
                             db: Optional[Session] = None) -> TimelineEvent:
        logger.debug(f"Adding timeline event for case {case_id}: {actor} -> {action}")

        should_close = False
        if db is None:
            db = SessionLocal()
            should_close = True
        try:
            # Verify the case exists
            recovery_case = db.query(RecoveryCase).filter(
                RecoveryCase.id == case_id
            ).first()

            if not recovery_case:
                raise ValueError(f"Recovery case {case_id} not found")

            import json
            # Create the timeline event
            timeline_event = TimelineEvent(
                case_id=case_id,
                actor=actor,
                action=action,
                input_json=json.dumps(input_data) if input_data is not None else None,
                decision_json=json.dumps(decision_data) if decision_data is not None else None
            )

            db.add(timeline_event)
            if should_close:
                db.commit()
                db.refresh(timeline_event)
            else:
                db.flush()

            return timeline_event

        except Exception as e:
            db.rollback()
            logger.error(f"Error adding timeline event for case {case_id}: {str(e)}")
            raise
        finally:
            if should_close:
                db.close()

    def get_timeline_for_case(self, case_id: int) -> List[TimelineEvent]:
        """
        Get all timeline events for a recovery case, ordered by timestamp.

        Args:
            case_id: ID of the recovery case

        Returns:
            List[TimelineEvent]: List of timeline events ordered by timestamp (oldest first)
        """
        db = SessionLocal()
        try:
            events = db.query(TimelineEvent).filter(
                TimelineEvent.case_id == case_id
            ).order_by(TimelineEvent.timestamp.asc(), TimelineEvent.id.asc()).all()

            return events
        finally:
            db.close()

    def get_timeline_for_scenario(self, scenario_key: str) -> List[TimelineEvent]:
        """
        Get timeline events for a canonical benchmark scenario by key.
        """
        db = SessionLocal()
        try:
            case = db.query(RecoveryCase).filter(
                RecoveryCase.scenario_key == scenario_key
            ).first()
            if not case:
                return []
            return db.query(TimelineEvent).filter(
                TimelineEvent.case_id == case.id
            ).order_by(TimelineEvent.timestamp.asc(), TimelineEvent.id.asc()).all()
        finally:
            db.close()

# Singleton instance
timeline_service = TimelineService()

def get_timeline_service():
    return timeline_service