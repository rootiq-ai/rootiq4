from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import structlog

from database.connection import get_db
from database.models import RawEvent, EnrichedEvent, FusedContext, RCAResult
from ingestion.data_models import IncomingEvent, EventType, Severity
from ingestion.ingestion_layer import IngestionLayer
from enrichment.enrichment_layer import EnrichmentLayer
from fusion.fusion_layer import FusionLayer
from rca.rca_engine import RCAEngine
from agentic.agentic_ai import AgenticAI
from utils.helpers import system_monitor

logger = structlog.get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="RCA System API",
    description="Root Cause Analysis System API for incident management and analysis",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
ingestion = IngestionLayer()
enrichment = EnrichmentLayer()
fusion = FusionLayer()
rca_engine = RCAEngine()
agentic_ai = AgenticAI()

# Response models
class EventResponse(BaseModel):
    id: int
    event_type: str
    source: str
    timestamp: datetime
    severity: Optional[str]
    message: str

class IncidentResponse(BaseModel):
    incident_id: str
    fusion_score: float
    created_at: datetime
    semantic_context: Optional[Dict[str, Any]]
    temporal_context: Optional[Dict[str, Any]]
    causal_context: Optional[Dict[str, Any]]

class RCAResponse(BaseModel):
    incident_id: str
    root_cause: str
    confidence_score: float
    suggested_fix: str
    analysis_method: str
    created_at: datetime

class SystemStatusResponse(BaseModel):
    status: str
    uptime_seconds: float
    total_events: int
    total_incidents: int
    total_rca_results: int
    metrics: Dict[str, Any]

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": system_monitor.get_uptime()
    }

# Events endpoints
@app.post("/api/v1/events", response_model=Dict[str, Any])
async def ingest_event(event: IncomingEvent, background_tasks: BackgroundTasks):
    """
    Ingest a single event into the system
    """
    try:
        event_id = ingestion.ingest_event(event)
        
        # Trigger background processing
        background_tasks.add_task(process_event_pipeline, event_id)
        
        logger.info(f"Event ingested successfully", event_id=event_id)
        return {
            "status": "success",
            "event_id": event_id,
            "message": "Event ingested and queued for processing"
        }
    except Exception as e:
        logger.error(f"Error ingesting event: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/events/batch", response_model=Dict[str, Any])
async def ingest_events_batch(events: List[IncomingEvent], background_tasks: BackgroundTasks):
    """
    Ingest a batch of events
    """
    try:
        event_ids = ingestion.ingest_batch(events)
        
        # Trigger background processing
        background_tasks.add_task(process_events_pipeline, event_ids)
        
        logger.info(f"Batch of {len(events)} events ingested successfully")
        return {
            "status": "success",
            "event_ids": event_ids,
            "count": len(event_ids),
            "message": "Events ingested and queued for processing"
        }
    except Exception as e:
        logger.error(f"Error ingesting batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/events", response_model=List[EventResponse])
