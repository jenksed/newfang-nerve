from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime
import random

from newfang.lifecycle.engine import EvaluationContext, GateName
from newfang.models.uow import UoWState

class SimulationDecision(str, Enum):
    LOW_RISK = "LOW_RISK"
    MEDIUM_RISK = "MEDIUM_RISK"
    HIGH_RISK = "HIGH_RISK"

class SimulationResult(BaseModel):
    """
    The structured output from the Simulation Engine.
    """
    simulation_id: str = Field(..., description="Unique identifier for this simulation run")
    decision: SimulationDecision = Field(..., description="Overall risk assessment from the simulation")
    estimated_effort_hours: Optional[float] = Field(None, description="Estimated effort in hours")
    likely_blockers: List[str] = Field(default_factory=list, description="Predicted potential blockers")
    dependency_conflicts: List[str] = Field(default_factory=list, description="Identified dependency conflicts")
    historical_similarity_outcomes: List[Dict[str, Any]] = Field(default_factory=list, description="Outcomes from historically similar UoWs")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the simulation's predictions")
    recommended_changes: List[str] = Field(default_factory=list, description="Recommendations to mitigate risks or improve predictability")
    score_contribution: float = Field(0.0, ge=-1.0, le=1.0, description="Contribution to the overall gate score based on simulation risk")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional detailed output from the simulation")

# --- Placeholder Services (will be separate modules in a real system) ---
class HistoricalDataService:
    """Simulates access to historical UoW data."""
    def get_similar_uows_outcomes(self, uow: Any) -> List[Dict[str, Any]]:
        # In a real system: query vector DB for similar UoWs, retrieve their outcomes
        if "complex" in uow.objective.lower():
            return [{"uow_id": "HIST-001", "outcome": "delayed", "delay_days": 5, "reason": "unexpected complexity"}]
        if "ambiguous" in uow.objective.lower():
            return [{"uow_id": "HIST-002", "outcome": "rework", "rework_hours": 10, "reason": "unclear requirements"}]
        return []

class SpineService:
    """Simulates access to the Project Spine."""
    def get_uow_dependency_info(self, uow: Any) -> Dict[str, Any]:
        # In a real system: query graph DB for UoW dependencies, linked code complexity
        if "high-risk-dependency" in uow.dependencies:
            return {"external_dependencies": ["PaymentGatewayAPI"], "internal_dependencies": ["CoreAuthModule"], "complexity_score": 0.8}
        return {"external_dependencies": [], "internal_dependencies": [], "complexity_score": 0.3}

class LLMRiskAssessmentService:
    """Simulates LLM-based risk assessment."""
    async def assess_risk(self, uow: Any) -> Dict[str, Any]:
        # In a real system: call LLM with UoW details, parse structured response
        prompt = f"Assess the risk of implementing the following Unit of Work:\nObjective: {uow.objective}\nAcceptance Criteria: {', '.join(uow.acceptance_criteria)}\n\nProvide a risk level (low, medium, high), estimated effort in hours, and potential blockers/recommendations in JSON format."
        
        # Simulate LLM response
        if "ambiguous" in uow.objective.lower():
            return {"risk_level": "high", "effort": random.randint(30, 60), "blockers": ["unclear requirements", "scope creep"], "recommendations": ["refine objective", "break down ACs"]}
        elif "complex" in uow.objective.lower() or len(uow.acceptance_criteria) > 5:
            return {"risk_level": "medium", "effort": random.randint(20, 40), "blockers": ["technical challenges"], "recommendations": ["spike solution", "senior dev review"]}
        else:
            return {"risk_level": "low", "effort": random.randint(5, 15), "blockers": [], "recommendations": []}

class FailurePatternLibrary:
    """Simulates access to a library of known failure patterns."""
    def identify_patterns(self, uow: Any) -> List[str]:
        patterns = []
        if "untested" in uow.objective.lower(): # Example pattern
            patterns.append("Lack of test coverage leading to regressions")
        return patterns

class DeliveryFingerprints:
    """Simulates access to project/team delivery fingerprints."""
    def get_project_risk_profile(self, project_id: str) -> Dict[str, Any]:
        # In a real system: query for project's historical risk profile
        if project_id == "high-risk-project":
            return {"risk_profile": "drift-prone", "recommended_controls": ["strict gating", "reduced WIP"]}
        return {"risk_profile": "stable", "recommended_controls": []}

