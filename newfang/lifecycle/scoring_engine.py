from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import yaml
import os

from newfang.lifecycle.engine import EvaluationContext, GateDecision, GateName
from newfang.lifecycle.constraint_engine import Constraint, ConstraintEnforcementLevel
from newfang.lifecycle.gate_evaluator import ValidatorResult, ValidatorStatus
from newfang.agents.simulator import SimulationResult, SimulationDecision

class ScoringConfig(BaseModel):
    """
    Configuration for the scoring model, including weights and decision thresholds.
    """
    default_validator_weight: float = Field(0.1, description="Default weight for validators if not specified individually")
    validator_weights: Dict[str, float] = Field(default_factory=dict, description="Specific weights for validators by ID")
    simulation_weight: float = Field(0.3, description="Weight for the simulation engine's score contribution")
    
    # Thresholds for overall gate decision
    allow_threshold: float = Field(0.7, description="Overall score >= this allows transition")
    block_threshold: float = Field(0.3, description="Overall score <= this blocks transition")
    # Scores between block_threshold and allow_threshold result in CONDITIONAL

class ScoringEngine:
    """
    Calculates the overall gate score and decision based on constraint, validator,
    and simulation results, using a configurable scoring model.
    """
    def __init__(self, scoring_config_path: str = ".newfang/config/scoring_config.yaml"):
        self.config: ScoringConfig = self._load_scoring_config(scoring_config_path)

    def _load_scoring_config(self, path: str) -> ScoringConfig:
        """
        Loads scoring configuration from a YAML file.
        If file doesn't exist, creates a default one.
        """
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            print(f"Scoring config not found at {path}. Creating default config.")
            default_config = ScoringConfig().dict()
            with open(path, 'w') as f:
                yaml.safe_dump(default_config, f)
            return ScoringConfig(**default_config)
        else:
            with open(path, 'r') as f:
                config_data = yaml.safe_load(f)
            return ScoringConfig(**config_data)

    def calculate_score_and_decision(
        self,
        context: EvaluationContext,
        violated_constraints: List[Constraint],
        validator_results: List[ValidatorResult],
        simulation_result: Optional[SimulationResult]
    ) -> (float, GateDecision, List[str], List[str]):
        """
        Calculates the overall gate score and determines the final decision.
        Returns (overall_score, decision, all_violations, all_recommendations).
        """
        all_violations: List[str] = []
        all_recommendations: List[str] = []
        total_weighted_score = 0.0
        max_possible_weighted_score = 0.0 # For normalization

        # 1. Process Constraints (Hard Blocks handled by GateEvaluationEngine, here for warnings)
        for constraint in violated_constraints:
            if constraint.enforcement_level == ConstraintEnforcementLevel.WARNING:
                all_violations.append(f"Warning Constraint '{constraint.name}': {constraint.error_message}")
                all_recommendations.append(f"Consider addressing warning constraint '{constraint.name}'.")
            # Hard blocks are assumed to have already caused an early exit in GateEvaluationEngine

        # 2. Process Validators
        for res in validator_results:
            weight = self.config.validator_weights.get(res.validator_id, self.config.default_validator_weight)
            
            # Validators contribute to score based on their status and score_contribution
            if res.status == ValidatorStatus.FAIL:
                all_violations.append(f"Validation '{res.name}': {res.message}")
                all_recommendations.append(f"Review validator '{res.name}' findings: {res.message}")
                total_weighted_score += weight * res.score_contribution # Negative contribution
            elif res.status == ValidatorStatus.ERROR:
                all_violations.append(f"Validator Error '{res.name}': {res.message}")
                all_recommendations.append(f"Investigate error in validator '{res.name}'.")
                total_weighted_score += weight * -1.0 # Treat error as a strong negative
            elif res.status == ValidatorStatus.PASS:
                total_weighted_score += weight * res.score_contribution # Positive contribution
            # SKIPPED validators don't contribute to score

            max_possible_weighted_score += weight * 1.0 # Max possible positive contribution

            if res.details:
                all_recommendations.extend(res.details.get("suggestions", []))

        # 3. Process Simulation Results
        if simulation_result:
            weight = self.config.simulation_weight
            total_weighted_score += weight * simulation_result.score_contribution
            max_possible_weighted_score += weight * 1.0

            if simulation_result.decision == SimulationDecision.HIGH_RISK:
                all_violations.append("Simulation detected high execution risk.")
                all_recommendations.append("Review simulation results for potential blockers and recommended changes.")
                all_recommendations.extend(simulation_result.recommended_changes)
            
            if simulation_result.likely_blockers:
                all_violations.extend([f"Simulation identified potential blocker: {b}" for b in simulation_result.likely_blockers])

        # 4. Calculate Overall Score (normalize to 0-1)
        # Avoid division by zero if no components contributed
        if max_possible_weighted_score > 0:
            overall_score = max(0.0, min(1.0, (total_weighted_score + max_possible_weighted_score) / (2 * max_possible_weighted_score)))
        else:
            overall_score = 1.0 # Default to allow if no checks were performed

        # 5. Determine Decision
        decision = GateDecision.ALLOW
        if overall_score <= self.config.block_threshold:
            decision = GateDecision.BLOCK
        elif overall_score < self.config.allow_threshold or all_violations:
            # If there are any violations (even if score is above block_threshold), it's at least CONDITIONAL
            decision = GateDecision.CONDITIONAL
        
        # If simulation explicitly says high risk, and it's not already blocked, make it conditional
        if simulation_result and simulation_result.decision == SimulationDecision.HIGH_RISK and decision == GateDecision.ALLOW:
            decision = GateDecision.CONDITIONAL


        return overall_score, decision, all_violations, all_recommendations

