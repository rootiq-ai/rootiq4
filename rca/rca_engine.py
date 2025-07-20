import structlog
import yaml
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from database.connection import db_manager
from database.models import FusedContext, RCAResult
from rca.vector_store import VectorStore
import openai
import os

logger = structlog.get_logger(__name__)

class RCAEngine:
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)
        
        self.db_manager = db_manager
        self.vector_store = VectorStore(config_path)
        
        # LLM configuration
        llm_config = self.config['llm']
        self.provider = llm_config['provider']
        self.model = llm_config['model']
        self.temperature = llm_config['temperature']
        self.max_tokens = llm_config['max_tokens']
        
        # RCA configuration
        rca_config = self.config['rca']
        self.confidence_threshold = rca_config['confidence_threshold']
        self.max_context_length = rca_config['max_context_length']
        self.enable_agentic_fallback = rca_config['enable_agentic_fallback']
        
        # Initialize OpenAI client
        if self.provider == "openai":
            openai.api_key = os.getenv("OPENAI_API_KEY")
    
    def analyze_incidents(self, lookback_hours: int = 1) -> List[str]:
        """
        Analyze recent incidents that don't have RCA results yet
        Returns list of incident IDs that were analyzed
        """
        session = self.db_manager.get_session()
        try:
            # Get fused contexts without RCA results
            unanalyzed_incidents = session.query(FusedContext).filter(
                ~FusedContext.incident_id.in_(
                    session.query(RCAResult.incident_id)
                )
            ).all()
            
            analyzed_ids = []
            for incident in unanalyzed_incidents:
                result_id = self._analyze_single_incident(session, incident)
                if result_id:
                    analyzed_ids.append(incident.incident_id)
            
            session.commit()
            logger.info(f"Analyzed {len(analyzed_ids)} incidents")
            return analyzed_ids
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error analyzing incidents: {e}")
            raise
        finally:
            session.close()
    
    def _analyze_single_incident(self, session: Session, fused_context: FusedContext) -> Optional[int]:
        """
        Analyze a single incident and create RCA result
        """
        try:
            # Prepare incident context
            incident_context = {
                "incident_id": fused_context.incident_id,
                "temporal_context": fused_context.temporal_context,
                "semantic_context": fused_context.semantic_context,
                "causal_context": fused_context.causal_context,
                "fusion_score": fused_context.fusion_score
            }
            
            # Search for similar historical patterns
            similar_patterns = self.vector_store.search_similar_patterns(incident_context, top_k=3)
            
            # Generate RCA using LLM
            rca_result = self._generate_llm_rca(incident_context, similar_patterns)
            
            # Check confidence threshold
            if rca_result["confidence_score"] < (self.confidence_threshold / 100.0):
                if self.enable_agentic_fallback:
                    # Mark for agentic analysis (would be handled by agentic layer)
                    rca_result["analysis_method"] = "pending_agentic"
                    rca_result["suggested_fix"] = "Requires deeper analysis with external tools"
                else:
                    rca_result["analysis_method"] = "llm_low_confidence"
            else:
                rca_result["analysis_method"] = "llm"
            
            # Store RCA result
            rca_record = RCAResult(
                incident_id=fused_context.incident_id,
                root_cause=rca_result["root_cause"],
                confidence_score=rca_result["confidence_score"],
                suggested_fix=rca_result["suggested_fix"],
                analysis_method=rca_result["analysis_method"],
                llm_reasoning=rca_result["llm_reasoning"],
                vector_matches={"similar_patterns": similar_patterns}
            )
            
            session.add(rca_record)
            
            logger.info(f"Generated RCA for incident {fused_context.incident_id}", 
                       confidence=rca_result["confidence_score"])
            
            return rca_record.id
            
        except Exception as e:
            logger.error(f"Error analyzing incident {fused_context.incident_id}: {e}")
            return None
    
    def _generate_llm_rca(self, incident_context: Dict[str, Any], similar_patterns: List[Dict]) -> Dict[str, Any]:
        """
        Generate RCA using LLM with RAG context
        """
        try:
            # Prepare prompt
            prompt = self._build_rca_prompt(incident_context, similar_patterns)
            
            # Call LLM
            if self.provider == "openai":
                response = openai.ChatCompletion.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self._get_system_prompt()},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )
                
                response_text = response.choices[0].message.content
            else:
                # Placeholder for other LLM providers (e.g., local LLaMA)
                response_text = self._mock_llm_response(incident_context)
            
            # Parse LLM response
            return self._parse_llm_response(response_text)
            
        except Exception as e:
            logger.error(f"Error generating LLM RCA: {e}")
            # Return fallback response
            return {
                "root_cause": "Unable to determine root cause due to LLM error",
                "confidence_score": 0.1,
                "suggested_fix": "Manual investigation required",
                "llm_reasoning": f"LLM error: {str(e)}"
            }
    
    def _build_rca_prompt(self, incident_context: Dict[str, Any], similar_patterns: List[Dict]) -> str:
        """
        Build the prompt for LLM RCA analysis
        """
        prompt_parts = []
        
        # Incident overview
        prompt_parts.append("=== INCIDENT ANALYSIS REQUEST ===")
        prompt_parts.append(f"Incident ID: {incident_context['incident_id']}")
        prompt_parts.append(f"Fusion Score: {incident_context['fusion_score']:.2f}")
        
        # Temporal context
        temporal = incident_context.get("temporal_context", {})
        if temporal:
            prompt_parts.append("\\n--- TEMPORAL CONTEXT ---")
            prompt_parts.append(f"Event Count: {temporal.get('event_count', 0)}")
            prompt_parts.append(f"Duration: {temporal.get('duration_seconds', 0)} seconds")
            prompt_parts.append(f"Intensity: {temporal.get('temporal_intensity', 0):.1f} events/min")
            if temporal.get("is_burst_pattern"):
                prompt_parts.append("⚠️ BURST PATTERN DETECTED")
        
        # Semantic context
        semantic = incident_context.get("semantic_context", {})
        if semantic:
            prompt_parts.append("\\n--- SEMANTIC CONTEXT ---")
            prompt_parts.append(f"Category: {semantic.get('incident_category', 'unknown')}")
            prompt_parts.append(f"Max Severity: {semantic.get('max_severity', 'info')}")
            prompt_parts.append(f"Multi-Service: {semantic.get('is_multi_service', False)}")
            
            keywords = semantic.get("common_keywords", [])
            if keywords:
                prompt_parts.append(f"Keywords: {', '.join(keywords[:5])}")
            
            sources = semantic.get("sources", {})
            if sources:
                source_list = [f"{k}({v})" for k, v in sources.items()]
                prompt_parts.append(f"Sources: {', '.join(source_list)}")
        
        # Causal context
        causal = incident_context.get("causal_context", {})
        if causal:
            prompt_parts.append("\\n--- CAUSAL CONTEXT ---")
            prompt_parts.append(f"Causal Strength: {causal.get('causal_strength', 0):.2f}")
            prompt_parts.append(f"Root Cause Confidence: {causal.get('root_cause_confidence', 0):.2f}")
            
            if causal.get("has_clear_progression"):
                prompt_parts.append("✅ Clear causal progression identified")
            
            root_causes = causal.get("potential_root_causes", [])
            if root_causes:
                prompt_parts.append("Potential Root Causes:")
                for rc in root_causes[:2]:
                    prompt_parts.append(f"  - {rc.get('event_source', 'unknown')}: {rc.get('event_message', 'no message')} (confidence: {rc.get('confidence', 0):.2f})")
        
        # Similar patterns from RAG
        if similar_patterns:
            prompt_parts.append("\\n--- SIMILAR HISTORICAL PATTERNS ---")
            for i, pattern in enumerate(similar_patterns[:2]):
                prompt_parts.append(f"\\nPattern {i+1} (similarity: {pattern['similarity_score']:.2f}):")
                prompt_parts.append(f"Description: {pattern['pattern_text'][:200]}...")
                
                if pattern.get("resolution_steps"):
                    prompt_parts.append("Previous resolution steps:")
                    for step in pattern["resolution_steps"][:3]:
                        prompt_parts.append(f"  - {step}")
        
        prompt_parts.append("\\n=== ANALYSIS REQUEST ===")
        prompt_parts.append("Based on the above incident data and historical patterns, provide:")
        prompt_parts.append("1. Root cause analysis")
        prompt_parts.append("2. Confidence score (0-1)")
        prompt_parts.append("3. Suggested fix/remediation steps")
        prompt_parts.append("4. Reasoning for your analysis")
        
        return "\\n".join(prompt_parts)
    
    def _get_system_prompt(self) -> str:
        """
        Get the system prompt for RCA analysis
        """
        return """You are an expert Site Reliability Engineer (SRE) specializing in incident root cause analysis. 

Your task is to analyze incidents based on temporal, semantic, and causal context, along with similar historical patterns.

Provide your response in this JSON format:
{
    "root_cause": "Clear, specific description of the root cause",
    "confidence_score": 0.85,
    "suggested_fix": "Step-by-step remediation plan",
    "llm_reasoning": "Detailed explanation of your analysis"
}

Guidelines:
- Be specific and actionable in your root cause identification
- Consider temporal patterns (burst events, timing)
- Weight semantic context (severity, multi-service impacts)
- Use causal relationships to trace event sequences
- Leverage similar historical patterns for guidance
- Provide confidence scores based on evidence strength
- Suggest immediate and long-term fixes
- If confidence is low, explain why and what additional data would help"""
    
    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse LLM response into structured format
        """
        try:
            # Try to parse as JSON first
            if "{" in response_text and "}" in response_text:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                json_str = response_text[start:end]
                parsed = json.loads(json_str)
                
                # Validate required fields
                required_fields = ["root_cause", "confidence_score", "suggested_fix", "llm_reasoning"]
                for field in required_fields:
                    if field not in parsed:
                        parsed[field] = f"Missing {field}"
                
                # Ensure confidence is in valid range
                if not isinstance(parsed["confidence_score"], (int, float)) or not (0 <= parsed["confidence_score"] <= 1):
                    parsed["confidence_score"] = 0.5
                
                return parsed
            
            # Fallback parsing if JSON fails
            return self._fallback_parse(response_text)
            
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return self._fallback_parse(response_text)
    
    def _fallback_parse(self, response_text: str) -> Dict[str, Any]:
        """
        Fallback parsing when JSON parsing fails
        """
        return {
            "root_cause": "Analysis completed but response format unclear",
            "confidence_score": 0.3,
            "suggested_fix": "Manual review of incident required",
            "llm_reasoning": response_text[:500] + "..." if len(response_text) > 500 else response_text
        }
    
    def _mock_llm_response(self, incident_context: Dict[str, Any]) -> str:
        """
        Mock LLM response for testing when no API key is available
        """
        semantic = incident_context.get("semantic_context", {})
        category = semantic.get("incident_category", "unknown")
        severity = semantic.get("max_severity", "info")
        
        return f"""{{
    "root_cause": "Incident appears to be a {category} issue with {severity} severity. Based on the patterns observed, this is likely caused by resource constraints or configuration issues.",
    "confidence_score": 0.75,
    "suggested_fix": "1. Check resource utilization (CPU, memory, disk)\\n2. Review recent configuration changes\\n3. Scale resources if needed\\n4. Monitor for recurrence",
    "llm_reasoning": "The incident shows characteristics of a {category} problem with {severity} severity. The temporal patterns and service involvement suggest a systemic issue that requires immediate attention and resource scaling."
}}"""
    
    def get_incident_rca(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """
        Get RCA result for a specific incident
        """
        session = self.db_manager.get_session()
        try:
            rca_result = session.query(RCAResult).filter_by(incident_id=incident_id).first()
            
            if not rca_result:
                return None
            
            return {
                "incident_id": rca_result.incident_id,
                "root_cause": rca_result.root_cause,
                "confidence_score": rca_result.confidence_score,
                "suggested_fix": rca_result.suggested_fix,
                "analysis_method": rca_result.analysis_method,
                "llm_reasoning": rca_result.llm_reasoning,
                "vector_matches": rca_result.vector_matches,
                "created_at": rca_result.created_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error retrieving RCA for incident {incident_id}: {e}")
            return None
        finally:
            session.close()
    
    def get_pending_agentic_incidents(self) -> List[str]:
        """
        Get incidents that require agentic analysis (low confidence LLM results)
        """
        session = self.db_manager.get_session()
        try:
            pending_incidents = session.query(RCAResult.incident_id).filter(
                RCAResult.analysis_method == "pending_agentic"
            ).all()
            
            return [incident[0] for incident in pending_incidents]
            
        except Exception as e:
            logger.error(f"Error retrieving pending agentic incidents: {e}")
            return []
        finally:
            session.close()
