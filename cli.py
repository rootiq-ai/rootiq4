#!/usr/bin/env python3
"""
RCA System CLI Management Tool
"""

import click
import yaml
import json
import sys
from datetime import datetime, timedelta
from tabulate import tabulate
import structlog

from utils.helpers import setup_logging, check_environment, system_monitor
from database.connection import db_manager
from database.models import RawEvent, EnrichedEvent, FusedContext, RCAResult, AgenticInvocation
from ingestion.ingestion_layer import IngestionLayer
from enrichment.enrichment_layer import EnrichmentLayer
from fusion.fusion_layer import FusionLayer
from rca.rca_engine import RCAEngine
from rca.vector_store import VectorStore
from agentic.agentic_ai import AgenticAI

# Setup logging
setup_logging()
logger = structlog.get_logger(__name__)

@click.group()
def cli():
    """RCA System CLI Management Tool"""
    pass

@cli.group()
def setup():
    """Setup and initialization commands"""
    pass

@cli.group()
def status():
    """System status commands"""
    pass

@cli.group()
def data():
    """Data management commands"""
    pass

@cli.group()
def pipeline():
    """Pipeline management commands"""
    pass

# Setup commands
@setup.command()
def init():
    """Initialize the system (create database tables)"""
    click.echo("🔧 Initializing RCA System...")
    
    try:
        db_manager.create_tables()
        click.echo("✅ Database tables created successfully")
    except Exception as e:
        click.echo(f"❌ Error creating database tables: {e}")
        sys.exit(1)

@setup.command()
def check():
    """Check system environment and dependencies"""
    click.echo("🔍 Checking system environment...")
    
    env_checks = check_environment()
    
    click.echo("\nEnvironment Checks:")
    for check_name, status in env_checks.items():
        status_icon = "✅" if status else "❌"
        click.echo(f"  {status_icon} {check_name}: {'PASS' if status else 'FAIL'}")
    
    failed_checks = [k for k, v in env_checks.items() if not v]
    
    if failed_checks:
        click.echo(f"\n⚠️  {len(failed_checks)} checks failed. Please resolve before continuing.")
        sys.exit(1)
    else:
        click.echo("\n✅ All environment checks passed!")

@setup.command()
def sample_data():
    """Generate sample data for testing"""
    click.echo("📝 Generating sample data...")
    
    try:
        # Create sample events
        ingestion = IngestionLayer()
        event_ids = ingestion.create_sample_events()
        click.echo(f"✅ Created {len(event_ids)} sample events")
        
        # Add sample vector patterns
        vector_store = VectorStore()
        pattern_ids = vector_store.add_sample_patterns()
        click.echo(f"✅ Added {len(pattern_ids)} sample patterns to vector store")
        
        click.echo("🎉 Sample data generation completed!")
        
    except Exception as e:
        click.echo(f"❌ Error generating sample data: {e}")
        sys.exit(1)

# Status commands
@status.command()
def system():
    """Show overall system status"""
    click.echo("📊 System Status Report")
    click.echo("=" * 50)
    
    try:
        session = db_manager.get_session()
        
        # Database counts
        raw_events = session.query(RawEvent).count()
        enriched_events = session.query(EnrichedEvent).count()
        incidents = session.query(FusedContext).count()
        rca_results = session.query(RCAResult).count()
        agentic_invocations = session.query(AgenticInvocation).count()
        
        session.close()
        
        # System metrics
        uptime = system_monitor.get_uptime()
        
        data = [
            ["Raw Events", raw_events],
            ["Enriched Events", enriched_events],
            ["Incidents", incidents],
            ["RCA Results", rca_results],
            ["Agentic Invocations", agentic_invocations],
            ["System Uptime", f"{uptime:.1f} seconds"]
        ]
        
        click.echo(tabulate(data, headers=["Metric", "Value"], tablefmt="grid"))
        
        # Processing rates
        if incidents > 0:
            resolution_rate = (rca_results / incidents) * 100
            click.echo(f"\n📈 Resolution Rate: {resolution_rate:.1f}%")
        
        # Vector store stats
        try:
            vector_store = VectorStore()
            vector_stats = vector_store.get_collection_stats()
            click.echo(f"🧠 Vector Store Patterns: {vector_stats['total_patterns']}")
        except Exception as e:
            click.echo(f"⚠️  Vector Store Error: {e}")
        
    except Exception as e:
        click.echo(f"❌ Error getting system status: {e}")
        sys.exit(1)

