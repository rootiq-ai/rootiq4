import structlog
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from database.connection import db_manager
from database.models import RawEvent
from ingestion.data_models import IncomingEvent, EventType
import json

logger = structlog.get_logger(__name__)

class IngestionLayer:
    def __init__(self):
        self.db_manager = db_manager
    
    def ingest_event(self, event: IncomingEvent) -> int:
        """
        Ingest a single event into the database
        Returns the ID of the created raw event
        """
        session = self.db_manager.get_session()
        try:
            raw_event = RawEvent(
                event_type=event.event_type.value,
                source=event.source,
                timestamp=event.timestamp,
                severity=event.severity.value if event.severity else None,
                message=event.message,
                metadata=event.metadata,
                raw_data=event.raw_data
            )
            
            session.add(raw_event)
            session.commit()
            
            event_id = raw_event.id
            logger.info(f"Ingested event", event_id=event_id, event_type=event.event_type, source=event.source)
            return event_id
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error ingesting event: {e}")
            raise
        finally:
            session.close()
    
    def ingest_batch(self, events: List[IncomingEvent]) -> List[int]:
        """
        Ingest a batch of events into the database
        Returns list of created event IDs
        """
        session = self.db_manager.get_session()
        try:
            raw_events = []
            for event in events:
                raw_event = RawEvent(
                    event_type=event.event_type.value,
                    source=event.source,
                    timestamp=event.timestamp,
                    severity=event.severity.value if event.severity else None,
                    message=event.message,
                    metadata=event.metadata,
                    raw_data=event.raw_data
                )
                raw_events.append(raw_event)
            
            session.add_all(raw_events)
            session.commit()
            
            event_ids = [event.id for event in raw_events]
            logger.info(f"Ingested batch of {len(events)} events", event_ids=event_ids)
            return event_ids
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error ingesting batch: {e}")
            raise
        finally:
            session.close()
    
    def get_recent_events(self, limit: int = 100, event_type: EventType = None) -> List[RawEvent]:
        """
        Retrieve recent events from the database
        """
        session = self.db_manager.get_session()
        try:
            query = session.query(RawEvent).order_by(RawEvent.timestamp.desc())
            
            if event_type:
                query = query.filter(RawEvent.event_type == event_type.value)
            
            events = query.limit(limit).all()
            return events
            
        except Exception as e:
            logger.error(f"Error retrieving events: {e}")
            raise
        finally:
            session.close()
    
    def create_sample_events(self) -> List[int]:
        """
        Create sample events for testing
        """
        sample_events = [
            IncomingEvent(
                event_type=EventType.EVENT,
                source="prometheus",
                severity="critical",
                message="High CPU usage detected",
                metadata={"cpu_usage": 95.5, "instance": "web-server-01"},
                raw_data={"alert": "HighCPUUsage", "threshold": 90}
            ),
            IncomingEvent(
                event_type=EventType.LOG,
                source="application",
                severity="high",
                message="Database connection timeout",
                metadata={"service": "user-service", "database": "postgres"},
                raw_data={"error_code": "CONN_TIMEOUT", "retry_count": 3}
            ),
            IncomingEvent(
                event_type=EventType.METRIC,
                source="grafana",
                severity="medium",
                message="Response time increased",
                metadata={"endpoint": "/api/users", "response_time_ms": 1500},
                raw_data={"metric": "http_request_duration", "value": 1.5}
            ),
            IncomingEvent(
                event_type=EventType.TRACE,
                source="jaeger",
                severity="info",
                message="Slow database query detected",
                metadata={"trace_id": "abc123", "duration_ms": 2000},
                raw_data={"operation": "db.query", "table": "users"}
            )
        ]
        
        return self.ingest_batch(sample_events)
