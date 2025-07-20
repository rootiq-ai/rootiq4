#!/usr/bin/env python3
"""
RCA System Main Application Entry Point
"""

import asyncio
import time
import threading
from datetime import datetime, timedelta
import structlog
from utils.helpers import setup_logging, check_environment, system_monitor
from database.connection import db_manager
from ingestion.ingestion_layer import IngestionLayer
from enrichment.enrichment_layer import EnrichmentLayer
from fusion.fusion_layer import FusionLayer
from rca.rca_engine import RCAEngine
from agentic.agentic_ai import AgenticAI

# Setup logging
setup_logging()
logger = structlog.get_logger(__name__)

class RCASystemOrchestrator:
    """
    Main orchestrator for the RCA system pipeline
    """
    
    def __init__(self):
        self.ingestion = IngestionLayer()
        self.enrichment = EnrichmentLayer()
        self.fusion = FusionLayer()
        self.rca_engine = RCAEngine()
        self.agentic_ai = AgenticAI()
        
        self.running = False
        self.processing_interval = 30  # seconds
        
    def start(self):
        """Start the RCA system"""
        logger.info("Starting RCA System...")
        
        # Check environment
        env_checks = check_environment()
        failed_checks = [k for k, v in env_checks.items() if not v]
        
        if failed_checks:
            logger.warning("Some environment checks failed", failed_checks=failed_checks)
        else:
            logger.info("All environment checks passed")
        
        # Initialize database
        try:
            db_manager.create_tables()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize database", error=str(e))
            return
        
        # Start processing pipeline
        self.running = True
        self._run_pipeline()
    
    def stop(self):
        """Stop the RCA system"""
        logger.info("Stopping RCA System...")
        self.running = False
    
    def _run_pipeline(self):
        """Run the continuous processing pipeline"""
        logger.info("Starting continuous processing pipeline")
        
        while self.running:
            try:
                start_time = time.time()
                
                # Step 1: Process raw events
                logger.info("Processing raw events...")
                enriched_count = len(self.enrichment.process_raw_events(limit=100))
                system_monitor.record_metric("enriched_events_batch", enriched_count)
                
                # Step 2: Create incident contexts
                logger.info("Creating incident contexts...")
                incident_count = len(self.fusion.create_incident_contexts(lookback_hours=1))
                system_monitor.record_metric("incident_contexts_batch", incident_count)
                
                # Step 3: Analyze incidents
                logger.info("Analyzing incidents...")
                analyzed_count = len(self.rca_engine.analyze_incidents(lookback_hours=1))
                system_monitor.record_metric("analyzed_incidents_batch", analyzed_count)
                
                # Step 4: Handle low-confidence incidents with agentic AI
                logger.info("Processing low-confidence incidents...")
                agentic_count = len(self.agentic_ai.analyze_low_confidence_incidents())
                system_monitor.record_metric("agentic_analyses_batch", agentic_count)
                
                # Record processing time
                processing_time = time.time() - start_time
                system_monitor.record_metric("pipeline_processing_time", processing_time)
                
                logger.info("Pipeline cycle completed", 
                           enriched=enriched_count,
                           incidents=incident_count, 
                           analyzed=analyzed_count,
                           agentic=agentic_count,
                           processing_time=f"{processing_time:.2f}s")
                
                # Wait before next cycle
                time.sleep(self.processing_interval)
                
            except KeyboardInterrupt:
                logger.info("Received interrupt signal, stopping...")
                break
            except Exception as e:
                logger.error("Error in pipeline processing", error=str(e))
                time.sleep(self.processing_interval)
        
        logger.info("Pipeline processing stopped")

def run_background_pipeline():
    """Run the pipeline in background thread"""
    orchestrator = RCASystemOrchestrator()
    orchestrator.start()

def main():
    """Main application entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RCA System")
    parser.add_argument("--mode", choices=["pipeline", "api", "dashboard"], 
                       default="pipeline", help="Run mode")
    parser.add_argument("--host", default="0.0.0.0", help="Host address")
    parser.add_argument("--port", type=int, default=8000, help="Port number")
    
    args = parser.parse_args()
    
    if args.mode == "pipeline":
        # Run continuous pipeline
        orchestrator = RCASystemOrchestrator()
        try:
            orchestrator.start()
        except KeyboardInterrupt:
            orchestrator.stop()
    
    elif args.mode == "api":
        # Run FastAPI server
        import uvicorn
        from api.endpoints import app
        
        logger.info(f"Starting API server on {args.host}:{args.port}")
        uvicorn.run(app, host=args.host, port=args.port)
    
    elif args.mode == "dashboard":
        # Run Streamlit dashboard
        import subprocess
        import sys
        
        logger.info(f"Starting Streamlit dashboard on {args.host}:{args.port}")
        cmd = [
            sys.executable, "-m", "streamlit", "run", 
            "ui/streamlit_app.py",
            "--server.address", args.host,
            "--server.port", str(args.port)
        ]
        subprocess.run(cmd)

if __name__ == "__main__":
    main()