@status.command()
def recent():
    """Show recent activity"""
    click.echo("📋 Recent Activity (Last 24 hours)")
    click.echo("=" * 60)
    
    try:
        session = db_manager.get_session()
        cutoff = datetime.utcnow() - timedelta(days=1)
        
        # Recent events
        recent_events = session.query(RawEvent).filter(
            RawEvent.timestamp >= cutoff
        ).order_by(RawEvent.timestamp.desc()).limit(10).all()
        
        if recent_events:
            click.echo("\n🔔 Recent Events:")
            event_data = []
            for event in recent_events:
                event_data.append([
                    event.timestamp.strftime("%H:%M:%S"),
                    event.event_type,
                    event.source,
                    event.severity or "N/A",
                    event.message[:50] + "..." if len(event.message) > 50 else event.message
                ])
            
            click.echo(tabulate(event_data, 
                              headers=["Time", "Type", "Source", "Severity", "Message"],
                              tablefmt="grid"))
        
        # Recent incidents
        recent_incidents = session.query(FusedContext).filter(
            FusedContext.created_at >= cutoff
        ).order_by(FusedContext.created_at.desc()).limit(5).all()
        
        if recent_incidents:
            click.echo("\n🚨 Recent Incidents:")
            incident_data = []
            for incident in recent_incidents:
                rca_result = session.query(RCAResult).filter_by(
                    incident_id=incident.incident_id
                ).first()
                
                status = "Resolved" if rca_result and rca_result.confidence_score >= 0.8 else "Pending"
                confidence = f"{rca_result.confidence_score:.2f}" if rca_result else "N/A"
                
                incident_data.append([
                    incident.created_at.strftime("%H:%M:%S"),
                    incident.incident_id[:8] + "...",
                    f"{incident.fusion_score:.2f}",
                    status,
                    confidence
                ])
            
            click.echo(tabulate(incident_data,
                              headers=["Time", "Incident ID", "Fusion Score", "Status", "Confidence"],
                              tablefmt="grid"))
        
        session.close()
        
    except Exception as e:
        click.echo(f"❌ Error getting recent activity: {e}")
        sys.exit(1)

# Data commands
@data.command()
@click.option('--limit', default=100, help='Number of events to show')
@click.option('--type', help='Filter by event type')
def events(limit, type):
    """List recent events"""
    click.echo(f"📋 Recent Events (limit: {limit})")
    
    try:
        ingestion = IngestionLayer()
        from ingestion.data_models import EventType
        
        event_type = EventType(type) if type else None
        events = ingestion.get_recent_events(limit=limit, event_type=event_type)
        
        if not events:
            click.echo("No events found.")
            return
        
        event_data = []
        for event in events:
            event_data.append([
                event.id,
                event.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                event.event_type,
                event.source,
                event.severity or "N/A",
                event.message[:60] + "..." if len(event.message) > 60 else event.message
            ])
        
        click.echo(tabulate(event_data,
                          headers=["ID", "Timestamp", "Type", "Source", "Severity", "Message"],
                          tablefmt="grid"))
        
    except Exception as e:
        click.echo(f"❌ Error listing events: {e}")
        sys.exit(1)

