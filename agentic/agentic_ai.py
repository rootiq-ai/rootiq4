import structlog
import yaml
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from database.connection import db_manager
from database.models import RCAResult, AgenticInvocation
import requests
import subprocess

logger = structlog.get_logger(__name__)

class AgenticAI:
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)
        
        self.db_manager = db_manager
        
        # Available tools for agentic analysis
        self.available_tools = {
            "query_monitoring_tools": self._query_monitoring_tools,
            "github_artifacts": self._analyze_github_artifacts,
            "analyze_source_repos": self._analyze_source_repos,
            "fetch_external_context": self._fetch_external_context
        }
    
    def analyze_low_confidence_incidents(self) -> List[str]:
        """
        Analyze incidents that have low confidence from LLM analysis
        """
        session = self.db_manager.get_session()
        try:
            # Get incidents marked for agentic analysis
            pending_incidents = session.query(RCAResult).filter(
                RCAResult.analysis_method == "pending_agentic"
            ).all()
            
            analyzed_ids = []
            for rca_result in pending_incidents:
                success = self._perform_agentic_analysis(session, rca_result)
                if success:
                    analyzed_ids.append(rca_result.incident_id)
            
            session.commit()
            logger.info(f"Performed agentic analysis on {len(analyzed_ids)} incidents")
            return analyzed_ids
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error in agentic analysis: {e}")
            raise
        finally:
            session.close()
    
    def _perform_agentic_analysis(self, session: Session, rca_result: RCAResult) -> bool:
        """
        Perform deep agentic analysis on a single incident
        """
        try:
            start_time = time.time()
            
            # Gather additional context using various tools
            external_context = {}
            tools_used = []
            
            # Tool 1: Query monitoring tools
            monitoring_data = self._query_monitoring_tools(rca_result.incident_id)
            if monitoring_data:
                external_context["monitoring"] = monitoring_data
                tools_used.append("query_monitoring_tools")
            
            # Tool 2: Analyze GitHub artifacts (recent deployments, issues)
            github_data = self._analyze_github_artifacts(rca_result.incident_id)
            if github_data:
                external_context["github"] = github_data
                tools_used.append("github_artifacts")
            
            # Tool 3: Analyze source repositories for recent changes
            source_analysis = self._analyze_source_repos(rca_result.incident_id)
            if source_analysis:
                external_context["source_analysis"] = source_analysis
                tools_used.append("analyze_source_repos")
            
            # Tool 4: Fetch external context (status pages, dependencies)
            external_status = self._fetch_external_context(rca_result.incident_id)
            if external_status:
                external_context["external_status"] = external_status
                tools_used.append("fetch_external_context")
            
            # Synthesize findings
            enhanced_analysis = self._synthesize_agentic_findings(rca_result, external_context)
            
            # Calculate confidence improvement
            original_confidence = rca_result.confidence_score
            confidence_improvement = enhanced_analysis["confidence_score"] - original_confidence
            
            # Update RCA result
            rca_result.root_cause = enhanced_analysis["root_cause"]
            rca_result.confidence_score = enhanced_analysis["confidence_score"]
            rca_result.suggested_fix = enhanced_analysis["suggested_fix"]
            rca_result.analysis_method = "agentic"
            rca_result.llm_reasoning = enhanced_analysis["reasoning"]
            
            # Create agentic invocation record
            execution_time = time.time() - start_time
            agentic_record = AgenticInvocation(
                incident_id=rca_result.incident_id,
                tools_used={"tools": tools_used},
                external_context=external_context,
                analysis_result=enhanced_analysis["reasoning"],
                confidence_improvement=confidence_improvement,
                execution_time_seconds=execution_time
            )
            
            session.add(agentic_record)
            
            logger.info(f"Enhanced analysis for incident {rca_result.incident_id}", 
                       confidence_improvement=confidence_improvement,
                       tools_used=len(tools_used))
            
            return True
            
        except Exception as e:
            logger.error(f"Error in agentic analysis for {rca_result.incident_id}: {e}")
            return False
    
    def _query_monitoring_tools(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """
        Tool 1: Query monitoring tools for additional metrics and context
        """
        try:
            # This would integrate with actual monitoring tools like Prometheus, Grafana, etc.
            # For MVP, we'll simulate the analysis
            
            monitoring_data = {
                "cpu_utilization": {
                    "max": 85.5,
                    "avg": 72.3,
                    "trend": "increasing"
                },
                "memory_usage": {
                    "max": 78.2,
                    "avg": 65.1,
                    "trend": "stable"
                },
                "network_io": {
                    "max_connections": 1250,
                    "errors": 23,
                    "trend": "spike_detected"
                },
                "disk_io": {
                    "read_latency_ms": 15.2,
                    "write_latency_ms": 22.1,
                    "trend": "normal"
                },
                "service_health": {
                    "services_down": ["user-service-replica-2"],
                    "services_degraded": ["auth-service"],
                    "total_services": 12
                }
            }
            
            # Simulate API call delay
            time.sleep(0.1)
            
            logger.info(f"Retrieved monitoring data for incident {incident_id}")
            return monitoring_data
            
        except Exception as e:
            logger.error(f"Error querying monitoring tools: {e}")
            return None
    
    def _analyze_github_artifacts(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """
        Tool 2: Analyze GitHub for recent deployments, issues, and PRs
        """
        try:
            # This would integrate with GitHub API to check recent activity
            # For MVP, we'll simulate the analysis
            
            github_data = {
                "recent_deployments": [
                    {
                        "service": "user-service",
                        "version": "v2.1.3",
                        "deployed_at": "2024-01-15T14:30:00Z",
                        "commit_hash": "abc123def",
                        "changes": ["Updated authentication logic", "Fixed memory leak"]
                    },
                    {
                        "service": "auth-service",
                        "version": "v1.8.2",
                        "deployed_at": "2024-01-15T13:45:00Z",
                        "commit_hash": "def456ghi",
                        "changes": ["Database connection pool optimization"]
                    }
                ],
                "recent_issues": [
                    {
                        "title": "High CPU usage after v2.1.3 deployment",
                        "state": "open",
                        "created_at": "2024-01-15T15:00:00Z",
                        "labels": ["bug", "performance"]
                    }
                ],
                "recent_prs": [
                    {
                        "title": "Fix memory leak in user session handling",
                        "merged_at": "2024-01-15T14:00:00Z",
                        "files_changed": ["src/auth/session.py", "src/utils/memory.py"]
                    }
                ]
            }
            
            # Simulate API call delay
            time.sleep(0.2)
            
            logger.info(f"Retrieved GitHub artifacts for incident {incident_id}")
            return github_data
            
        except Exception as e:
            logger.error(f"Error analyzing GitHub artifacts: {e}")
            return None
    
    def _analyze_source_repos(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """
        Tool 3: Analyze source code repositories for recent changes
        """
        try:
            # This would analyze git history, code changes, and patterns
            # For MVP, we'll simulate the analysis
            
            source_analysis = {
                "recent_commits": [
                    {
                        "hash": "abc123def",
                        "message": "Fix authentication timeout issue",
                        "author": "developer@company.com",
                        "timestamp": "2024-01-15T14:15:00Z",
                        "files_modified": ["auth/timeout.py"],
                        "risk_score": 0.7
                    }
                ],
                "code_hotspots": [
                    {
                        "file": "src/auth/session.py",
                        "function": "create_session",
                        "complexity_score": 8.5,
                        "recent_changes": 3,
                        "bug_history": 2
                    }
                ],
                "dependency_changes": [
                    {
                        "package": "redis-py",
                        "old_version": "4.5.1",
                        "new_version": "4.5.4",
                        "change_type": "patch",
                        "security_fixes": True
                    }
                ],
                "test_coverage": {
                    "overall": 0.78,
                    "recent_changes": 0.65,
                    "critical_paths": 0.82
                }
            }
            
            # Simulate analysis delay
            time.sleep(0.3)
            
            logger.info(f"Completed source analysis for incident {incident_id}")
            return source_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing source repos: {e}")
            return None
    
    def _fetch_external_context(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """
        Tool 4: Fetch external context from status pages and dependencies
        """
        try:
            # This would check external service status pages, cloud provider status, etc.
            # For MVP, we'll simulate the checks
            
            external_context = {
                "cloud_provider_status": {
                    "aws_us_east_1": "operational",
                    "aws_eu_west_1": "degraded_performance",
                    "incidents": [
                        {
                            "service": "EC2",
                            "region": "eu-west-1",
                            "impact": "Increased instance launch times",
                            "started_at": "2024-01-15T14:20:00Z"
                        }
                    ]
                },
                "dependency_status": {
                    "redis_cluster": {
                        "status": "operational",
                        "latency_ms": 2.3,
                        "error_rate": 0.001
                    },
                    "postgres_primary": {
                        "status": "operational",
                        "connection_pool": "75% utilized",
                        "query_latency_ms": 45.2
                    },
                    "external_api": {
                        "status": "degraded",
                        "success_rate": 0.89,
                        "avg_response_ms": 1200
                    }
                },
                "security_alerts": [],
                "network_issues": [
                    {
                        "type": "packet_loss",
                        "location": "eu-west datacenter",
                        "severity": "low",
                        "impact": "< 1% requests affected"
                    }
                ]
            }
            
            # Simulate external API calls
            time.sleep(0.4)
            
            logger.info(f"Retrieved external context for incident {incident_id}")
            return external_context
            
        except Exception as e:
            logger.error(f"Error fetching external context: {e}")
            return None
    
    def _synthesize_agentic_findings(self, original_rca: RCAResult, external_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synthesize all agentic findings into enhanced analysis
        """
        try:
            findings = []
            confidence_factors = []
            
            # Analyze monitoring data
            monitoring = external_context.get("monitoring", {})
            if monitoring:
                cpu_usage = monitoring.get("cpu_utilization", {})
                if cpu_usage.get("max", 0) > 80:
                    findings.append("High CPU utilization detected (max: {:.1f}%)".format(cpu_usage.get("max", 0)))
                    confidence_factors.append(0.2)
                
                service_health = monitoring.get("service_health", {})
                if service_health.get("services_down"):
                    findings.append(f"Services down: {', '.join(service_health['services_down'])}")
                    confidence_factors.append(0.3)
            
            # Analyze GitHub data
            github = external_context.get("github", {})
            if github:
                recent_deployments = github.get("recent_deployments", [])
                for deployment in recent_deployments:
                    # Check if deployment was recent (within incident timeframe)
                    findings.append(f"Recent deployment: {deployment['service']} v{deployment['version']}")
                    confidence_factors.append(0.25)
                
                recent_issues = github.get("recent_issues", [])
                for issue in recent_issues:
                    if "performance" in issue.get("labels", []):
                        findings.append(f"Related GitHub issue: {issue['title']}")
                        confidence_factors.append(0.2)
            
            # Analyze source code changes
            source = external_context.get("source_analysis", {})
            if source:
                hotspots = source.get("code_hotspots", [])
                for hotspot in hotspots:
                    if hotspot.get("risk_score", 0) > 0.7:
                        findings.append(f"High-risk code area: {hotspot['file']} (risk: {hotspot['risk_score']:.1f})")
                        confidence_factors.append(0.15)
            
            # Analyze external context
            external = external_context.get("external_status", {})
            if external:
                cloud_status = external.get("cloud_provider_status", {})
                incidents = cloud_status.get("incidents", [])
                for incident in incidents:
                    findings.append(f"Cloud provider issue: {incident['service']} - {incident['impact']}")
                    confidence_factors.append(0.1)
                
                deps = external.get("dependency_status", {})
                for dep_name, dep_status in deps.items():
                    if dep_status.get("status") == "degraded":
                        findings.append(f"Degraded dependency: {dep_name}")
                        confidence_factors.append(0.15)
            
            # Synthesize enhanced root cause
            enhanced_root_cause = original_rca.root_cause
            if findings:
                enhanced_root_cause += f"\\n\\nAdditional findings from agentic analysis:\\n• " + "\\n• ".join(findings)
            
            # Calculate enhanced confidence
            base_confidence = original_rca.confidence_score
            confidence_boost = min(0.3, sum(confidence_factors))  # Cap at 30% boost
            enhanced_confidence = min(0.95, base_confidence + confidence_boost)
            
            # Generate enhanced suggested fix
            enhanced_fix = self._generate_enhanced_fix(original_rca.suggested_fix, external_context)
            
            # Generate detailed reasoning
            reasoning = f"""Enhanced analysis using agentic tools:

Original LLM Analysis:
{original_rca.llm_reasoning}

Agentic Findings:
{chr(10).join(f"• {finding}" for finding in findings)}

Confidence increased from {base_confidence:.2f} to {enhanced_confidence:.2f} based on:
{chr(10).join(f"• Additional evidence factor: +{factor:.2f}" for factor in confidence_factors)}

The agentic analysis provides concrete evidence supporting the initial assessment and adds specific technical details for remediation."""
            
            return {
                "root_cause": enhanced_root_cause,
                "confidence_score": enhanced_confidence,
                "suggested_fix": enhanced_fix,
                "reasoning": reasoning
            }
            
        except Exception as e:
            logger.error(f"Error synthesizing agentic findings: {e}")
            # Return enhanced version of original
            return {
                "root_cause": original_rca.root_cause + "\\n\\n[Agentic analysis completed with partial results]",
                "confidence_score": min(0.85, original_rca.confidence_score + 0.1),
                "suggested_fix": original_rca.suggested_fix,
                "reasoning": f"{original_rca.llm_reasoning}\\n\\n[Agentic analysis error: {str(e)}]"
            }
    
    def _generate_enhanced_fix(self, original_fix: str, external_context: Dict[str, Any]) -> str:
        """
        Generate enhanced fix suggestions based on external context
        """
        enhanced_steps = [original_fix]
        
        # Add specific steps based on findings
        monitoring = external_context.get("monitoring", {})
        if monitoring:
            services_down = monitoring.get("service_health", {}).get("services_down", [])
            if services_down:
                enhanced_steps.append(f"\\nImmediate actions:\\n• Restart failed services: {', '.join(services_down)}")
        
        github = external_context.get("github", {})
        if github:
            recent_deployments = github.get("recent_deployments", [])
            if recent_deployments:
                enhanced_steps.append("\\nDeployment-related actions:\\n• Consider rollback if issues persist\\n• Review recent deployment changes")
        
        external = external_context.get("external_status", {})
        if external:
            degraded_deps = []
            deps = external.get("dependency_status", {})
            for dep_name, dep_status in deps.items():
                if dep_status.get("status") == "degraded":
                    degraded_deps.append(dep_name)
            
            if degraded_deps:
                enhanced_steps.append(f"\\nDependency actions:\\n• Monitor {', '.join(degraded_deps)} recovery\\n• Implement circuit breakers if needed")
        
        return "\\n".join(enhanced_steps)
    
    def get_agentic_invocation_stats(self) -> Dict[str, Any]:
        """
        Get statistics about agentic invocations
        """
        session = self.db_manager.get_session()
        try:
            invocations = session.query(AgenticInvocation).all()
            
            if not invocations:
                return {"total_invocations": 0}
            
            total_invocations = len(invocations)
            avg_execution_time = sum(inv.execution_time_seconds for inv in invocations) / total_invocations
            avg_confidence_improvement = sum(inv.confidence_improvement for inv in invocations) / total_invocations
            
            # Tool usage statistics
            tool_usage = {}
            for inv in invocations:
                tools = inv.tools_used.get("tools", [])
                for tool in tools:
                    tool_usage[tool] = tool_usage.get(tool, 0) + 1
            
            return {
                "total_invocations": total_invocations,
                "average_execution_time_seconds": avg_execution_time,
                "average_confidence_improvement": avg_confidence_improvement,
                "tool_usage_counts": tool_usage
            }
            
        except Exception as e:
            logger.error(f"Error getting agentic stats: {e}")
            return {"error": str(e)}
        finally:
            session.close()
