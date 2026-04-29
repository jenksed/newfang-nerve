from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime

from newfang.models.uow import UnitOfWork, UoWState
from newfang.lifecycle.constraint_engine import ConstraintEngine, ConstraintEnforcementLevel
from newfang.lifecycle.gate_evaluator import GateEvaluator, ValidatorStatus
from newfang.agents.simulator import SimulationEngine, SimulationDecision
from newfang.lifecycle.scoring_engine import ScoringEngine
from newfang.observability.override_ledger import OverrideLedger, OverrideEntry, OverrideOutcome # Import OverrideLedger

class GateName(str, Enum):
    """
    Defines the names of the gates in the UoW lifecycle.
    """
    DEFINED_TO_READY = "DefinedToReady"
    READY_TO_IN_PROGRESS = "ReadyToInProgress"
    IN_PROGRESS_TO_VALIDATION = "InProgressToValidation"
    VALIDATION_TO_DONE = "ValidationToDone"
    # Add other potential gates like REVERT_TO_READY, etc.

class GateDecision(str, Enum):
    """
    Represents the possible decisions a gate evaluation can return.
    """
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    CONDITIONAL = "CONDITIONAL" # e.g., requires human approval or further action

class GateResult(BaseModel):
    """
    The structured result of a single gate evaluation.
    """
    gate_name: GateName
    decision: GateDecision
    score: float = Field(..., ge=0.0, le=1.0, description="Overall score for the gate evaluation")
    violations: List[str] = Field(default_factory=list, description="List of constraint or validation violations")
    recommendations: List[str] = Field(default_factory=list, description="Suggestions for how to proceed if blocked or conditional")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional detailed output from validators or simulation")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class EvaluationContext(BaseModel):
    """
    Contextual information required for a gate evaluation.
    This encapsulates the UoW, the target state, and any other relevant system state.
    """
    uow: UnitOfWork = Field(..., description="The Unit of Work being evaluated")
    target_state: UoWState = Field(..., description="The state the UoW is attempting to transition to")
    current_project_spine: Optional[Dict[str, Any]] = Field(None, description="Snapshot of the relevant parts of the Project Spine")
    user_id: Optional[str] = Field(None, description="ID of the user initiating the transition, if any")
    system_context: Dict[str, Any] = Field(default_factory=dict, description="General system context (e.g., current policies, configurations)")