# Example usage for ScoringEngine
if __name__ == "__main__":
    # Create a dummy scoring config file
    config_dir = ".newfang/config"
    os.makedirs(config_dir, exist_ok=True)
    scoring_config_content = """
default_validator_weight: 0.1
validator_weights:
  DET-AC-001: 0.2 # Higher weight for deterministic AC check
  LLM-AC-001: 0.3 # Higher weight for LLM AC testability
simulation_weight: 0.4 # Simulation has a significant weight
allow_threshold: 0.75
block_threshold: 0.25
"""
    scoring_config_path = os.path.join(config_dir, "scoring_config.yaml")
    with open(scoring_config_path, "w") as f:
        f.write(scoring_config_content)

    scoring_engine = ScoringEngine(scoring_config_path=scoring_config_path)

    # Dummy data for testing
    from newfang.models.uow import UnitOfWork, UoWState
    from newfang.lifecycle.engine import EvaluationContext
    from newfang.lifecycle.constraint_engine import Constraint
    from newfang.lifecycle.gate_evaluator import ValidatorResult

    uow_dummy = UnitOfWork(id="test-uow-score", objective="Test scoring", acceptance_criteria=["AC1"])
    context_dummy = EvaluationContext(uow=uow_dummy, target_state=UoWState.READY)

    # Test Case 1: All good
    print("\n--- Scoring Test Case 1: All Good ---")
    violated_constraints_1 = []
    validator_results_1 = [
        ValidatorResult(validator_id="DET-AC-001", name="AC Present", status=ValidatorStatus.PASS, message="AC present", score_contribution=1.0),
        ValidatorResult(validator_id="LLM-AC-001", name="AC Testable", status=ValidatorStatus.PASS, message="AC testable", score_contribution=0.8)
    ]
    simulation_result_1 = SimulationResult(
        simulation_id="sim-1", decision=SimulationDecision.LOW_RISK, confidence=0.9, score_contribution=1.0
    )
    score, decision, violations, recommendations = scoring_engine.calculate_score_and_decision(
        context_dummy, violated_constraints_1, validator_results_1, simulation_result_1
    )
    print(f"Score: {score:.2f}, Decision: {decision}")
    print(f"Violations: {violations}")
    print(f"Recommendations: {recommendations}")
    assert decision == GateDecision.ALLOW

    # Test Case 2: Some validator fails
    print("\n--- Scoring Test Case 2: Validator Fails ---")
    violated_constraints_2 = []
    validator_results_2 = [
        ValidatorResult(validator_id="DET-AC-001", name="AC Present", status=ValidatorStatus.PASS, message="AC present", score_contribution=1.0),
        ValidatorResult(validator_id="LLM-AC-001", name="AC Testable", status=ValidatorStatus.FAIL, message="AC not testable", score_contribution=-0.5)
    ]
    simulation_result_2 = SimulationResult(
        simulation_id="sim-2", decision=SimulationDecision.LOW_RISK, confidence=0.9, score_contribution=1.0
    )
    score, decision, violations, recommendations = scoring_engine.calculate_score_and_decision(
        context_dummy, violated_constraints_2, validator_results_2, simulation_result_2
    )
    print(f"Score: {score:.2f}, Decision: {decision}")
    print(f"Violations: {violations}")
    print(f"Recommendations: {recommendations}")
    assert decision == GateDecision.CONDITIONAL # Because of validator failure

    # Test Case 3: High Risk Simulation
    print("\n--- Scoring Test Case 3: High Risk Simulation ---")
    violated_constraints_3 = []
    validator_results_3 = [
        ValidatorResult(validator_id="DET-AC-001", name="AC Present", status=ValidatorStatus.PASS, message="AC present", score_contribution=1.0),
        ValidatorResult(validator_id="LLM-AC-001", name="AC Testable", status=ValidatorStatus.PASS, message="AC testable", score_contribution=0.8)
    ]
    simulation_result_3 = SimulationResult(
        simulation_id="sim-3", decision=SimulationDecision.HIGH_RISK, confidence=0.5, score_contribution=-1.0,
        likely_blockers=["Complex dependency"], recommended_changes=["Split UoW"]
    )
    score, decision, violations, recommendations = scoring_engine.calculate_score_and_decision(
        context_dummy, violated_constraints_3, validator_results_3, simulation_result_3
    )
    print(f"Score: {score:.2f}, Decision: {decision}")
    print(f"Violations: {violations}")
    print(f"Recommendations: {recommendations}")
    assert decision == GateDecision.BLOCK # Because of high risk simulation and low score

    # Test Case 4: Constraint Warning
    print("\n--- Scoring Test Case 4: Constraint Warning ---")
    violated_constraints_4 = [
        Constraint(id="WARN-001", name="Naming Convention", description="UoW name should follow convention",
                   target_gates=[GateName.DEFINED_TO_READY], condition_expression="False",
                   enforcement_level=ConstraintEnforcementLevel.WARNING, error_message="Name does not follow convention")
    ]
    validator_results_4 = [
        ValidatorResult(validator_id="DET-AC-001", name="AC Present", status=ValidatorStatus.PASS, message="AC present", score_contribution=1.0),
    ]
    simulation_result_4 = SimulationResult(
        simulation_id="sim-4", decision=SimulationDecision.LOW_RISK, confidence=0.9, score_contribution=1.0
    )
    score, decision, violations, recommendations = scoring_engine.calculate_score_and_decision(
        context_dummy, violated_constraints_4, validator_results_4, simulation_result_4
    )
    print(f"Score: {score:.2f}, Decision: {decision}")
    print(f"Violations: {violations}")
    print(f"Recommendations: {recommendations}")
    assert decision == GateDecision.CONDITIONAL # Because of warning constraint
    assert "Warning Constraint 'Naming Convention'" in violations
