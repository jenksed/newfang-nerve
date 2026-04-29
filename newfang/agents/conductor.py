from typing import Optional
from newfang.models.uow import UnitOfWork, UoWState
from newfang.lifecycle.engine import GateEvaluationEngine, EvaluationContext, GateDecision, GateResult, GateName
from newfang.core.spine import ProjectSpine, UoWNode, NodeType
import os

class ConductorAgent:
    """
    The Conductor Agent acts as the Lifecycle Orchestrator, managing UoW state transitions,
    enforcing gates, and coordinating with the GateEvaluationEngine.
    """
    def __init__(self, project_id: str, 
                 spine_storage_path: str = ".newfang/spine",
                 constraints_dir: str = ".newfang/constraints",
                 scoring_config_path: str = ".newfang/config/scoring_config.yaml",
                 override_ledger_path: str = ".newfang/observability/override_ledger.jsonl"):
        self.project_id = project_id
        self.spine = ProjectSpine(project_id=project_id, storage_path=spine_storage_path)
        self.gate_evaluation_engine = GateEvaluationEngine(
            constraints_dir=constraints_dir,
            scoring_config_path=scoring_config_path,
            override_ledger_path=override_ledger_path
        )

    async def request_uow_transition(self, uow_id: str, target_state: UoWState, user_id: Optional[str] = None) -> GateResult:
        """
        Requests a state transition for a Unit of Work and evaluates it against the gate.
        """
        uow_node = self.spine.get_uow_node(uow_id)
        if not uow_node:
            raise ValueError(f"Unit of Work with ID '{uow_id}' not found in Spine.")
        
        current_uow = uow_node.properties
        if current_uow.state == target_state:
            print(f"UoW {uow_id} is already in state {target_state}. No transition needed.")
            # Return a dummy ALLOW result
            gate_name = self.gate_evaluation_engine._get_gate_name(current_uow.state, target_state)
            return GateResult(gate_name=gate_name, decision=GateDecision.ALLOW, score=1.0, violations=[], recommendations=["UoW already in target state."])

        if not self._is_valid_transition(current_uow.state, target_state):
            raise ValueError(f"Invalid state transition requested: {current_uow.state} -> {target_state}")

        context = EvaluationContext(
            uow=current_uow,
            target_state=target_state,
            user_id=user_id,
            current_project_spine={"nodes": len(self.spine.graph.nodes), "edges": len(self.spine.graph.edges)} # Simplified spine context
        )

        gate_result = await self.gate_evaluation_engine.evaluate_gate(context)

        if gate_result.decision == GateDecision.ALLOW:
            print(f"Gate ALLOWED transition for UoW {uow_id} to {target_state}.")
            self._update_uow_state_in_spine(current_uow, target_state, gate_result, "ALLOW")
        else:
            print(f"Gate {gate_result.decision}ED transition for UoW {uow_id} to {target_state}.")
            print(f"  Violations: {gate_result.violations}")
            print(f"  Recommendations: {gate_result.recommendations}")
        
        return gate_result

    async def override_gate_decision(self, uow_id: str, target_state: UoWState, gate_result: GateResult, override_by: str, reason: str) -> bool:
        """
        Allows a user to override a BLOCK or CONDITIONAL gate decision.
        Records the override and then proceeds with the state transition.
        """
        uow_node = self.spine.get_uow_node(uow_id)
        if not uow_node:
            raise ValueError(f"Unit of Work with ID '{uow_id}' not found in Spine.")
        current_uow = uow_node.properties

        if gate_result.decision == GateDecision.ALLOW:
            print("Cannot override an ALLOW decision.")
            return False
        
        if not self.gate_evaluation_engine.handle_override(current_uow, gate_result, override_by, reason):
            return False # Override recording failed

        print(f"Override successful for UoW {uow_id} to {target_state}. Proceeding with transition.")
        self._update_uow_state_in_spine(current_uow, target_state, gate_result, "OVERRIDE", override_by)
        return True

    def _update_uow_state_in_spine(self, uow: UnitOfWork, new_state: UoWState, gate_result: GateResult, result_type: str, overridden_by: Optional[str] = None):
        """
        Updates the UoW's state in the Spine and records the transition history.
        """
        old_state = uow.state
        uow.add_transition(
            from_state=old_state,
            to_state=new_state,
            result=result_type,
            gated_by=gate_result.gate_name.value,
            reason=f"Decision: {gate_result.decision}, Score: {gate_result.score:.2f}",
            details={
                "violations": gate_result.violations,
                "recommendations": gate_result.recommendations,
                "overridden_by": overridden_by
            }
        )
        self.spine.update_uow_node(uow)
        print(f"UoW {uow.id} state updated in Spine: {old_state} -> {new_state}")

    def _is_valid_transition(self, current_state: UoWState, target_state: UoWState) -> bool:
        """
        Checks if the requested state transition is valid according to the state machine.
        """
        valid_transitions = {
            UoWState.DEFINED: [UoWState.READY],
            UoWState.READY: [UoWState.IN_PROGRESS],
            UoWState.IN_PROGRESS: [UoWState.VALIDATION, UoWState.READY], # Can revert to Ready
            UoWState.VALIDATION: [UoWState.DONE, UoWState.IN_PROGRESS], # Can revert to In Progress
            UoWState.DONE: [] # No transitions from Done (for now)
        }
        return target_state in valid_transitions.get(current_state, [])