class GateEvaluationEngine:
    """
    The central engine responsible for orchestrating gate evaluations.
    It coordinates constraint checks, validator runs, and simulation.
    """
    def __init__(self, constraints_dir: str = ".newfang/constraints", 
                 scoring_config_path: str = ".newfang/config/scoring_config.yaml",
                 override_ledger_path: str = ".newfang/observability/override_ledger.jsonl"):
        self.constraint_engine = ConstraintEngine(constraints_dir=constraints_dir)
        self.gate_evaluator = GateEvaluator()
        self.simulation_engine = SimulationEngine()
        self.scoring_engine = ScoringEngine(scoring_config_path=scoring_config_path)
        self.override_ledger = OverrideLedger(ledger_file_path=override_ledger_path) # Initialize OverrideLedger

    async def evaluate_gate(self, context: EvaluationContext) -> GateResult:
        """
        Performs a comprehensive evaluation for a UoW attempting a state transition.
        """
        gate_name = self._get_gate_name(context.uow.state, context.target_state)
        
        # 1. Run Constraint Engine (Hard Rules)
        violated_constraints = self.constraint_engine.evaluate_constraints(context)
        hard_block_due_to_constraints = False
        for constraint in violated_constraints:
            if constraint.enforcement_level == ConstraintEnforcementLevel.HARD_BLOCK:
                hard_block_due_to_constraints = True
        
        if hard_block_due_to_constraints:
            # Collect all violations and recommendations for the hard block
            all_violations = [f"Constraint '{c.name}': {c.error_message}" for c in violated_constraints if c.enforcement_level == ConstraintEnforcementLevel.HARD_BLOCK]
            all_recommendations = [f"Address constraint '{c.name}': {c.description}" for c in violated_constraints if c.enforcement_level == ConstraintEnforcementLevel.HARD_BLOCK]
            return GateResult(
                gate_name=gate_name,
                decision=GateDecision.BLOCK,
                score=0.0, # Hard block, so score is 0
                violations=all_violations,
                recommendations=all_recommendations,
                details={"constraint_evaluation": [c.dict() for c in violated_constraints]}
            )

        # 2. Run Validators (Deterministic and LLM-based)
        validator_results = await self.gate_evaluator.evaluate_validators(context)
        
        # 3. Optionally run Simulation Engine
        simulation_results = None
        if gate_name in [GateName.DEFINED_TO_READY, GateName.READY_TO_IN_PROGRESS]: # Only simulate for relevant gates
            simulation_results = await self.simulation_engine.run_simulation(context)
            if simulation_results:
                context.uow.simulation_results = simulation_results.dict() # Store simulation results in UoW

        # 4. Compute overall score and decision using ScoringEngine
        overall_score, decision, all_violations, all_recommendations = self.scoring_engine.calculate_score_and_decision(
            context,
            violated_constraints, # Pass all violated constraints (including warnings)
            validator_results,
            simulation_results
        )

        # Emit structured events (for now, just print)
        print(f"Gate Evaluation Event: UoW {context.uow.id} attempting transition to {context.target_state}")
        print(f"  Decision: {decision}, Score: {overall_score:.2f}")
        if all_violations:
            print(f"  Violations: {'; '.join(all_violations)}")
        if all_recommendations:
            print(f"  Recommendations: {'; '.join(all_recommendations)}")

        return GateResult(
            gate_name=gate_name,
            decision=decision,
            score=overall_score,
            violations=all_violations,
            recommendations=all_recommendations,
            details={
                "constraint_evaluation": [c.dict() for c in violated_constraints],
                "validator_evaluation": [res.dict() for res in validator_results],
                "simulation_evaluation": simulation_results.dict() if simulation_results else None
            }
        )

    def handle_override(self, uow: UnitOfWork, gate_result: GateResult, override_by: str, reason: str) -> bool:
        """
        Records a human override for a gate decision.
        Returns True if the override was successfully recorded.
        """
        if gate_result.decision == GateDecision.ALLOW:
            print("Cannot override an ALLOW decision.")
            return False
        
        override_entry = OverrideEntry(
            uow_id=uow.id,
            gate=gate_result.gate_name,
            original_decision=gate_result.decision,
            failed_checks=gate_result.violations,
            override_by=override_by,
            reason=reason,
            details={"original_score": gate_result.score}
        )
        self.override_ledger.record_override(override_entry)
        print(f"Override for UoW {uow.id} at gate {gate_result.gate_name} recorded.")
        return True


    def _get_gate_name(self, from_state: UoWState, to_state: UoWState) -> GateName:
        """Helper to determine the gate name from state transition."""
        if from_state == UoWState.DEFINED and to_state == UoWState.READY:
            return GateName.DEFINED_TO_READY
        elif from_state == UoWState.READY and to_state == UoWState.IN_PROGRESS:
            return GateName.READY_TO_IN_PROGRESS
        elif from_state == UoWState.IN_PROGRESS and to_state == UoWState.VALIDATION:
            return GateName.IN_PROGRESS_TO_VALIDATION
        elif from_state == UoWState.VALIDATION and to_state == UoWState.DONE:
            return GateName.VALIDATION_TO_DONE
        else:
            raise ValueError(f"Unsupported UoW state transition: {from_state} -> {to_state}")