async def get_events(limit: int = 100, event_type: Optional[EventType] = None, db=Depends(get_db)):
    """
    Get recent events
    """
    try:
        query = db.query(RawEvent).order_by(RawEvent.timestamp.desc())
        
        if event_type:
            query = query.filter(RawEvent.event_type == event_type.value)
        
        events = query.limit(limit).all()
        
        return [
            EventResponse(
                id=event.id,
                event_type=event.event_type,
                source=event.source,
                timestamp=event.timestamp,
                severity=event.severity,
                message=event.message
            )
            for event in events
        ]
    except Exception as e:
        logger.error(f"Error retrieving events: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Incidents endpoints
@app.get("/api/v1/incidents", response_model=List[IncidentResponse])
async def get_incidents(limit: int = 50, db=Depends(get_db)):
    """
    Get recent incidents
    """
    try:
        incidents = db.query(FusedContext).order_by(FusedContext.created_at.desc()).limit(limit).all()
        
        return [
            IncidentResponse(
                incident_id=incident.incident_id,
                fusion_score=incident.fusion_score,
                created_at=incident.created_at,
                semantic_context=incident.semantic_context,
                temporal_context=incident.temporal_context,
                causal_context=incident.causal_context
            )
            for incident in incidents
        ]
    except Exception as e:
        logger.error(f"Error retrieving incidents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/incidents/{incident_id}", response_model=IncidentResponse)
async def get_incident(incident_id: str, db=Depends(get_db)):
    """
    Get specific incident details
    """
    try:
        incident = db.query(FusedContext).filter_by(incident_id=incident_id).first()
        
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        return IncidentResponse(
            incident_id=incident.incident_id,
            fusion_score=incident.fusion_score,
            created_at=incident.created_at,
            semantic_context=incident.semantic_context,
            temporal_context=incident.temporal_context,
            causal_context=incident.causal_context
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving incident {incident_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# RCA endpoints
@app.get("/api/v1/rca", response_model=List[RCAResponse])
async def get_rca_results(limit: int = 50, db=Depends(get_db)):
    """
    Get RCA results
    """
    try:
        results = db.query(RCAResult).order_by(RCAResult.created_at.desc()).limit(limit).all()
        
        return [
            RCAResponse(
                incident_id=result.incident_id,
                root_cause=result.root_cause,
                confidence_score=result.confidence_score,
                suggested_fix=result.suggested_fix,
                analysis_method=result.analysis_method,
                created_at=result.created_at
            )
            for result in results
        ]
    except Exception as e:
        logger.error(f"Error retrieving RCA results: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/rca/{incident_id}", response_model=RCAResponse)
async def get_rca_result(incident_id: str, db=Depends(get_db)):
    """
    Get RCA result for specific incident
    """
    try:
        result = db.query(RCAResult).filter_by(incident_id=incident_id).first()
        
        if not result:
            raise HTTPException(status_code=404, detail="RCA result not found")
        
        return RCAResponse(
            incident_id=result.incident_id,
            root_cause=result.root_cause,
            confidence_score=result.confidence_score,
            suggested_fix=result.suggested_fix,
            analysis_method=result.analysis_method,
            created_at=result.created_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving RCA result for {incident_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/rca/{incident_id}/reanalyze")
async def reanalyze_incident(incident_id: str, background_tasks: BackgroundTasks, db=Depends(get_db)):
    """
    Trigger re-analysis of an incident
    """
    try:
        # Check if incident exists
        incident = db.query(FusedContext).filter_by(incident_id=incident_id).first()
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        # Delete existing RCA result
        existing_rca = db.query(RCAResult).filter_by(incident_id=incident_id).first()
        if existing_rca:
            db.delete(existing_rca)
            db.commit()
        
        # Trigger background re-analysis
        background_tasks.add_task(reanalyze_incident_task, incident_id)
        
        return {
            "status": "success",
            "message": f"Re-analysis triggered for incident {incident_id}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering re-analysis for {incident_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# System status endpoint
@app.get("/api/v1/status", response_model=SystemStatusResponse)
async def get_system_status(db=Depends(get_db)):
    """
    Get system status and metrics
    """
    try:
        # Get counts
        total_events = db.query(RawEvent).count()
        total_incidents = db.query(FusedContext).count()
        total_rca_results = db.query(RCAResult).count()
        
        # Get system metrics
        metrics = system_monitor.get_metrics_summary()
        
        return SystemStatusResponse(
            status="operational",
            uptime_seconds=system_monitor.get_uptime(),
            total_events=total_events,
            total_incidents=total_incidents,
            total_rca_results=total_rca_results,
            metrics=metrics
        )
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Pipeline control endpoints
@app.post("/api/v1/pipeline/process")
async def trigger_pipeline_processing(background_tasks: BackgroundTasks):
    """
    Manually trigger pipeline processing
    """
    try:
        background_tasks.add_task(run_full_pipeline)
        return {
            "status": "success",
            "message": "Pipeline processing triggered"
        }
    except Exception as e:
        logger.error(f"Error triggering pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/pipeline/enrichment")
async def trigger_enrichment(background_tasks: BackgroundTasks):
    """
    Trigger enrichment processing
    """
    try:
        background_tasks.add_task(run_enrichment_step)
        return {
            "status": "success",
            "message": "Enrichment processing triggered"
        }
    except Exception as e:
        logger.error(f"Error triggering enrichment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/pipeline/fusion")
async def trigger_fusion(background_tasks: BackgroundTasks):
    """
    Trigger fusion processing
    """
    try:
        background_tasks.add_task(run_fusion_step)
        return {
            "status": "success",
            "message": "Fusion processing triggered"
        }
    except Exception as e:
        logger.error(f"Error triggering fusion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/pipeline/rca")
async def trigger_rca(background_tasks: BackgroundTasks):
    """
    Trigger RCA analysis
    """
    try:
        background_tasks.add_task(run_rca_step)
        return {
            "status": "success",
            "message": "RCA analysis triggered"
        }
    except Exception as e:
        logger.error(f"Error triggering RCA: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Background tasks
async def process_event_pipeline(event_id: int):
    """Process a single event through the pipeline"""
    try:
        logger.info(f"Processing event {event_id} through pipeline")
        # This would trigger processing for the specific event
        # For simplicity, we'll just run a mini pipeline cycle
        await run_enrichment_step()
        await run_fusion_step()
        await run_rca_step()
    except Exception as e:
        logger.error(f"Error in event pipeline processing: {e}")

async def process_events_pipeline(event_ids: List[int]):
    """Process multiple events through the pipeline"""
    try:
        logger.info(f"Processing {len(event_ids)} events through pipeline")
        await run_enrichment_step()
        await run_fusion_step()
        await run_rca_step()
    except Exception as e:
        logger.error(f"Error in batch pipeline processing: {e}")

async def reanalyze_incident_task(incident_id: str):
    """Re-analyze a specific incident"""
    try:
        logger.info(f"Re-analyzing incident {incident_id}")
        # Force re-analysis for the specific incident
        # This would need custom logic in the RCA engine
        await run_rca_step()
    except Exception as e:
        logger.error(f"Error in incident re-analysis: {e}")

async def run_full_pipeline():
    """Run the complete processing pipeline"""
    try:
        logger.info("Running full pipeline")
        
        # Step 1: Enrichment
        enriched_count = len(enrichment.process_raw_events(limit=100))
        logger.info(f"Enriched {enriched_count} events")
        
        # Step 2: Fusion
        incident_count = len(fusion.create_incident_contexts(lookback_hours=1))
        logger.info(f"Created {incident_count} incident contexts")
        
        # Step 3: RCA
        analyzed_count = len(rca_engine.analyze_incidents(lookback_hours=1))
        logger.info(f"Analyzed {analyzed_count} incidents")
        
        # Step 4: Agentic processing
        agentic_count = len(agentic_ai.analyze_low_confidence_incidents())
        logger.info(f"Processed {agentic_count} low-confidence incidents")
        
    except Exception as e:
        logger.error(f"Error in full pipeline: {e}")

async def run_enrichment_step():
    """Run enrichment step only"""
    try:
        enriched_count = len(enrichment.process_raw_events(limit=50))
        logger.info(f"Enrichment step completed: {enriched_count} events processed")
    except Exception as e:
        logger.error(f"Error in enrichment step: {e}")

async def run_fusion_step():
    """Run fusion step only"""
    try:
        incident_count = len(fusion.create_incident_contexts(lookback_hours=1))
        logger.info(f"Fusion step completed: {incident_count} contexts created")
    except Exception as e:
        logger.error(f"Error in fusion step: {e}")

async def run_rca_step():
    """Run RCA step only"""
    try:
        analyzed_count = len(rca_engine.analyze_incidents(lookback_hours=1))
        logger.info(f"RCA step completed: {analyzed_count} incidents analyzed")
    except Exception as e:
        logger.error(f"Error in RCA step: {e}")

# Error handlers
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