@data.command()
@click.option('--limit', default=20, help='Number of incidents to show')
def incidents(limit):
    """List recent incidents"""
    click.echo(f"🚨 Recent Incidents (limit: {limit})")
    
    try:
        session = db_manager.get_session()
        
        incidents = session.query(FusedContext).order_by(
            FusedContext.created_at.desc()
        ).limit(limit).all()
        
        if not incidents:
            click.echo("No incidents found.")
            session.close()
            return
        
        incident_data = []
        for incident in incidents:
            # Get RCA result if available
            rca_result = session.query(RCAResult).filter_by(
                incident_id=incident.incident_id
            ).first()
            
            category = "unknown"
            if incident.semantic_context and 'incident_category' in incident.semantic_context:
                category = incident.semantic_context['incident_category']
            
            status = "Resolved" if rca_result and rca_result.confidence_score >= 0.8 else "Pending"
            confidence = f"{rca_result.confidence_score:.2f}" if rca_result else "N/A"
            
            incident_data.append([
                incident.incident_id[:12] + "...",
                incident.created_at.strftime("%Y-%m-%d %H:%M"),
                f"{incident.fusion_score:.2f}",
                category,
                status,
                confidence
            ])
        
        click.echo(tabulate(incident_data,
                          headers=["Incident ID", "Created", "Fusion Score", "Category", "Status", "Confidence"],
                          tablefmt="grid"))
        
        session.close()
        
    except Exception as e:
        click.echo(f"❌ Error listing incidents: {e}")
        sys.exit(1)

@data.command()
@click.argument('incident_id')
def incident(incident_id):
    """Show detailed incident information"""
    click.echo(f"🔍 Incident Details: {incident_id}")
    click.echo("=" * 60)
    
    try:
        rca_engine = RCAEngine()
        rca_result = rca_engine.get_incident_rca(incident_id)
        
        if not rca_result:
            click.echo("❌ Incident not found or no RCA result available")
            sys.exit(1)
        
        click.echo(f"📅 Created: {rca_result['created_at']}")
        click.echo(f"🎯 Confidence: {rca_result['confidence_score']:.2f}")
        click.echo(f"🔧 Method: {rca_result['analysis_method']}")
        
        click.echo(f"\n🔍 Root Cause:")
        click.echo(rca_result['root_cause'])
        
        click.echo(f"\n💡 Suggested Fix:")
        click.echo(rca_result['suggested_fix'])
        
        if rca_result.get('llm_reasoning'):
            click.echo(f"\n🧠 Analysis Reasoning:")
            click.echo(rca_result['llm_reasoning'][:500] + "..." if len(rca_result['llm_reasoning']) > 500 else rca_result['llm_reasoning'])
        
    except Exception as e:
        click.echo(f"❌ Error getting incident details: {e}")
        sys.exit(1)

@data.command()
def cleanup():
    """Clean up old data (>30 days)"""
    click.echo("🧹 Cleaning up old data...")
    
    if not click.confirm("This will delete data older than 30 days. Continue?"):
        click.echo("Operation cancelled.")
        return
    
    try:
        session = db_manager.get_session()
        cutoff = datetime.utcnow() - timedelta(days=30)
        
        # Count records to be deleted
        old_events = session.query(RawEvent).filter(RawEvent.timestamp < cutoff).count()
        old_contexts = session.query(FusedContext).filter(FusedContext.created_at < cutoff).count()
        
        if old_events == 0 and old_contexts == 0:
            click.echo("✅ No old data found to clean up.")
            session.close()
            return
        
        click.echo(f"Found {old_events} old events and {old_contexts} old contexts to delete.")
        
        if click.confirm("Proceed with deletion?"):
            # Delete old records (cascade will handle related records)
            session.query(RawEvent).filter(RawEvent.timestamp < cutoff).delete()
            session.query(FusedContext).filter(FusedContext.created_at < cutoff).delete()
            
            session.commit()
            click.echo(f"✅ Deleted {old_events} events and {old_contexts} contexts.")
        else:
            click.echo("Cleanup cancelled.")
        
        session.close()
        
    except Exception as e:
        click.echo(f"❌ Error during cleanup: {e}")
        sys.exit(1)

