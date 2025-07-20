import pytest
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.data_models import IncomingEvent, EventType, Severity
from ingestion.ingestion_layer import IngestionLayer
from database.connection import db_manager
from database.models import RawEvent

class TestIngestionLayer:
    """Test suite for the ingestion layer"""
    
    @pytest.fixture(autouse=True)
    def setup_database(self):
        """Setup test database before each test"""
        try:
            db_manager.create_tables()
        except Exception:
            pass  # Tables might already exist
        
        yield
        
        # Cleanup after test
        session = db_manager.get_session()
        try:
            session.query(RawEvent).delete()
            session.commit()
        finally:
            session.close()
    
    def test_create_incoming_event(self):
        """Test creating an incoming event model"""
        event = IncomingEvent(
            event_type=EventType.EVENT,
            source="test-source",
            severity=Severity.HIGH,
            message="Test message",
            metadata={"test": "data"},
            raw_data={"raw": "test"}
        )
        
        assert event.event_type == EventType.EVENT
        assert event.source == "test-source"
        assert event.severity == Severity.HIGH
        assert event.message == "Test message"
        assert event.metadata == {"test": "data"}
        assert event.raw_data == {"raw": "test"}
    
    def test_ingest_single_event(self):
        """Test ingesting a single event"""
        ingestion = IngestionLayer()
        
        event = IncomingEvent(
            event_type=EventType.LOG,
            source="application",
            severity=Severity.CRITICAL,
            message="Database connection failed",
            metadata={"service": "user-service", "database": "postgres"},
            raw_data={"error_code": "CONN_FAILED"}
        )
        
        event_id = ingestion.ingest_event(event)
        
        assert isinstance(event_id, int)
        assert event_id > 0
        
        # Verify event was stored
        session = db_manager.get_session()
        try:
            stored_event = session.query(RawEvent).filter_by(id=event_id).first()
            assert stored_event is not None
            assert stored_event.event_type == "log"
            assert stored_event.source == "application"
            assert stored_event.severity == "critical"
            assert stored_event.message == "Database connection failed"
            assert stored_event.metadata["service"] == "user-service"
            assert stored_event.raw_data["error_code"] == "CONN_FAILED"
        finally:
            session.close()
    
    def test_ingest_batch_events(self):
        """Test ingesting multiple events"""
        ingestion = IngestionLayer()
        
        events = [
            IncomingEvent(
                event_type=EventType.METRIC,
                source="prometheus",
                severity=Severity.MEDIUM,
                message="High CPU usage",
                metadata={"cpu_usage": 85.5}
            ),
            IncomingEvent(
                event_type=EventType.TRACE,
                source="jaeger",
                severity=Severity.LOW,
                message="Slow API call",
                metadata={"duration_ms": 2000}
            ),
            IncomingEvent(
                event_type=EventType.EVENT,
                source="kubernetes",
                severity=Severity.HIGH,
                message="Pod restart",
                metadata={"pod": "web-server-1", "namespace": "production"}
            )
        ]
        
        event_ids = ingestion.ingest_batch(events)
        
        assert len(event_ids) == 3
        assert all(isinstance(eid, int) for eid in event_ids)
        
        # Verify all events were stored
        session = db_manager.get_session()
        try:
            stored_events = session.query(RawEvent).filter(RawEvent.id.in_(event_ids)).all()
            assert len(stored_events) == 3
            
            sources = [event.source for event in stored_events]
            assert "prometheus" in sources
            assert "jaeger" in sources
            assert "kubernetes" in sources
        finally:
            session.close()
    
    def test_get_recent_events(self):
        """Test retrieving recent events"""
        ingestion = IngestionLayer()
        
        # Ingest some test events
        test_events = [
            IncomingEvent(
                event_type=EventType.LOG,
                source="app1",
                message="Test log 1"
            ),
            IncomingEvent(
                event_type=EventType.METRIC,
                source="app2",
                message="Test metric 1"
            ),
            IncomingEvent(
                event_type=EventType.LOG,
                source="app1",
                message="Test log 2"
            )
        ]
        
        ingestion.ingest_batch(test_events)
        
        # Test getting all recent events
        recent_events = ingestion.get_recent_events(limit=10)
        assert len(recent_events) >= 3
        
        # Test filtering by event type
        log_events = ingestion.get_recent_events(limit=10, event_type=EventType.LOG)
        assert len(log_events) >= 2
        assert all(event.event_type == "log" for event in log_events)
        
        metric_events = ingestion.get_recent_events(limit=10, event_type=EventType.METRIC)
        assert len(metric_events) >= 1
        assert all(event.event_type == "metric" for event in metric_events)
    
    def test_event_timestamps(self):
        """Test that events have proper timestamps"""
        ingestion = IngestionLayer()
        
        # Test with auto-generated timestamp
        event1 = IncomingEvent(
            event_type=EventType.EVENT,
            source="test",
            message="Auto timestamp"
        )
        
        event_id1 = ingestion.ingest_event(event1)
        
        # Test with custom timestamp
        custom_time = datetime(2024, 1, 15, 12, 0, 0)
        event2 = IncomingEvent(
            event_type=EventType.EVENT,
            source="test",
            message="Custom timestamp",
            timestamp=custom_time
        )
        
        event_id2 = ingestion.ingest_event(event2)
        
        # Verify timestamps
        session = db_manager.get_session()
        try:
            stored_event1 = session.query(RawEvent).filter_by(id=event_id1).first()
            stored_event2 = session.query(RawEvent).filter_by(id=event_id2).first()
            
            assert stored_event1.timestamp is not None
            assert stored_event2.timestamp == custom_time
        finally:
            session.close()
    
    def test_create_sample_events(self):
        """Test sample event generation"""
        ingestion = IngestionLayer()
        
        event_ids = ingestion.create_sample_events()
        
        assert len(event_ids) > 0
        assert all(isinstance(eid, int) for eid in event_ids)
        
        # Verify sample events were created
        session = db_manager.get_session()
        try:
            sample_events = session.query(RawEvent).filter(RawEvent.id.in_(event_ids)).all()
            assert len(sample_events) == len(event_ids)
            
            # Check that we have different event types
            event_types = set(event.event_type for event in sample_events)
            assert len(event_types) > 1  # Should have multiple types
            
            # Check that all events have required fields
            for event in sample_events:
                assert event.source is not None
                assert event.message is not None
                assert event.timestamp is not None
        finally:
            session.close()