# --- Main Simulation Engine ---
class SimulationEngine:
    """
    The engine responsible for simulating UoW execution and predicting risks.
    This will be part of the Simulator Agent.
    """
    def __init__(self):
        self.historical_data_service = HistoricalDataService()
        self.spine_service = SpineService()
        self.llm_risk_assessment_service = LLMRiskAssessmentService()
        self.failure_pattern_library = FailurePatternLibrary()
        self.delivery_fingerprints = DeliveryFingerprints()

    async def run_simulation(self, context: EvaluationContext) -> SimulationResult:
        """
        Runs a simulation for the given UoW to predict execution risk and outcomes.
        """
        uow = context.uow
        
        # 1. Gather data from simulated services
        historical_outcomes = self.historical_data_service.get_similar_uows_outcomes(uow)
        spine_info = self.spine_service.get_uow_dependency_info(uow)
        llm_assessment = await self.llm_risk_assessment_service.assess_risk(uow)
        identified_failure_patterns = self.failure_pattern_library.identify_patterns(uow)
        project_risk_profile = self.delivery_fingerprints.get_project_risk_profile(context.system_context.get("project_id", "default-project"))

        # 2. Aggregate and process risk factors
        risk_factors = []
        estimated_effort = llm_assessment.get("effort", 10.0) # Start with LLM estimate
        likely_blockers = list(llm_assessment.get("blockers", []))
        recommended_changes = list(llm_assessment.get("recommendations", []))
        confidence = 0.8 # Base confidence

        # From UoW attributes
        if not uow.acceptance_criteria:
            risk_factors.append("no_acceptance_criteria")
            likely_blockers.append("Lack of clear acceptance criteria.")
            recommended_changes.append("Define clear and measurable acceptance criteria.")
            confidence -= 0.1
        if len(uow.acceptance_criteria) > 5:
            risk_factors.append("high_ac_count")
            recommended_changes.append("Consider breaking down complex acceptance criteria.")
            estimated_effort += 5
            confidence -= 0.05
        if "ambiguous" in uow.objective.lower():
            risk_factors.append("ambiguous_objective")
            likely_blockers.append("Ambiguous objective leading to scope creep.")
            recommended_changes.append("Refine objective for clarity.")
            estimated_effort += 10
            confidence -= 0.2

        # From historical data
        if historical_outcomes:
            risk_factors.append("historical_issues")
            for outcome in historical_outcomes:
                if outcome.get("outcome") in ["delayed", "rework"]:
                    likely_blockers.append(f"Historical similar UoW experienced: {outcome.get('reason')}")
                    estimated_effort += outcome.get("delay_days", 0) * 8 # Convert days to hours
                    confidence -= 0.15

        # From Spine info
        if spine_info.get("complexity_score", 0) > 0.7:
            risk_factors.append("high_code_complexity")
            likely_blockers.append("High complexity in linked code modules.")
            recommended_changes.append("Conduct a technical spike or senior review.")
            estimated_effort += 15
            confidence -= 0.1
        if spine_info.get("external_dependencies"):
            risk_factors.append("external_dependencies")
            likely_blockers.append(f"Reliance on external dependencies: {', '.join(spine_info['external_dependencies'])}")
            confidence -= 0.05

        # From LLM assessment
        if llm_assessment.get("risk_level") == "high":
            risk_factors.append("llm_high_risk")
            confidence -= 0.2
        elif llm_assessment.get("risk_level") == "medium":
            risk_factors.append("llm_medium_risk")
            confidence -= 0.1

        # From Failure Patterns
        if identified_failure_patterns:
            risk_factors.append("known_failure_pattern")
            likely_blockers.append(f"Identified failure patterns: {', '.join(identified_failure_patterns)}")
            confidence -= 0.1

        # From Delivery Fingerprints
        if project_risk_profile.get("risk_profile") == "drift-prone":
            risk_factors.append("project_drift_prone")
            recommended_changes.extend(project_risk_profile.get("recommended_controls", []))
            confidence -= 0.1

        # 3. Determine overall simulation decision and score contribution
        overall_risk_level = SimulationDecision.LOW_RISK
        if len(risk_factors) >= 3 or llm_assessment.get("risk_level") == "high":
            overall_risk_level = SimulationDecision.HIGH_RISK
        elif len(risk_factors) >= 1 or llm_assessment.get("risk_level") == "medium":
            overall_risk_level = SimulationDecision.MEDIUM_RISK

        score_contribution = 0.8 # Default for low risk
        if overall_risk_level == SimulationDecision.MEDIUM_RISK:
            score_contribution = 0.2
        elif overall_risk_level == SimulationDecision.HIGH_RISK:
            score_contribution = -0.5 # Negative contribution for high risk

        # Ensure confidence is within bounds
        confidence = max(0.0, min(1.0, confidence))

        return SimulationResult(
            simulation_id=f"sim-{uow.id}-{datetime.now().timestamp()}",
            decision=overall_risk_level,
            estimated_effort_hours=estimated_effort,
            likely_blockers=list(set(likely_blockers)), # Remove duplicates
            dependency_conflicts=spine_info.get("internal_dependencies", []), # Example
            historical_similarity_outcomes=historical_outcomes,
            confidence=confidence,
            recommended_changes=list(set(recommended_changes)), # Remove duplicates
            score_contribution=score_contribution,
            details={
                "risk_factors_identified": risk_factors,
                "llm_assessment": llm_assessment,
                "spine_info": spine_info,
                "historical_data": historical_outcomes,
                "failure_patterns": identified_failure_patterns,
                "project_risk_profile": project_risk_profile
            }
        )

