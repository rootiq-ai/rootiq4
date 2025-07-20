from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum

class EventType(str, Enum):
    EVENT = "event"
    TRACE = "trace"
    METRIC = "metric"
    LOG = "log"

class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class IncomingEvent(BaseModel):
    event_type: EventType
    source: str
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)
    severity: Optional[Severity] = Severity.INFO
    message: str
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    raw_data: Optional[Dict[str, Any]] = Field(default_factory=dict)

class LogEntry(IncomingEvent):
    event_type: EventType = EventType.LOG
    log_level: Optional[str] = None
    service_name: Optional[str] = None
    trace_id: Optional[str] = None

class MetricEntry(IncomingEvent):
    event_type: EventType = EventType.METRIC
    metric_name: str
    value: float
    unit: Optional[str] = None
    tags: Optional[Dict[str, str]] = Field(default_factory=dict)

class TraceEntry(IncomingEvent):
    event_type: EventType = EventType.TRACE
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    operation_name: str
    duration_ms: Optional[float] = None

class AlertEvent(IncomingEvent):
    event_type: EventType = EventType.EVENT
    alert_name: str
    rule_id: Optional[str] = None
    threshold_value: Optional[float] = None
    current_value: Optional[float] = None