class TestEventModels:
    """Test suite for event data models"""
    
    def test_event_type_enum(self):
        """Test EventType enum values"""
        assert EventType.EVENT == "event"
        assert EventType.TRACE == "trace" 
        assert EventType.METRIC == "metric"
        assert EventType.LOG == "log"
    
    def test_severity_enum(self):
        """Test Severity enum values"""
        assert Severity.CRITICAL == "critical"
        assert Severity.HIGH == "high"
        assert Severity.MEDIUM == "medium"
        assert Severity.LOW == "low"
        assert Severity.INFO == "info"
    
    def test_incoming_event_defaults(self):
        """Test IncomingEvent default values"""
        event = IncomingEvent(
            event_type=EventType.LOG,
            source="test",
            message="test message"
        )
        
        assert event.severity == Severity.INFO
        assert event.metadata == {}
        assert event.raw_data == {}
        assert event.timestamp is not None
        assert isinstance(event.timestamp, datetime)
    
    def test_log_entry_model(self):
        """Test LogEntry specialized model"""
        from ingestion.data_models import LogEntry
        
        log_entry = LogEntry(
            source="application",
            message="Test log message",
            log_level="ERROR",
            service_name="user-service",
            trace_id="abc123"
        )
        
        assert log_entry.event_type == EventType.LOG
        assert log_entry.log_level == "ERROR"
        assert log_entry.service_name == "user-service"
        assert log_entry.trace_id == "abc123"
    
    def test_metric_entry_model(self):
        """Test MetricEntry specialized model"""
        from ingestion.data_models import MetricEntry
        
        metric_entry = MetricEntry(
            source="prometheus",
            message="CPU usage metric",
            metric_name="cpu_usage_percent",
            value=85.5,
            unit="percent",
            tags={"instance": "web-01", "region": "us-east-1"}
        )
        
        assert metric_entry.event_type == EventType.METRIC
        assert metric_entry.metric_name == "cpu_usage_percent"
        assert metric_entry.value == 85.5
        assert metric_entry.unit == "percent"
        assert metric_entry.tags["instance"] == "web-01"
    
    def test_trace_entry_model(self):
        """Test TraceEntry specialized model"""
        from ingestion.data_models import TraceEntry
        
        trace_entry = TraceEntry(
            source="jaeger",
            message="API call trace",
            trace_id="trace123",
            span_id="span456",
            parent_span_id="span789",
            operation_name="get_user",
            duration_ms=150.5
        )
        
        assert trace_entry.event_type == EventType.TRACE
        assert trace_entry.trace_id == "trace123"
        assert trace_entry.span_id == "span456"
        assert trace_entry.parent_span_id == "span789"
        assert trace_entry.operation_name == "get_user"
        assert trace_entry.duration_ms == 150.5
    
    def test_alert_event_model(self):
        """Test AlertEvent specialized model"""
        from ingestion.data_models import AlertEvent
        
        alert_event = AlertEvent(
            source="prometheus",
            message="High CPU alert",
            alert_name="HighCPUUsage",
            rule_id="cpu_rule_001",
            threshold_value=80.0,
            current_value=95.5,
            severity=Severity.CRITICAL
        )
        
        assert alert_event.event_type == EventType.EVENT
        assert alert_event.alert_name == "HighCPUUsage"
        assert alert_event.rule_id == "cpu_rule_001"
        assert alert_event.threshold_value == 80.0
        assert alert_event.current_value == 95.5

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