# Pipeline commands
@pipeline.command()
def run():
    """Run a single pipeline cycle"""
    click.echo("🔄 Running pipeline cycle...")
    
    try:
        # Step 1: Enrichment
        enrichment = EnrichmentLayer()
        enriched_ids = enrichment.process_raw_events(limit=100)
        click.echo(f"✅ Enrichment: Processed {len(enriched_ids)} events")
        
        # Step 2: Fusion
        fusion = FusionLayer()
        incident_ids = fusion.create_incident_contexts(lookback_hours=1)
        click.echo(f"✅ Fusion: Created {len(incident_ids)} incident contexts")
        
        # Step 3: RCA
        rca_engine = RCAEngine()
        analyzed_ids = rca_engine.analyze_incidents(lookback_hours=1)
        click.echo(f"✅ RCA: Analyzed {len(analyzed_ids)} incidents")
        
        # Step 4: Agentic
        agentic_ai = AgenticAI()
        agentic_ids = agentic_ai.analyze_low_confidence_incidents()
        click.echo(f"✅ Agentic: Processed {len(agentic_ids)} low-confidence incidents")
        
        click.echo("🎉 Pipeline cycle completed successfully!")
        
    except Exception as e:
        click.echo(f"❌ Error running pipeline: {e}")
        sys.exit(1)

@pipeline.command()
def enrichment():
    """Run enrichment step only"""
    click.echo("🔄 Running enrichment step...")
    
    try:
        enrichment = EnrichmentLayer()
        enriched_ids = enrichment.process_raw_events(limit=100)
        click.echo(f"✅ Processed {len(enriched_ids)} events")
    except Exception as e:
        click.echo(f"❌ Error in enrichment: {e}")
        sys.exit(1)

@pipeline.command()
def fusion():
    """Run fusion step only"""
    click.echo("🔄 Running fusion step...")
    
    try:
        fusion = FusionLayer()
        incident_ids = fusion.create_incident_contexts(lookback_hours=2)
        click.echo(f"✅ Created {len(incident_ids)} incident contexts")
    except Exception as e:
        click.echo(f"❌ Error in fusion: {e}")
        sys.exit(1)

@pipeline.command()
def rca():
    """Run RCA analysis step only"""
    click.echo("🔄 Running RCA analysis...")
    
    try:
        rca_engine = RCAEngine()
        analyzed_ids = rca_engine.analyze_incidents(lookback_hours=2)
        click.echo(f"✅ Analyzed {len(analyzed_ids)} incidents")
    except Exception as e:
        click.echo(f"❌ Error in RCA: {e}")
        sys.exit(1)

@pipeline.command()
def agentic():
    """Run agentic analysis step only"""
    click.echo("🔄 Running agentic analysis...")
    
    try:
        agentic_ai = AgenticAI()
        agentic_ids = agentic_ai.analyze_low_confidence_incidents()
        click.echo(f"✅ Processed {len(agentic_ids)} low-confidence incidents")
    except Exception as e:
        click.echo(f"❌ Error in agentic analysis: {e}")
        sys.exit(1)

# Configuration commands
@cli.group()
def config():
    """Configuration management"""
    pass

@config.command()
def show():
    """Show current configuration"""
    try:
        with open("config/config.yaml", 'r') as file:
            config = yaml.safe_load(file)
        
        click.echo("📋 Current Configuration:")
        click.echo("=" * 40)
        click.echo(yaml.dump(config, default_flow_style=False))
        
    except Exception as e:
        click.echo(f"❌ Error reading configuration: {e}")
        sys.exit(1)

@config.command()
@click.argument('key')
@click.argument('value')
def set(key, value):
    """Set a configuration value (e.g., rca.confidence_threshold 90)"""
    try:
        with open("config/config.yaml", 'r') as file:
            config = yaml.safe_load(file)
        
        # Parse nested key (e.g., "rca.confidence_threshold")
        keys = key.split('.')
        current = config
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        # Try to convert value to appropriate type
        try:
            if value.lower() in ['true', 'false']:
                value = value.lower() == 'true'
            elif '.' in value:
                value = float(value)
            else:
                value = int(value)
        except ValueError:
            pass  # Keep as string
        
        current[keys[-1]] = value
        
        # Write back to file
        with open("config/config.yaml", 'w') as file:
            yaml.dump(config, file, default_flow_style=False)
        
        click.echo(f"✅ Set {key} = {value}")
        
    except Exception as e:
        click.echo(f"❌ Error setting configuration: {e}")
        sys.exit(1)

if __name__ == "__main__":
    cli()
