import structlog
import uuid
import yaml
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
from database.connection import db_manager
from database.models import RawEvent, EnrichedEvent
import numpy as np

logger = structlog.get_logger(__name__)

class EnrichmentLayer:
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)
        
        self.db_manager = db_manager
        self.correlation_window = self.config['enrichment']['correlation_window_minutes']
        self.anomaly_threshold = self.config['enrichment']['anomaly_threshold']
    
    def process_raw_events(self, limit: int = 100) -> List[int]:
        """
        Process unprocessed raw events and create enriched events
        Returns list of enriched event IDs
        """
        session = self.db_manager.get_session()
        try:
            # Get raw events that haven't been processed yet
            unprocessed_events = session.query(RawEvent).filter(
                ~RawEvent.id.in_(
                    session.query(EnrichedEvent.raw_event_id)
                )
            ).order_by(RawEvent.timestamp.desc()).limit(limit).all()
            
            enriched_ids = []
            for raw_event in unprocessed_events:
                enriched_id = self._enrich_single_event(session, raw_event)
                if enriched_id:
                    enriched_ids.append(enriched_id)
            
            session.commit()
            logger.info(f"Processed {len(enriched_ids)} raw events")
            return enriched_ids
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error processing raw events: {e}")
            raise
        finally:
            session.close()
    
    def _enrich_single_event(self, session: Session, raw_event: RawEvent) -> Optional[int]:
        """
        Enrich a single raw event with correlation and anomaly detection
        """
        try:
            # Generate correlation ID for related events
            correlation_id = self._generate_correlation_id(session, raw_event)
            
            # Calculate anomaly score
            anomaly_score = self._calculate_anomaly_score(session, raw_event)
            
            # Generate context data
            context_data = self._generate_context_data(session, raw_event)
            
            # Create enriched event
            enriched_event = EnrichedEvent(
                raw_event_id=raw_event.id,
                correlation_id=correlation_id,
                anomaly_score=anomaly_score,
                context_data=context_data,
                enrichment_metadata={
                    "enrichment_version": "1.0",
                    "correlation_window_minutes": self.correlation_window,
                    "anomaly_threshold": self.anomaly_threshold
                }
            )
            
            session.add(enriched_event)
            return enriched_event.id
            
        except Exception as e:
            logger.error(f"Error enriching event {raw_event.id}: {e}")
            return None
    
    def _generate_correlation_id(self, session: Session, raw_event: RawEvent) -> str:
        """
        Generate correlation ID by finding related events within time window
        """
        # Time window for correlation
        time_start = raw_event.timestamp - timedelta(minutes=self.correlation_window)
        time_end = raw_event.timestamp + timedelta(minutes=self.correlation_window)
        
        # Find related events by source, severity, or metadata similarity
        related_events = session.query(EnrichedEvent).join(RawEvent).filter(
            and_(
                RawEvent.timestamp >= time_start,
                RawEvent.timestamp <= time_end,
                RawEvent.id != raw_event.id
            )
        ).all()
        
        # Check for existing correlation groups
        for related in related_events:
            related_raw = related.raw_event
            if self._events_are_related(raw_event, related_raw):
                return related.correlation_id
        
        # No related events found, create new correlation ID
        return str(uuid.uuid4())
    
    def _events_are_related(self, event1: RawEvent, event2: RawEvent) -> bool:
        """
        Determine if two events are related based on various factors
        """
        # Same source
        if event1.source == event2.source:
            return True
        
        # Similar severity levels
        severity_groups = [
            ["critical", "high"],
            ["medium", "low", "info"]
        ]
        
        for group in severity_groups:
            if event1.severity in group and event2.severity in group:
                return True
        
        # Check metadata similarity (simplified)
        if event1.metadata and event2.metadata:
            common_keys = set(event1.metadata.keys()) & set(event2.metadata.keys())
            if len(common_keys) >= 2:  # At least 2 common metadata keys
                return True
        
        return False
    
    def _calculate_anomaly_score(self, session: Session, raw_event: RawEvent) -> float:
        """
        Calculate anomaly score based on historical patterns
        """
        # Get historical events from same source
        historical_events = session.query(RawEvent).filter(
            and_(
                RawEvent.source == raw_event.source,
                RawEvent.event_type == raw_event.event_type,
                RawEvent.timestamp < raw_event.timestamp
            )
        ).order_by(RawEvent.timestamp.desc()).limit(100).all()
        
        if len(historical_events) < 10:
            return 0.5  # Not enough historical data
        
        # Simple anomaly detection based on message similarity and frequency
        similar_messages = [
            event for event in historical_events 
            if self._message_similarity(raw_event.message, event.message) > 0.7
        ]
        
        # Calculate frequency-based anomaly score
        frequency = len(similar_messages) / len(historical_events)
        
        # Lower frequency = higher anomaly score
        anomaly_score = max(0.0, min(1.0, 1.0 - (frequency * 2)))
        
        return anomaly_score
    
    def _message_similarity(self, msg1: str, msg2: str) -> float:
        """
        Simple message similarity calculation
        """
        if not msg1 or not msg2:
            return 0.0
        
        words1 = set(msg1.lower().split())
        words2 = set(msg2.lower().split())
        
        intersection = words1 & words2
        union = words1 | words2
        
        if not union:
            return 0.0
        
        return len(intersection) / len(union)
    
    def _generate_context_data(self, session: Session, raw_event: RawEvent) -> Dict[str, Any]:
        """
        Generate contextual data for the event
        """
        context = {
            "event_frequency": self._get_event_frequency(session, raw_event),
            "related_services": self._get_related_services(session, raw_event),
            "time_context": self._get_time_context(raw_event),
            "severity_context": self._get_severity_context(session, raw_event)
        }
        
        return context
    
    def _get_event_frequency(self, session: Session, raw_event: RawEvent) -> Dict[str, Any]:
        """
        Get frequency analysis for this type of event
        """
        # Count similar events in last hour, day, week
        now = raw_event.timestamp
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(weeks=1)
        
        hour_count = session.query(RawEvent).filter(
            and_(
                RawEvent.source == raw_event.source,
                RawEvent.event_type == raw_event.event_type,
                RawEvent.timestamp >= hour_ago,
                RawEvent.timestamp < now
            )
        ).count()
        
        day_count = session.query(RawEvent).filter(
            and_(
                RawEvent.source == raw_event.source,
                RawEvent.event_type == raw_event.event_type,
                RawEvent.timestamp >= day_ago,
                RawEvent.timestamp < now
            )
        ).count()
        
        week_count = session.query(RawEvent).filter(
            and_(
                RawEvent.source == raw_event.source,
                RawEvent.event_type == raw_event.event_type,
                RawEvent.timestamp >= week_ago,
                RawEvent.timestamp < now
            )
        ).count()
        
        return {
            "last_hour": hour_count,
            "last_day": day_count,
            "last_week": week_count
        }
    
    def _get_related_services(self, session: Session, raw_event: RawEvent) -> List[str]:
        """
        Get list of related services based on recent events
        """
        time_window = raw_event.timestamp - timedelta(minutes=self.correlation_window)
        
        related_sources = session.query(RawEvent.source).filter(
            and_(
                RawEvent.timestamp >= time_window,
                RawEvent.timestamp <= raw_event.timestamp,
                RawEvent.source != raw_event.source
            )
        ).distinct().all()
        
        return [source[0] for source in related_sources]
    
    def _get_time_context(self, raw_event: RawEvent) -> Dict[str, Any]:
        """
        Get temporal context (business hours, weekend, etc.)
        """
        timestamp = raw_event.timestamp
        
        return {
            "hour_of_day": timestamp.hour,
            "day_of_week": timestamp.weekday(),
            "is_business_hours": 9 <= timestamp.hour <= 17,
            "is_weekend": timestamp.weekday() >= 5
        }
    
    def _get_severity_context(self, session: Session, raw_event: RawEvent) -> Dict[str, Any]:
        """
        Get severity context compared to recent events
        """
        recent_events = session.query(RawEvent).filter(
            and_(
                RawEvent.timestamp >= raw_event.timestamp - timedelta(hours=1),
                RawEvent.timestamp <= raw_event.timestamp
            )
        ).all()
        
        severity_counts = {}
        for event in recent_events:
            severity_counts[event.severity] = severity_counts.get(event.severity, 0) + 1
        
        return {
            "recent_severity_distribution": severity_counts,
            "is_severity_escalation": self._is_severity_escalation(raw_event, recent_events)
        }
    
    def _is_severity_escalation(self, raw_event: RawEvent, recent_events: List[RawEvent]) -> bool:
        """
        Determine if this event represents a severity escalation
        """
        severity_order = {"info": 1, "low": 2, "medium": 3, "high": 4, "critical": 5}
        current_severity = severity_order.get(raw_event.severity, 1)
        
        for event in recent_events:
            if event.source == raw_event.source:
                event_severity = severity_order.get(event.severity, 1)
                if current_severity > event_severity:
                    return True
        
        return False