# Example usage for GateEvaluationEngine
if __name__ == "__main__":
    import asyncio
    import os
    
    # --- Setup: Ensure constraints and scoring config files exist for testing ---
    constraints_dir = ".newfang/constraints"
    os.makedirs(constraints_dir, exist_ok=True)
    constraint_content = """
- id: "UOW-AC-001"
  name: "Acceptance Criteria Must Exist"
  description: "A UoW cannot move to Ready if it has no acceptance criteria."
  target_gates: ["DefinedToReady"]
  condition_expression: "len(context.uow.acceptance_criteria) > 0"
  enforcement_level: "HARD_BLOCK"
  error_message: "UoW must have at least one acceptance criterion before moving to Ready."
- id: "UOW-OBJ-001"
  name: "Objective Must Not Be Empty"
  description: "A UoW must have a defined objective."
  target_gates: ["DefinedToReady", "ReadyToInProgress"]
  condition_expression: "len(context.uow.objective.strip()) > 0"
  enforcement_level: "HARD_BLOCK"
  error_message: "UoW objective cannot be empty."
- id: "UOW-WARN-NAMING"
  name: "UoW Naming Convention"
  description: "UoW objective should start with 'Implement' or 'Fix'."
  target_gates: ["DefinedToReady"]
  condition_expression: "context.uow.objective.startswith('Implement') or context.uow.objective.startswith('Fix')"
  enforcement_level: "WARNING"
  error_message: "UoW objective does not follow naming convention."
"""
    with open(os.path.join(constraints_dir, "basic_uow_constraints.yaml"), "w") as f:
        f.write(constraint_content)

    config_dir = ".newfang/config"
    os.makedirs(config_dir, exist_ok=True)
    scoring_config_path = os.path.join(config_dir, "scoring_config.yaml")
    scoring_config_content = """
default_validator_weight: 0.1
validator_weights:
  DET-AC-001: 0.2 # Higher weight for deterministic AC check
  LLM-AC-001: 0.3 # Higher weight for LLM AC testability
simulation_weight: 0.4 # Simulation has a significant weight
allow_threshold: 0.75
block_threshold: 0.25
"""
    with open(scoring_config_path, "w") as f:
        f.write(scoring_config_content)

    override_ledger_path = ".newfang/observability/test_override_ledger.jsonl"
    if os.path.exists(override_ledger_path):
        os.remove(override_ledger_path) # Clean up previous test ledger

    engine = GateEvaluationEngine(
        constraints_dir=constraints_dir, 
        scoring_config_path=scoring_config_path,
        override_ledger_path=override_ledger_path
    )

    async def run_full_evaluation_and_override_test():
        print("\n--- Full Gate Evaluation Test Cases with Override ---")

        # Test Case 1: UoW with no acceptance criteria (should be hard blocked by constraint)
        uow_no_ac = UnitOfWork(id="test-uow-001", objective="Implement feature X", acceptance_criteria=[])
        context_no_ac = EvaluationContext(uow=uow_no_ac, target_state=UoWState.READY)
        result_no_ac = await engine.evaluate_gate(context_no_ac)
        print(f"\nResult for UoW {uow_no_ac.id}: Decision={result_no_ac.decision}, Score={result_no_ac.score:.2f}")
        print(f"  Violations: {result_no_ac.violations}")
        print(f"  Recommendations: {result_no_ac.recommendations}")
        assert result_no_ac.decision == GateDecision.BLOCK
        assert "UOW-AC-001" in result_no_ac.violations[0]

        # Attempt to override a BLOCK decision
        print("\nAttempting to override BLOCK decision for UoW-001...")
        override_success = engine.handle_override(
            uow=uow_no_ac,
            gate_result=result_no_ac,
            override_by="test_user_override",
            reason="Product owner explicitly approved to proceed without AC for now."
        )
        assert override_success
        print(f"Override recorded: {override_success}")
        
        # Test Case 2: UoW with AC, but ambiguous objective (should be conditional/blocked by LLM validator and simulation)
        uow_ambiguous_obj = UnitOfWork(
            id="test-uow-002",
            objective="Ambiguous feature implementation",
            acceptance_criteria=["Make it work", "Ensure good UX"]
        )
        context_ambiguous_obj = EvaluationContext(uow=uow_ambiguous_obj, target_state=UoWState.READY)
        result_ambiguous_obj = await engine.evaluate_gate(context_ambiguous_obj)
        print(f"\nResult for UoW {uow_ambiguous_obj.id}: Decision={result_ambiguous_obj.decision}, Score={result_ambiguous_obj.score:.2f}")
        print(f"  Violations: {result_ambiguous_obj.violations}")
        print(f"  Recommendations: {result_ambiguous_obj.recommendations}")
        assert result_ambiguous_obj.decision in [GateDecision.BLOCK, GateDecision.CONDITIONAL]

        # Attempt to override a CONDITIONAL decision
        print("\nAttempting to override CONDITIONAL decision for UoW-002...")
        override_success_cond = engine.handle_override(
            uow=uow_ambiguous_obj,
            gate_result=result_ambiguous_obj,
            override_by="test_user_override_cond",
            reason="Team decided to accept the ambiguity and refine during development."
        )
        assert override_success_cond
        print(f"Override recorded: {override_success_cond}")

        # Test Case 3: UoW with good AC and objective (should allow)
        uow_good = UnitOfWork(
            id="test-uow-003",
            objective="Implement user authentication with OAuth",
            acceptance_criteria=[
                "Users can log in using Google OAuth.",
                "Users can log out.",
                "Session tokens are securely managed."
            ]
        )
        context_good = EvaluationContext(uow=uow_good, target_state=UoWState.READY)
        result_good = await engine.evaluate_gate(context_good)
        print(f"\nResult for UoW {uow_good.id}: Decision={result_good.decision}, Score={result_good.score:.2f}")
        print(f"  Violations: {result_good.violations}")
        print(f"  Recommendations: {result_good.recommendations}")
        assert result_good.decision == GateDecision.ALLOW
        assert not result_good.violations

        # Attempt to override an ALLOW decision (should fail)
        print("\nAttempting to override ALLOW decision for UoW-003...")
        override_fail = engine.handle_override(
            uow=uow_good,
            gate_result=result_good,
            override_by="test_user_override_fail",
            reason="Just testing."
        )
        assert not override_fail
        print(f"Override recorded: {override_fail}")

        # Verify overrides were recorded
        print("\n--- Overrides recorded in ledger ---")
        all_overrides = engine.override_ledger.get_all_overrides()
        for entry in all_overrides:
            print(f"UoW: {entry.uow_id}, Gate: {entry.gate}, Decision: {entry.original_decision}, Overridden by: {entry.override_by}")
        assert len(all_overrides) == 2 # Two successful overrides

    asyncio.run(run_full_evaluation_and_override_test())