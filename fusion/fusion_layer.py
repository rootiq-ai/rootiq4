import structlog
import yaml
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
from database.connection import db_manager
from database.models import EnrichedEvent, FusedContext, RawEvent
import numpy as np

logger = structlog.get_logger(__name__)

class FusionLayer:
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)
        
        self.db_manager = db_manager
        self.temporal_weight = self.config['fusion']['temporal_weight']
        self.semantic_weight = self.config['fusion']['semantic_weight']
        self.causal_weight = self.config['fusion']['causal_weight']
    
    def create_incident_contexts(self, lookback_hours: int = 1) -> List[str]:
        """
        Create fused contexts for incidents based on correlated enriched events
        Returns list of incident IDs
        """
        session = self.db_manager.get_session()
        try:
            # Get recent enriched events that don't have fusion context yet
            cutoff_time = datetime.utcnow() - timedelta(hours=lookback_hours)
            
            unfused_events = session.query(EnrichedEvent).join(RawEvent).filter(
                and_(
                    RawEvent.timestamp >= cutoff_time,
                    ~EnrichedEvent.correlation_id.in_(
                        session.query(FusedContext.incident_id)
                    )
                )
            ).all()
            
            # Group events by correlation ID
            correlation_groups = {}
            for event in unfused_events:
                if event.correlation_id not in correlation_groups:
                    correlation_groups[event.correlation_id] = []
                correlation_groups[event.correlation_id].append(event)
            
            incident_ids = []
            for correlation_id, events in correlation_groups.items():
                if len(events) >= 1:  # Create incident for any correlated events
                    incident_id = self._create_fused_context(session, correlation_id, events)
                    if incident_id:
                        incident_ids.append(incident_id)
            
            session.commit()
            logger.info(f"Created {len(incident_ids)} incident contexts")
            return incident_ids
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating incident contexts: {e}")
            raise
        finally:
            session.close()
    
    def _create_fused_context(self, session: Session, correlation_id: str, events: List[EnrichedEvent]) -> Optional[str]:
        """
        Create a fused context from correlated enriched events
        """
        try:
            # Generate temporal context
            temporal_context = self._generate_temporal_context(events)
            
            # Generate semantic context
            semantic_context = self._generate_semantic_context(events)
            
            # Generate causal context
            causal_context = self._generate_causal_context(events)
            
            # Calculate fusion score
            fusion_score = self._calculate_fusion_score(temporal_context, semantic_context, causal_context)
            
            # Create fused context record
            fused_context = FusedContext(
                incident_id=correlation_id,
                temporal_context=temporal_context,
                semantic_context=semantic_context,
                causal_context=causal_context,
                fusion_score=fusion_score
            )
            
            session.add(fused_context)
            
            logger.info(f"Created fused context for incident {correlation_id}", 
                       fusion_score=fusion_score, event_count=len(events))
            
            return correlation_id
            
        except Exception as e:
            logger.error(f"Error creating fused context for {correlation_id}: {e}")
            return None
    
    def _generate_temporal_context(self, events: List[EnrichedEvent]) -> Dict[str, Any]:
        """
        Generate temporal context analysis
        """
        if not events:
            return {}
        
        # Get timestamps from raw events
        timestamps = []
        for event in events:
            if event.raw_event:
                timestamps.append(event.raw_event.timestamp)
        
        if not timestamps:
            return {}
        
        timestamps.sort()
        start_time = timestamps[0]
        end_time = timestamps[-1]
        duration = (end_time - start_time).total_seconds()
        
        # Calculate event rate
        event_intervals = []
        for i in range(1, len(timestamps)):
            interval = (timestamps[i] - timestamps[i-1]).total_seconds()
            event_intervals.append(interval)
        
        avg_interval = np.mean(event_intervals) if event_intervals else 0
        
        # Analyze temporal patterns
        hourly_distribution = {}
        for ts in timestamps:
            hour = ts.hour
            hourly_distribution[hour] = hourly_distribution.get(hour, 0) + 1
        
        return {
            "event_count": len(events),
            "duration_seconds": duration,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "average_interval_seconds": avg_interval,
            "hourly_distribution": hourly_distribution,
            "is_burst_pattern": avg_interval < 60 and len(events) > 3,  # Events within 1 minute
            "temporal_intensity": len(events) / max(duration / 60, 1)  # Events per minute
        }
    
    def _generate_semantic_context(self, events: List[EnrichedEvent]) -> Dict[str, Any]:
        """
        Generate semantic context analysis
        """
        if not events:
            return {}
        
        # Analyze event types and sources
        event_types = {}
        sources = {}
        severities = {}
        messages = []
        
        for event in events:
            if event.raw_event:
                raw = event.raw_event
                
                # Count event types
                event_types[raw.event_type] = event_types.get(raw.event_type, 0) + 1
                
                # Count sources
                sources[raw.source] = sources.get(raw.source, 0) + 1
                
                # Count severities
                if raw.severity:
                    severities[raw.severity] = severities.get(raw.severity, 0) + 1
                
                # Collect messages
                if raw.message:
                    messages.append(raw.message)
        
        # Extract common keywords from messages
        common_keywords = self._extract_common_keywords(messages)
        
        # Calculate diversity metrics
        type_diversity = len(event_types)
        source_diversity = len(sources)
        
        # Determine incident category
        incident_category = self._categorize_incident(event_types, severities, common_keywords)
        
        return {
            "event_types": event_types,
            "sources": sources,
            "severities": severities,
            "common_keywords": common_keywords,
            "type_diversity": type_diversity,
            "source_diversity": source_diversity,
            "incident_category": incident_category,
            "is_multi_service": source_diversity > 1,
            "max_severity": self._get_max_severity(severities)
        }
    
    def _generate_causal_context(self, events: List[EnrichedEvent]) -> Dict[str, Any]:
        """
        Generate causal relationship analysis
        """
        if not events:
            return {}
        
        # Sort events by timestamp
        events_with_time = [(event, event.raw_event.timestamp) for event in events if event.raw_event]
        events_with_time.sort(key=lambda x: x[1])
        
        # Analyze causal chains
        causal_chains = self._identify_causal_chains(events_with_time)
        
        # Calculate anomaly patterns
        anomaly_progression = self._analyze_anomaly_progression(events)
        
        # Identify potential root causes
        potential_root_causes = self._identify_potential_root_causes(events_with_time)
        
        # Calculate causal strength
        causal_strength = self._calculate_causal_strength(causal_chains, anomaly_progression)
        
        return {
            "causal_chains": causal_chains,
            "anomaly_progression": anomaly_progression,
            "potential_root_causes": potential_root_causes,
            "causal_strength": causal_strength,
            "has_clear_progression": len(causal_chains) > 0,
            "root_cause_confidence": self._calculate_root_cause_confidence(potential_root_causes)
        }
    
    def _extract_common_keywords(self, messages: List[str], min_frequency: int = 2) -> List[str]:
        """
        Extract common keywords from messages
        """
        if not messages:
            return []
        
        # Simple keyword extraction
        word_counts = {}
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        
        for message in messages:
            words = message.lower().split()
            for word in words:
                # Remove punctuation and filter stop words
                word = ''.join(c for c in word if c.isalnum())
                if word and word not in stop_words and len(word) > 2:
                    word_counts[word] = word_counts.get(word, 0) + 1
        
        # Return words that appear at least min_frequency times
        common_words = [word for word, count in word_counts.items() if count >= min_frequency]
        return sorted(common_words, key=lambda x: word_counts[x], reverse=True)[:10]
    
    def _categorize_incident(self, event_types: Dict, severities: Dict, keywords: List[str]) -> str:
        """
        Categorize the incident based on patterns
        """
        # Performance-related keywords
        performance_keywords = ["timeout", "slow", "latency", "response", "cpu", "memory", "disk"]
        
        # Connectivity-related keywords
        connectivity_keywords = ["connection", "network", "dns", "unreachable", "refused"]
        
        # Application-related keywords
        application_keywords = ["error", "exception", "failed", "crash", "restart"]
        
        # Check keyword matches
        perf_score = sum(1 for k in keywords if any(pk in k for pk in performance_keywords))
        conn_score = sum(1 for k in keywords if any(ck in k for ck in connectivity_keywords))
        app_score = sum(1 for k in keywords if any(ak in k for ak in application_keywords))
        
        # Determine category
        if perf_score >= conn_score and perf_score >= app_score:
            return "performance"
        elif conn_score >= app_score:
            return "connectivity"
        else:
            return "application"
    
    def _get_max_severity(self, severities: Dict) -> str:
        """
        Get the maximum severity level
        """
        severity_order = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}
        max_severity = "info"
        max_level = 0
        
        for severity in severities:
            level = severity_order.get(severity, 0)
            if level > max_level:
                max_level = level
                max_severity = severity
        
        return max_severity
    
    def _identify_causal_chains(self, events_with_time: List[tuple]) -> List[Dict]:
        """
        Identify potential causal chains in events
        """
        chains = []
        
        for i in range(len(events_with_time) - 1):
            current_event, current_time = events_with_time[i]
            next_event, next_time = events_with_time[i + 1]
            
            time_diff = (next_time - current_time).total_seconds()
            
            # If events are close in time (within 5 minutes), they might be causally related
            if time_diff <= 300:
                chain = {
                    "source_event": {
                        "source": current_event.raw_event.source,
                        "message": current_event.raw_event.message,
                        "severity": current_event.raw_event.severity
                    },
                    "target_event": {
                        "source": next_event.raw_event.source,
                        "message": next_event.raw_event.message,
                        "severity": next_event.raw_event.severity
                    },
                    "time_diff_seconds": time_diff,
                    "causal_likelihood": max(0, 1 - (time_diff / 300))  # Higher likelihood for closer events
                }
                chains.append(chain)
        
        return chains
    
    def _analyze_anomaly_progression(self, events: List[EnrichedEvent]) -> Dict[str, Any]:
        """
        Analyze how anomaly scores progress over time
        """
        if not events:
            return {}
        
        anomaly_scores = [event.anomaly_score for event in events if event.anomaly_score is not None]
        
        if not anomaly_scores:
            return {}
        
        return {
            "average_anomaly_score": np.mean(anomaly_scores),
            "max_anomaly_score": max(anomaly_scores),
            "min_anomaly_score": min(anomaly_scores),
            "anomaly_trend": "increasing" if len(anomaly_scores) > 1 and anomaly_scores[-1] > anomaly_scores[0] else "stable",
            "high_anomaly_count": sum(1 for score in anomaly_scores if score > 0.7)
        }
    
    def _identify_potential_root_causes(self, events_with_time: List[tuple]) -> List[Dict]:
        """
        Identify potential root cause events
        """
        if not events_with_time:
            return []
        
        root_causes = []
        
        # First event in timeline could be root cause
        first_event, first_time = events_with_time[0]
        if first_event.anomaly_score and first_event.anomaly_score > 0.5:
            root_causes.append({
                "event_source": first_event.raw_event.source,
                "event_message": first_event.raw_event.message,
                "timestamp": first_time.isoformat(),
                "confidence": first_event.anomaly_score,
                "reason": "first_anomalous_event"
            })
        
        # Events with highest anomaly scores
        for event, timestamp in events_with_time:
            if event.anomaly_score and event.anomaly_score > 0.8:
                root_causes.append({
                    "event_source": event.raw_event.source,
                    "event_message": event.raw_event.message,
                    "timestamp": timestamp.isoformat(),
                    "confidence": event.anomaly_score,
                    "reason": "high_anomaly_score"
                })
        
        # Remove duplicates and sort by confidence
        unique_causes = []
        seen = set()
        for cause in root_causes:
            key = (cause["event_source"], cause["event_message"])
            if key not in seen:
                seen.add(key)
                unique_causes.append(cause)
        
        return sorted(unique_causes, key=lambda x: x["confidence"], reverse=True)[:3]
    
    def _calculate_causal_strength(self, causal_chains: List[Dict], anomaly_progression: Dict) -> float:
        """
        Calculate overall causal relationship strength
        """
        if not causal_chains:
            return 0.0
        
        # Average causal likelihood from chains
        avg_likelihood = np.mean([chain["causal_likelihood"] for chain in causal_chains])
        
        # Boost if anomaly progression shows increasing trend
        trend_boost = 0.2 if anomaly_progression.get("anomaly_trend") == "increasing" else 0.0
        
        return min(1.0, avg_likelihood + trend_boost)
    
    def _calculate_root_cause_confidence(self, potential_root_causes: List[Dict]) -> float:
        """
        Calculate confidence in root cause identification
        """
        if not potential_root_causes:
            return 0.0
        
        # Use highest confidence from potential root causes
        return max(cause["confidence"] for cause in potential_root_causes)
    
    def _calculate_fusion_score(self, temporal_context: Dict, semantic_context: Dict, causal_context: Dict) -> float:
        """
        Calculate overall fusion score based on weighted contexts
        """
        # Temporal score based on event intensity and patterns
        temporal_score = min(1.0, temporal_context.get("temporal_intensity", 0) / 10)
        if temporal_context.get("is_burst_pattern", False):
            temporal_score += 0.2
        
        # Semantic score based on diversity and severity
        semantic_score = 0.0
        if semantic_context.get("max_severity") == "critical":
            semantic_score += 0.4
        elif semantic_context.get("max_severity") == "high":
            semantic_score += 0.3
        
        if semantic_context.get("is_multi_service", False):
            semantic_score += 0.3
        
        semantic_score += min(0.3, semantic_context.get("type_diversity", 0) / 10)
        
        # Causal score based on causal strength and root cause confidence
        causal_score = causal_context.get("causal_strength", 0) * 0.6
        causal_score += causal_context.get("root_cause_confidence", 0) * 0.4
        
        # Weighted combination
        fusion_score = (
            temporal_score * self.temporal_weight +
            semantic_score * self.semantic_weight +
            causal_score * self.causal_weight
        )
        
        return min(1.0, fusion_score)