# Example usage (for testing the SimulationEngine in isolation)
if __name__ == "__main__":
    import asyncio
    from newfang.models.uow import UnitOfWork, UoWState

    sim_engine = SimulationEngine()

    async def test_simulation():
        print("\n--- Simulation Engine Test Cases (Robust Logic) ---")

        # Test Case 1: Low Risk UoW
        uow_low_risk = UnitOfWork(
            id="sim-uow-001",
            objective="Fix typo on homepage",
            acceptance_criteria=["Typo 'welcom' changed to 'welcome'"],
            state=UoWState.DEFINED
        )
        context_low_risk = EvaluationContext(uow=uow_low_risk, target_state=UoWState.READY)
        context_low_risk.system_context["project_id"] = "stable-project"
        result_low_risk = await sim_engine.run_simulation(context_low_risk)
        print(f"\nSimulation for UoW {uow_low_risk.id}:")
        print(f"  Decision: {result_low_risk.decision}")
        print(f"  Estimated Effort: {result_low_risk.estimated_effort_hours}h")
        print(f"  Blockers: {result_low_risk.likely_blockers}")
        print(f"  Recommendations: {result_low_risk.recommended_changes}")
        print(f"  Confidence: {result_low_risk.confidence:.2f}")
        assert result_low_risk.decision == SimulationDecision.LOW_RISK

        # Test Case 2: Medium Risk UoW (complex objective, high AC count)
        uow_medium_risk = UnitOfWork(
            id="sim-uow-002",
            objective="Implement complex new reporting dashboard with multiple data sources",
            acceptance_criteria=[f"AC{i}" for i in range(7)], # More than 5 ACs
            state=UoWState.DEFINED
        )
        context_medium_risk = EvaluationContext(uow=uow_medium_risk, target_state=UoWState.READY)
        context_medium_risk.system_context["project_id"] = "stable-project"
        result_medium_risk = await sim_engine.run_simulation(context_medium_risk)
        print(f"\nSimulation for UoW {uow_medium_risk.id}:")
        print(f"  Decision: {result_medium_risk.decision}")
        print(f"  Estimated Effort: {result_medium_risk.estimated_effort_hours}h")
        print(f"  Blockers: {result_medium_risk.likely_blockers}")
        print(f"  Recommendations: {result_medium_risk.recommended_changes}")
        print(f"  Confidence: {result_medium_risk.confidence:.2f}")
        assert result_medium_risk.decision == SimulationDecision.MEDIUM_RISK

        # Test Case 3: High Risk UoW (ambiguous objective + high-risk dependency + project risk)
        uow_high_risk = UnitOfWork(
            id="sim-uow-003",
            objective="Ambiguous refactor of core payment module",
            acceptance_criteria=["Payments still work"],
            state=UoWState.DEFINED,
            dependencies=["high-risk-dependency"]
        )
        context_high_risk = EvaluationContext(uow=uow_high_risk, target_state=UoWState.READY)
        context_high_risk.system_context["project_id"] = "high-risk-project" # Simulate high-risk project
        result_high_risk = await sim_engine.run_simulation(context_high_risk)
        print(f"\nSimulation for UoW {uow_high_risk.id}:")
        print(f"  Decision: {result_high_risk.decision}")
        print(f"  Estimated Effort: {result_high_risk.estimated_effort_hours}h")
        print(f"  Blockers: {result_high_risk.likely_blockers}")
        print(f"  Recommendations: {result_high_risk.recommended_changes}")
        print(f"  Confidence: {result_high_risk.confidence:.2f}")
        assert result_high_risk.decision == SimulationDecision.HIGH_RISK

        # Test Case 4: UoW with identified failure pattern
        uow_failure_pattern = UnitOfWork(
            id="sim-uow-004",
            objective="Implement untested new feature",
            acceptance_criteria=["Feature works"],
            state=UoWState.DEFINED
        )
        context_failure_pattern = EvaluationContext(uow=uow_failure_pattern, target_state=UoWState.READY)
        context_failure_pattern.system_context["project_id"] = "stable-project"
        result_failure_pattern = await sim_engine.run_simulation(context_failure_pattern)
        print(f"\nSimulation for UoW {uow_failure_pattern.id}:")
        print(f"  Decision: {result_failure_pattern.decision}")
        print(f"  Blockers: {result_failure_pattern.likely_blockers}")
        assert "Lack of test coverage leading to regressions" in result_failure_pattern.likely_blockers
        assert result_failure_pattern.decision == SimulationDecision.MEDIUM_RISK # Due to failure pattern

    asyncio.run(test_simulation())