# Example usage
if __name__ == "__main__":
    import asyncio
    import shutil
    
    project_id = "test_conductor_project"
    spine_storage_path = ".newfang/spine_conductor_test"
    constraints_dir = ".newfang/constraints"
    config_dir = ".newfang/config"
    scoring_config_path = os.path.join(config_dir, "scoring_config.yaml")
    override_ledger_path = ".newfang/observability/test_override_ledger.jsonl"

    # --- Setup: Ensure constraints and scoring config files exist for testing ---
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

    os.makedirs(config_dir, exist_ok=True)
    scoring_config_content = """
default_validator_weight: 0.1
validator_weights:
  DET-AC-001: 0.2
  LLM-AC-001: 0.3
simulation_weight: 0.4
allow_threshold: 0.75
block_threshold: 0.25
"""
    with open(scoring_config_path, "w") as f:
        f.write(scoring_config_content)

    # Clean up previous test data
    if os.path.exists(spine_storage_path):
        shutil.rmtree(spine_storage_path)
    if os.path.exists(override_ledger_path):
        os.remove(override_ledger_path)

    conductor = ConductorAgent(
        project_id=project_id,
        spine_storage_path=spine_storage_path,
        constraints_dir=constraints_dir,
        scoring_config_path=scoring_config_path,
        override_ledger_path=override_ledger_path
    )

    async def run_conductor_tests():
        # 1. Add a UoW to the Spine
        uow_initial = UnitOfWork(
            id="UOW-COND-001",
            objective="Implement user login feature",
            acceptance_criteria=["User can sign in", "User can sign up"],
            state=UoWState.DEFINED
        )
        conductor.spine.update_uow_node(uow_initial)
        print(f"\nInitial UoW state: {conductor.spine.get_uow_node('UOW-COND-001').properties.state}")

        # 2. Request transition: DEFINED -> READY (should ALLOW)
        print("\n--- Requesting UOW-COND-001: DEFINED -> READY (Expected: ALLOW) ---")
        gate_result_1 = await conductor.request_uow_transition("UOW-COND-001", UoWState.READY, user_id="test_user")
        print(f"Conductor Decision: {gate_result_1.decision}")
        assert gate_result_1.decision == GateDecision.ALLOW
        assert conductor.spine.get_uow_node("UOW-COND-001").properties.state == UoWState.READY

        # 3. Request transition: READY -> IN_PROGRESS (UoW with ambiguous objective, should be CONDITIONAL/BLOCK from simulation)
        uow_ambiguous = UnitOfWork(
            id="UOW-COND-002",
            objective="Ambiguous feature implementation",
            acceptance_criteria=["Make it work", "Ensure good UX"],
            state=UoWState.READY # Start in READY for this test
        )
        conductor.spine.update_uow_node(uow_ambiguous)
        print("\n--- Requesting UOW-COND-002: READY -> IN_PROGRESS (Expected: CONDITIONAL/BLOCK from simulation) ---")
        gate_result_2 = await conductor.request_uow_transition("UOW-COND-002", UoWState.IN_PROGRESS, user_id="test_user")
        print(f"Conductor Decision: {gate_result_2.decision}")
        assert gate_result_2.decision in [GateDecision.BLOCK, GateDecision.CONDITIONAL]
        assert conductor.spine.get_uow_node("UOW-COND-002").properties.state == UoWState.READY # State should not change

        # 4. Override the CONDITIONAL/BLOCK decision for UOW-COND-002
        print("\n--- Overriding decision for UOW-COND-002 ---")
        override_success = await conductor.override_gate_decision(
            "UOW-COND-002",
            UoWState.IN_PROGRESS,
            gate_result_2,
            "lead_dev_override",
            "Urgent, proceeding despite risks."
        )
        assert override_success
        assert conductor.spine.get_uow_node("UOW-COND-002").properties.state == UoWState.IN_PROGRESS

        # 5. Request invalid transition
        print("\n--- Requesting UOW-COND-001: READY -> DONE (Expected: ValueError) ---")
        try:
            await conductor.request_uow_transition("UOW-COND-001", UoWState.DONE, user_id="test_user")
            assert False, "Expected ValueError for invalid transition"
        except ValueError as e:
            print(f"Caught expected error: {e}")
            assert "Invalid state transition requested" in str(e)

        # Verify override ledger
        print("\n--- Overrides in Ledger ---")
        all_overrides = conductor.gate_evaluation_engine.override_ledger.get_all_overrides()
        assert len(all_overrides) == 1
        print(all_overrides[0].json(indent=2))

    asyncio.run(run_conductor_tests())

    # Clean up test data
    shutil.rmtree(spine_storage_path)
    os.remove(override_ledger_path)
