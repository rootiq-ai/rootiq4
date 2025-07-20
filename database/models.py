from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class RawEvent(Base):
    __tablename__ = "raw_events"
    
    id = Column(Integer, primary_key=True)
    event_type = Column(String(50), nullable=False)  # event, trace, metric, log
    source = Column(String(100), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    severity = Column(String(20))
    message = Column(Text)
    metadata = Column(JSON)
    raw_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

class EnrichedEvent(Base):
    __tablename__ = "enriched_events"
    
    id = Column(Integer, primary_key=True)
    raw_event_id = Column(Integer, ForeignKey("raw_events.id"))
    correlation_id = Column(String(100))
    anomaly_score = Column(Float)
    context_data = Column(JSON)
    enrichment_metadata = Column(JSON)
    processed_at = Column(DateTime, default=datetime.utcnow)
    
    raw_event = relationship("RawEvent", backref="enriched")

class FusedContext(Base):
    __tablename__ = "fused_contexts"
    
    id = Column(Integer, primary_key=True)
    incident_id = Column(String(100), unique=True)
    temporal_context = Column(JSON)
    semantic_context = Column(JSON)
    causal_context = Column(JSON)
    fusion_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class RCAResult(Base):
    __tablename__ = "rca_results"
    
    id = Column(Integer, primary_key=True)
    incident_id = Column(String(100), ForeignKey("fused_contexts.incident_id"))
    root_cause = Column(Text)
    confidence_score = Column(Float)
    suggested_fix = Column(Text)
    analysis_method = Column(String(50))  # llm, agentic
    llm_reasoning = Column(Text)
    vector_matches = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    fused_context = relationship("FusedContext", backref="rca_results")

class AgenticInvocation(Base):
    __tablename__ = "agentic_invocations"
    
    id = Column(Integer, primary_key=True)
    incident_id = Column(String(100))
    tools_used = Column(JSON)
    external_context = Column(JSON)
    analysis_result = Column(Text)
    confidence_improvement = Column(Float)
    execution_time_seconds = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class HistoricalPattern(Base):
    __tablename__ = "historical_patterns"
    
    id = Column(Integer, primary_key=True)
    pattern_signature = Column(String(200))
    incident_context = Column(JSON)
    resolution_steps = Column(JSON)
    success_rate = Column(Float)
    embedding_vector = Column(JSON)  # Store embedding as JSON for ChromaDB sync
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
