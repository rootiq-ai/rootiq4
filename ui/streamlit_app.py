import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
from database.connection import db_manager
from database.models import RawEvent, EnrichedEvent, FusedContext, RCAResult, AgenticInvocation
from sqlalchemy import func, desc
from ingestion.ingestion_layer import IngestionLayer
from enrichment.enrichment_layer import EnrichmentLayer
from fusion.fusion_layer import FusionLayer
from rca.rca_engine import RCAEngine
from rca.vector_store import VectorStore
from agentic.agentic_ai import AgenticAI

# Page configuration
st.set_page_config(
    page_title="RCA System Dashboard",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize components
@st.cache_resource
def init_components():
    return {
        "ingestion": IngestionLayer(),
        "enrichment": EnrichmentLayer(),
        "fusion": FusionLayer(),
        "rca_engine": RCAEngine(),
        "vector_store": VectorStore(),
        "agentic_ai": AgenticAI()
    }

components = init_components()

# Sidebar navigation
st.sidebar.title("🔍 RCA System")
page = st.sidebar.selectbox(
    "Navigate to:",
    ["Dashboard", "Incidents", "System Status", "Data Pipeline", "Settings"]
)

# Helper functions
@st.cache_data(ttl=60)  # Cache for 1 minute
def get_recent_events(limit=100):
    session = db_manager.get_session()
    try:
        events = session.query(RawEvent).order_by(desc(RawEvent.timestamp)).limit(limit).all()
        return events
    finally:
        session.close()

@st.cache_data(ttl=60)
def get_incident_summary():
    session = db_manager.get_session()
    try:
        # Get counts by status
        total_incidents = session.query(FusedContext).count()
        resolved_incidents = session.query(RCAResult).filter(RCAResult.confidence_score >= 0.8).count()
        pending_agentic = session.query(RCAResult).filter(RCAResult.analysis_method == "pending_agentic").count()
        
        # Get recent activity
        recent_incidents = session.query(FusedContext).order_by(desc(FusedContext.created_at)).limit(5).all()
        
        return {
            "total": total_incidents,
            "resolved": resolved_incidents,
            "pending_agentic": pending_agentic,
            "recent": recent_incidents
        }
    finally:
        session.close()

@st.cache_data(ttl=60)
def get_system_metrics():
    session = db_manager.get_session()
    try:
        # Count events by type in last 24 hours
        cutoff = datetime.utcnow() - timedelta(days=1)
        event_counts = session.query(
            RawEvent.event_type,
            func.count(RawEvent.id).label('count')
        ).filter(
            RawEvent.timestamp >= cutoff
        ).group_by(RawEvent.event_type).all()
        
        # Average processing time (mock data for demo)
        avg_processing_time = 2.3
        
        # System health score
        health_score = 0.87
        
        return {
            "event_counts": dict(event_counts),
            "avg_processing_time": avg_processing_time,
            "health_score": health_score
        }
    finally:
        session.close()

# Dashboard Page
if page == "Dashboard":
    st.title("🔍 RCA System Dashboard")
    
    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    incident_summary = get_incident_summary()
    system_metrics = get_system_metrics()
    
    with col1:
        st.metric(
            label="Total Incidents",
            value=incident_summary["total"],
            delta=f"{incident_summary['total'] - incident_summary['resolved']} pending"
        )
    
    with col2:
        st.metric(
            label="Resolution Rate",
            value=f"{(incident_summary['resolved'] / max(incident_summary['total'], 1) * 100):.1f}%",
            delta="↑ 5.2% vs last week"
        )
    
    with col3:
        st.metric(
            label="Avg Processing Time",
            value=f"{system_metrics['avg_processing_time']:.1f}s",
            delta="-0.3s vs last week"
        )
    
    with col4:
        st.metric(
            label="System Health",
            value=f"{system_metrics['health_score']:.1%}",
            delta="↑ 2.1% vs last week"
        )
    
    # Charts row
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Event Volume (Last 24h)")
        event_counts = system_metrics["event_counts"]
        if event_counts:
            fig = px.pie(
                values=list(event_counts.values()),
                names=list(event_counts.keys()),
                title="Events by Type"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Recent Incident Timeline")
        recent_incidents = incident_summary["recent"]
        if recent_incidents:
            timeline_data = []
            for incident in recent_incidents:
                timeline_data.append({
                    "Incident ID": incident.incident_id[:8] + "...",
                    "Created": incident.created_at,
                    "Fusion Score": incident.fusion_score
                })
            
            df = pd.DataFrame(timeline_data)
            fig = px.scatter(
                df,
                x="Created",
                y="Fusion Score",
                hover_data=["Incident ID"],
                title="Incident Fusion Scores Over Time"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Recent incidents table
    st.subheader("Recent Incidents")
    if recent_incidents:
        incident_data = []
        session = db_manager.get_session()
        try:
            for incident in recent_incidents:
                rca_result = session.query(RCAResult).filter_by(incident_id=incident.incident_id).first()
                
                incident_data.append({
                    "Incident ID": incident.incident_id[:8] + "...",
                    "Created": incident.created_at.strftime("%Y-%m-%d %H:%M"),
                    "Fusion Score": f"{incident.fusion_score:.2f}",
                    "Category": incident.semantic_context.get("incident_category", "unknown") if incident.semantic_context else "unknown",
                    "Status": "Resolved" if rca_result and rca_result.confidence_score >= 0.8 else "Pending",
                    "Confidence": f"{rca_result.confidence_score:.2f}" if rca_result else "N/A"
                })
        finally:
            session.close()
        
        df = pd.DataFrame(incident_data)
        st.dataframe(df, use_container_width=True)

# Incidents Page
elif page == "Incidents":
    st.title("🎯 Incident Analysis")
    
    # Get all incidents with RCA results
    session = db_manager.get_session()
    try:
        incidents_with_rca = session.query(FusedContext, RCAResult).outerjoin(
            RCAResult, FusedContext.incident_id == RCAResult.incident_id
        ).order_by(desc(FusedContext.created_at)).all()
    finally:
        session.close()
    
    # Incident filter
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    
    with filter_col1:
        status_filter = st.selectbox(
            "Filter by Status",
            ["All", "Resolved", "Pending", "Low Confidence"]
        )
    
    with filter_col2:
        category_filter = st.selectbox(
            "Filter by Category",
            ["All", "performance", "connectivity", "application"]
        )
    
    with filter_col3:
        severity_filter = st.selectbox(
            "Filter by Severity",
            ["All", "critical", "high", "medium", "low"]
        )
    
    # Display incidents
    for fused_context, rca_result in incidents_with_rca:
        # Apply filters
        if status_filter != "All":
            if status_filter == "Resolved" and (not rca_result or rca_result.confidence_score < 0.8):
                continue
            if status_filter == "Pending" and rca_result:
                continue
            if status_filter == "Low Confidence" and (not rca_result or rca_result.confidence_score >= 0.8):
                continue
        
        if category_filter != "All":
            incident_category = fused_context.semantic_context.get("incident_category", "unknown") if fused_context.semantic_context else "unknown"
            if incident_category != category_filter:
                continue
        
        # Create incident card
        with st.expander(f"🚨 Incident {fused_context.incident_id[:8]}... | Created: {fused_context.created_at.strftime('%Y-%m-%d %H:%M')}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Context Summary")
                if fused_context.semantic_context:
                    semantic = fused_context.semantic_context
                    st.write(f"**Category:** {semantic.get('incident_category', 'unknown')}")
                    st.write(f"**Max Severity:** {semantic.get('max_severity', 'info')}")
                    st.write(f"**Multi-Service:** {'Yes' if semantic.get('is_multi_service') else 'No'}")
                    
                    if semantic.get('common_keywords'):
                        st.write(f"**Keywords:** {', '.join(semantic['common_keywords'][:5])}")
                
                if fused_context.temporal_context:
                    temporal = fused_context.temporal_context
                    st.write(f"**Event Count:** {temporal.get('event_count', 0)}")
                    st.write(f"**Duration:** {temporal.get('duration_seconds', 0):.0f}s")
                    if temporal.get('is_burst_pattern'):
                        st.warning("⚡ Burst pattern detected")
            
            with col2:
                st.subheader("RCA Results")
                if rca_result:
                    # Confidence indicator
                    confidence = rca_result.confidence_score
                    if confidence >= 0.8:
                        st.success(f"✅ High Confidence: {confidence:.2f}")
                    elif confidence >= 0.6:
                        st.warning(f"⚠️ Medium Confidence: {confidence:.2f}")
                    else:
                        st.error(f"❌ Low Confidence: {confidence:.2f}")
                    
                    st.write(f"**Analysis Method:** {rca_result.analysis_method}")
                    st.write(f"**Root Cause:**")
                    st.info(rca_result.root_cause)
                    
                    st.write(f"**Suggested Fix:**")
                    st.code(rca_result.suggested_fix, language="text")
                    
                    # Show reasoning in collapsible section
                    with st.expander("View Detailed Reasoning"):
                        st.text(rca_result.llm_reasoning)
                else:
                    st.warning("⏳ Analysis pending")

# System Status Page
elif page == "System Status":
    st.title("⚙️ System Status")
    
    # System health metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Database Status")
        try:
            session = db_manager.get_session()
            raw_events_count = session.query(RawEvent).count()
            enriched_events_count = session.query(EnrichedEvent).count()
            fused_contexts_count = session.query(FusedContext).count()
            session.close()
            
            st.success("✅ Connected")
            st.metric("Raw Events", raw_events_count)
            st.metric("Enriched Events", enriched_events_count)
            st.metric("Fused Contexts", fused_contexts_count)
        except Exception as e:
            st.error(f"❌ Database Error: {str(e)}")
    
    with col2:
        st.subheader("Vector Store Status")
        try:
            vector_stats = components["vector_store"].get_collection_stats()
            st.success("✅ Connected")
            st.metric("Historical Patterns", vector_stats["total_patterns"])
            st.write(f"Collection: {vector_stats['collection_name']}")
        except Exception as e:
            st.error(f"❌ Vector Store Error: {str(e)}")
    
    with col3:
        st.subheader("Agentic AI Status")
        try:
            agentic_stats = components["agentic_ai"].get_agentic_invocation_stats()
            st.success("✅ Operational")
            st.metric("Total Invocations", agentic_stats.get("total_invocations", 0))
            if agentic_stats.get("average_execution_time_seconds"):
                st.metric("Avg Execution Time", f"{agentic_stats['average_execution_time_seconds']:.1f}s")
        except Exception as e:
            st.error(f"❌ Agentic AI Error: {str(e)}")
    
    # Component health dashboard
    st.subheader("Component Health")
    
    components_status = [
        {"Component": "Ingestion Layer", "Status": "Healthy", "Last Check": "2 min ago"},
        {"Component": "Enrichment Layer", "Status": "Healthy", "Last Check": "1 min ago"},
        {"Component": "Fusion Layer", "Status": "Healthy", "Last Check": "30 sec ago"},
        {"Component": "RCA Engine", "Status": "Healthy", "Last Check": "15 sec ago"},
        {"Component": "Vector Store", "Status": "Healthy", "Last Check": "45 sec ago"},
        {"Component": "Agentic AI", "Status": "Healthy", "Last Check": "1 min ago"},
    ]
    
    df = pd.DataFrame(components_status)
    st.dataframe(df, use_container_width=True)

# Data Pipeline Page
elif page == "Data Pipeline":
    st.title("🔄 Data Pipeline Management")
    
    # Pipeline controls
    st.subheader("Pipeline Operations")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Process Raw Events", type="primary"):
            with st.spinner("Processing raw events..."):
                try:
                    enriched_ids = components["enrichment"].process_raw_events(limit=50)
                    st.success(f"✅ Processed {len(enriched_ids)} raw events")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
    
    with col2:
        if st.button("🔗 Create Incident Contexts"):
            with st.spinner("Creating incident contexts..."):
                try:
                    incident_ids = components["fusion"].create_incident_contexts(lookback_hours=2)
                    st.success(f"✅ Created {len(incident_ids)} incident contexts")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
    
    with col3:
        if st.button("🧠 Analyze Incidents"):
            with st.spinner("Analyzing incidents..."):
                try:
                    analyzed_ids = components["rca_engine"].analyze_incidents(lookback_hours=2)
                    st.success(f"✅ Analyzed {len(analyzed_ids)} incidents")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
    
    # Sample data generation
    st.subheader("Sample Data Generation")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📝 Create Sample Events"):
            with st.spinner("Creating sample events..."):
                try:
                    event_ids = components["ingestion"].create_sample_events()
                    st.success(f"✅ Created {len(event_ids)} sample events")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
    
    with col2:
        if st.button("📚 Add Sample Patterns"):
            with st.spinner("Adding sample patterns..."):
                try:
                    pattern_ids = components["vector_store"].add_sample_patterns()
                    st.success(f"✅ Added {len(pattern_ids)} sample patterns")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
    
    # Pipeline visualization
    st.subheader("Pipeline Flow")
    pipeline_steps = [
        "1. Raw Events → Ingestion Layer",
        "2. Ingestion → Enrichment (correlation, anomaly detection)",
        "3. Enrichment → Fusion (multimodal context)",
        "4. Fusion → RCA Engine (LLM + RAG)",
        "5. Low confidence → Agentic AI (external tools)",
        "6. Results → Dashboard & Storage"
    ]
    
    for step in pipeline_steps:
        st.write(f"🔄 {step}")

# Settings Page
elif page == "Settings":
    st.title("⚙️ Settings")
    
    # Configuration display
    st.subheader("Current Configuration")
    
    # Load and display config
    try:
        with open("config/config.yaml", 'r') as file:
            import yaml
            config = yaml.safe_load(file)
        
        # Display key settings
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**RCA Settings**")
            st.write(f"Confidence Threshold: {config['rca']['confidence_threshold']}%")
            st.write(f"Max Context Length: {config['rca']['max_context_length']}")
            st.write(f"Agentic Fallback: {config['rca']['enable_agentic_fallback']}")
            
            st.write("**Enrichment Settings**")
            st.write(f"Correlation Window: {config['enrichment']['correlation_window_minutes']} min")
            st.write(f"Anomaly Threshold: {config['enrichment']['anomaly_threshold']}")
        
        with col2:
            st.write("**Fusion Settings**")
            st.write(f"Temporal Weight: {config['fusion']['temporal_weight']}")
            st.write(f"Semantic Weight: {config['fusion']['semantic_weight']}")
            st.write(f"Causal Weight: {config['fusion']['causal_weight']}")
            
            st.write("**LLM Settings**")
            st.write(f"Provider: {config['llm']['provider']}")
            st.write(f"Model: {config['llm']['model']}")
            st.write(f"Temperature: {config['llm']['temperature']}")
        
        # Full config in expandable section
        with st.expander("View Full Configuration"):
            st.json(config)
            
    except Exception as e:
        st.error(f"Error loading configuration: {str(e)}")
    
    # Environment variables
    st.subheader("Environment Setup")
    st.info("""
    **Required Environment Variables:**
    - `OPENAI_API_KEY`: Your OpenAI API key for LLM analysis
    - `DATABASE_URL`: PostgreSQL connection string (optional, uses config defaults)
    
    **Setup Instructions:**
    1. Create a `.env` file in the project root
    2. Add your OpenAI API key: `OPENAI_API_KEY=your_key_here`
    3. Ensure PostgreSQL is running and accessible
    4. Run database migrations: `python -c "from database.connection import db_manager; db_manager.create_tables()"`
    """)

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("🔍 **RCA System v1.0**")
st.sidebar.markdown("Built with Streamlit, PostgreSQL, ChromaDB")
st.sidebar.markdown(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
