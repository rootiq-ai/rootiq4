import os
import logging
import structlog
from typing import Dict, Any, Optional
import yaml
from datetime import datetime

def setup_logging(config_path: str = "config/config.yaml") -> None:
    """
    Setup structured logging based on configuration
    """
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        
        log_config = config.get('logging', {})
        log_level = log_config.get('level', 'INFO')
        log_format = log_config.get('format', 'json')
        
        # Configure structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer() if log_format == 'json' else structlog.dev.ConsoleRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        # Set log level
        logging.basicConfig(level=getattr(logging, log_level.upper()))
        
    except Exception as e:
        print(f"Error setting up logging: {e}")
        # Fallback to basic configuration
        logging.basicConfig(level=logging.INFO)

def load_config(config_path: str = "config/config.yaml") -> Dict[str, Any]:
    """
    Load configuration from YAML file
    """
    try:
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)
    except Exception as e:
        raise RuntimeError(f"Failed to load configuration from {config_path}: {e}")

def check_environment() -> Dict[str, bool]:
    """
    Check if required environment variables and dependencies are available
    """
    checks = {}
    
    # Check environment variables
    required_env_vars = ["OPENAI_API_KEY"]
    for var in required_env_vars:
        checks[f"env_{var}"] = os.getenv(var) is not None
    
    # Check database connectivity
    try:
        from database.connection import db_manager
        session = db_manager.get_session()
        session.execute("SELECT 1")
        session.close()
        checks["database_connection"] = True
    except Exception:
        checks["database_connection"] = False
    
    # Check ChromaDB
    try:
        from rca.vector_store import VectorStore
        vector_store = VectorStore()
        vector_store.get_collection_stats()
        checks["vector_store"] = True
    except Exception:
        checks["vector_store"] = False
    
    return checks

def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"

def calculate_health_score(metrics: Dict[str, Any]) -> float:
    """
    Calculate overall system health score based on various metrics
    """
    score = 1.0
    
    # Check database metrics
    if "database_errors" in metrics:
        error_rate = metrics["database_errors"] / max(metrics.get("database_queries", 1), 1)
        score -= error_rate * 0.3
    
    # Check processing times
    if "avg_processing_time" in metrics:
        # Penalize if processing time > 5 seconds
        if metrics["avg_processing_time"] > 5:
            score -= 0.2
    
    # Check confidence scores
    if "avg_confidence" in metrics:
        if metrics["avg_confidence"] < 0.7:
            score -= 0.3
    
    # Check system availability
    if "uptime_percentage" in metrics:
        score *= metrics["uptime_percentage"]
    
    return max(0.0, min(1.0, score))

def validate_incident_context(context: Dict[str, Any]) -> bool:
    """
    Validate incident context structure
    """
    required_fields = ["temporal_context", "semantic_context", "causal_context"]
    
    for field in required_fields:
        if field not in context:
            return False
    
    # Validate temporal context
    temporal = context.get("temporal_context", {})
    if not isinstance(temporal, dict):
        return False
    
    # Validate semantic context
    semantic = context.get("semantic_context", {})
    if not isinstance(semantic, dict):
        return False
    
    # Validate causal context
    causal = context.get("causal_context", {})
    if not isinstance(causal, dict):
        return False
    
    return True

def generate_incident_id() -> str:
    """
    Generate a unique incident ID
    """
    import uuid
    return str(uuid.uuid4())

def sanitize_log_message(message: str, max_length: int = 500) -> str:
    """
    Sanitize log message for safe storage and display
    """
    if not message:
        return ""
    
    # Remove potentially sensitive information
    sensitive_patterns = [
        r'password[=:][\w\s]*',
        r'token[=:][\w\s]*',
        r'key[=:][\w\s]*',
        r'secret[=:][\w\s]*'
    ]
    
    import re
    sanitized = message
    for pattern in sensitive_patterns:
        sanitized = re.sub(pattern, '[REDACTED]', sanitized, flags=re.IGNORECASE)
    
    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "..."
    
    return sanitized

def retry_operation(func, max_retries: int = 3, delay: float = 1.0):
    """
    Retry an operation with exponential backoff
    """
    import time
    
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            
            wait_time = delay * (2 ** attempt)
            time.sleep(wait_time)

def create_summary_stats(data_list: list, field: str) -> Dict[str, Any]:
    """
    Create summary statistics for a numeric field in a list of dictionaries
    """
    import statistics
    
    values = [item.get(field, 0) for item in data_list if field in item and isinstance(item[field], (int, float))]
    
    if not values:
        return {"count": 0}
    
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "std_dev": statistics.stdev(values) if len(values) > 1 else 0
    }

def format_confidence_score(score: float) -> str:
    """
    Format confidence score with appropriate emoji and color coding
    """
    if score >= 0.9:
        return f"🟢 {score:.2f} (Very High)"
    elif score >= 0.8:
        return f"🟡 {score:.2f} (High)"
    elif score >= 0.6:
        return f"🟠 {score:.2f} (Medium)"
    elif score >= 0.4:
        return f"🔴 {score:.2f} (Low)"
    else:
        return f"⚫ {score:.2f} (Very Low)"

def export_incident_report(incident_data: Dict[str, Any], format: str = "json") -> str:
    """
    Export incident data to various formats
    """
    if format == "json":
        import json
        return json.dumps(incident_data, indent=2, default=str)
    
    elif format == "yaml":
        import yaml
        return yaml.dump(incident_data, default_flow_style=False)
    
    elif format == "text":
        lines = [
            f"Incident Report - {datetime.now().isoformat()}",
            "=" * 50,
            f"Incident ID: {incident_data.get('incident_id', 'N/A')}",
            f"Root Cause: {incident_data.get('root_cause', 'N/A')}",
            f"Confidence: {incident_data.get('confidence_score', 0):.2f}",
            f"Suggested Fix: {incident_data.get('suggested_fix', 'N/A')}",
            "",
            "Detailed Analysis:",
            incident_data.get('llm_reasoning', 'N/A')
        ]
        return "\n".join(lines)
    
    else:
        raise ValueError(f"Unsupported export format: {format}")

class SystemMonitor:
    """
    Simple system monitoring utility
    """
    
    def __init__(self):
        self.start_time = datetime.now()
        self.metrics = {}
    
    def record_metric(self, name: str, value: Any):
        """Record a metric value"""
        self.metrics[name] = {
            "value": value,
            "timestamp": datetime.now()
        }
    
    def get_uptime(self) -> float:
        """Get system uptime in seconds"""
        return (datetime.now() - self.start_time).total_seconds()
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of all recorded metrics"""
        return {
            "uptime_seconds": self.get_uptime(),
            "metrics_count": len(self.metrics),
            "last_metric_time": max([m["timestamp"] for m in self.metrics.values()]) if self.metrics else None,
            "metrics": self.metrics
        }

# Global system monitor instance
system_monitor = SystemMonitor()
