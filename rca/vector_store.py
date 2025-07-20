import structlog
import yaml
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
import json
import uuid
from database.connection import db_manager
from database.models import HistoricalPattern

logger = structlog.get_logger(__name__)

class VectorStore:
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)
        
        vector_config = self.config['vector_db']
        
        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(
            path=vector_config['persist_directory']
        )
        
        self.collection_name = vector_config['collection_name']
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "RCA historical patterns and solutions"}
        )
        
        # Initialize sentence transformer for embeddings
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        
        self.db_manager = db_manager
    
    def add_historical_pattern(self, incident_context: Dict[str, Any], resolution_steps: List[str], 
                             success_rate: float = 1.0) -> str:
        """
        Add a historical pattern to the vector store and database
        """
        try:
            # Create pattern signature
            pattern_signature = self._create_pattern_signature(incident_context)
            
            # Create text representation for embedding
            pattern_text = self._context_to_text(incident_context, resolution_steps)
            
            # Generate embedding
            embedding = self.encoder.encode(pattern_text).tolist()
            
            # Generate unique ID
            pattern_id = str(uuid.uuid4())
            
            # Store in ChromaDB
            self.collection.add(
                documents=[pattern_text],
                embeddings=[embedding],
                metadatas=[{
                    "pattern_signature": pattern_signature,
                    "success_rate": success_rate,
                    "resolution_count": len(resolution_steps)
                }],
                ids=[pattern_id]
            )
            
            # Store in PostgreSQL
            session = self.db_manager.get_session()
            try:
                historical_pattern = HistoricalPattern(
                    pattern_signature=pattern_signature,
                    incident_context=incident_context,
                    resolution_steps={"steps": resolution_steps},
                    success_rate=success_rate,
                    embedding_vector=embedding
                )
                
                session.add(historical_pattern)
                session.commit()
                
                logger.info(f"Added historical pattern {pattern_id}", pattern_signature=pattern_signature)
                return pattern_id
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error storing pattern in database: {e}")
                raise
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"Error adding historical pattern: {e}")
            raise
    
    def search_similar_patterns(self, incident_context: Dict[str, Any], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for similar historical patterns
        """
        try:
            # Create query text from incident context
            query_text = self._context_to_text(incident_context)
            
            # Generate query embedding
            query_embedding = self.encoder.encode(query_text).tolist()
            
            # Search ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k
            )
            
            # Format results
            similar_patterns = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    pattern = {
                        "id": results['ids'][0][i],
                        "similarity_score": 1 - results['distances'][0][i],  # Convert distance to similarity
                        "pattern_text": doc,
                        "metadata": results['metadatas'][0][i],
                        "resolution_steps": self._get_resolution_steps(results['ids'][0][i])
                    }
                    similar_patterns.append(pattern)
            
            logger.info(f"Found {len(similar_patterns)} similar patterns")
            return similar_patterns
            
        except Exception as e:
            logger.error(f"Error searching similar patterns: {e}")
            return []
    
    def _create_pattern_signature(self, incident_context: Dict[str, Any]) -> str:
        """
        Create a unique signature for the incident pattern
        """
        # Extract key characteristics
        semantic_context = incident_context.get("semantic_context", {})
        temporal_context = incident_context.get("temporal_context", {})
        
        signature_parts = []
        
        # Add incident category
        category = semantic_context.get("incident_category", "unknown")
        signature_parts.append(f"category:{category}")
        
        # Add max severity
        max_severity = semantic_context.get("max_severity", "info")
        signature_parts.append(f"severity:{max_severity}")
        
        # Add service diversity
        is_multi_service = semantic_context.get("is_multi_service", False)
        signature_parts.append(f"multi_service:{is_multi_service}")
        
        # Add temporal pattern
        is_burst = temporal_context.get("is_burst_pattern", False)
        signature_parts.append(f"burst:{is_burst}")
        
        return "|".join(signature_parts)
    
    def _context_to_text(self, incident_context: Dict[str, Any], resolution_steps: List[str] = None) -> str:
        """
        Convert incident context to text for embedding
        """
        text_parts = []
        
        # Add semantic context
        semantic_context = incident_context.get("semantic_context", {})
        if semantic_context:
            text_parts.append(f"Incident category: {semantic_context.get('incident_category', 'unknown')}")
            text_parts.append(f"Max severity: {semantic_context.get('max_severity', 'info')}")
            
            # Add common keywords
            keywords = semantic_context.get("common_keywords", [])
            if keywords:
                text_parts.append(f"Keywords: {', '.join(keywords)}")
            
            # Add event types and sources
            event_types = semantic_context.get("event_types", {})
            if event_types:
                text_parts.append(f"Event types: {', '.join(event_types.keys())}")
            
            sources = semantic_context.get("sources", {})
            if sources:
                text_parts.append(f"Sources: {', '.join(sources.keys())}")
        
        # Add temporal context
        temporal_context = incident_context.get("temporal_context", {})
        if temporal_context:
            if temporal_context.get("is_burst_pattern"):
                text_parts.append("Burst pattern detected")
            
            intensity = temporal_context.get("temporal_intensity", 0)
            text_parts.append(f"Event intensity: {intensity:.2f} events per minute")
        
        # Add causal context
        causal_context = incident_context.get("causal_context", {})
        if causal_context:
            if causal_context.get("has_clear_progression"):
                text_parts.append("Clear causal progression identified")
            
            root_causes = causal_context.get("potential_root_causes", [])
            if root_causes:
                root_cause_sources = [rc.get("event_source", "") for rc in root_causes[:2]]
                text_parts.append(f"Potential root causes: {', '.join(root_cause_sources)}")
        
        # Add resolution steps if provided
        if resolution_steps:
            text_parts.append("Resolution steps:")
            for step in resolution_steps[:3]:  # Include first 3 steps
                text_parts.append(f"- {step}")
        
        return " ".join(text_parts)
    
    def _get_resolution_steps(self, pattern_id: str) -> List[str]:
        """
        Get resolution steps for a pattern from the database
        """
        session = self.db_manager.get_session()
        try:
            pattern = session.query(HistoricalPattern).filter_by(id=pattern_id).first()
            if pattern and pattern.resolution_steps:
                return pattern.resolution_steps.get("steps", [])
            return []
        except Exception as e:
            logger.error(f"Error retrieving resolution steps: {e}")
            return []
        finally:
            session.close()
    
    def add_sample_patterns(self) -> List[str]:
        """
        Add sample historical patterns for testing
        """
        sample_patterns = [
            {
                "incident_context": {
                    "semantic_context": {
                        "incident_category": "performance",
                        "max_severity": "critical",
                        "common_keywords": ["cpu", "high", "usage", "timeout"],
                        "event_types": {"metric": 2, "event": 1},
                        "sources": {"prometheus": 2, "application": 1},
                        "is_multi_service": True
                    },
                    "temporal_context": {
                        "is_burst_pattern": True,
                        "temporal_intensity": 15.5
                    },
                    "causal_context": {
                        "has_clear_progression": True,
                        "potential_root_causes": [
                            {"event_source": "prometheus", "confidence": 0.9}
                        ]
                    }
                },
                "resolution_steps": [
                    "Scale up application instances",
                    "Optimize database queries",
                    "Add CPU monitoring alerts"
                ],
                "success_rate": 0.95
            },
            {
                "incident_context": {
                    "semantic_context": {
                        "incident_category": "connectivity",
                        "max_severity": "high",
                        "common_keywords": ["connection", "refused", "timeout"],
                        "event_types": {"log": 3, "event": 1},
                        "sources": {"application": 3, "load_balancer": 1},
                        "is_multi_service": True
                    },
                    "temporal_context": {
                        "is_burst_pattern": False,
                        "temporal_intensity": 2.1
                    },
                    "causal_context": {
                        "has_clear_progression": False,
                        "potential_root_causes": [
                            {"event_source": "load_balancer", "confidence": 0.7}
                        ]
                    }
                },
                "resolution_steps": [
                    "Restart load balancer",
                    "Check network connectivity",
                    "Update firewall rules"
                ],
                "success_rate": 0.85
            },
            {
                "incident_context": {
                    "semantic_context": {
                        "incident_category": "application",
                        "max_severity": "medium",
                        "common_keywords": ["error", "exception", "failed"],
                        "event_types": {"log": 4},
                        "sources": {"application": 4},
                        "is_multi_service": False
                    },
                    "temporal_context": {
                        "is_burst_pattern": True,
                        "temporal_intensity": 8.2
                    },
                    "causal_context": {
                        "has_clear_progression": True,
                        "potential_root_causes": [
                            {"event_source": "application", "confidence": 0.8}
                        ]
                    }
                },
                "resolution_steps": [
                    "Review application logs",
                    "Restart application service",
                    "Deploy hotfix if needed"
                ],
                "success_rate": 0.9
            }
        ]
        
        pattern_ids = []
        for pattern in sample_patterns:
            pattern_id = self.add_historical_pattern(
                pattern["incident_context"],
                pattern["resolution_steps"],
                pattern["success_rate"]
            )
            pattern_ids.append(pattern_id)
        
        return pattern_ids
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the vector collection
        """
        try:
            count = self.collection.count()
            return {
                "total_patterns": count,
                "collection_name": self.collection_name
            }
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {"total_patterns": 0, "collection_name": self.collection_name}
