from pydantic import BaseModel, Field
from typing import List, Dict, Any, Callable, Optional
import yaml
import os
from newfang.lifecycle.engine import GateName, EvaluationContext

class ConstraintEnforcementLevel(str, Enum):
    HARD_BLOCK = "HARD_BLOCK"
    WARNING = "WARNING"
    # Future: SOFT_BLOCK (requires override), INFO

class Constraint(BaseModel):
    """
    Represents a single hard constraint that must be met for a UoW transition.
    """
    id: str = Field(..., description="Unique identifier for the constraint")
    name: str = Field(..., description="Human-readable name of the constraint")
    description: str = Field(..., description="Detailed description of the constraint")
    target_gates: List[GateName] = Field(..., description="List of gates this constraint applies to")
    condition_expression: str = Field(..., description="Python expression to evaluate the constraint. Must return a boolean.")
    enforcement_level: ConstraintEnforcementLevel = Field(ConstraintEnforcementLevel.HARD_BLOCK, description="How strictly this constraint is enforced")
    error_message: str = Field(..., description="Message to display if the constraint is violated")

class ConstraintEngine:
    """
    Manages and evaluates hard constraints against an EvaluationContext.
    """
    def __init__(self, constraints_dir: str = ".newfang/constraints"):
        self.constraints_dir = constraints_dir
        self.constraints: List[Constraint] = []
        self._load_constraints()

    def _load_constraints(self):
        """
        Loads constraints from YAML files in the specified directory.
        """
        self.constraints = []
        if not os.path.exists(self.constraints_dir):
            os.makedirs(self.constraints_dir) # Ensure directory exists
            return

        for filename in os.listdir(self.constraints_dir):
            if filename.endswith((".yaml", ".yml")):
                filepath = os.path.join(self.constraints_dir, filename)
                with open(filepath, 'r') as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, list):
                        for item in data:
                            self.constraints.append(Constraint(**item))
                    else:
                        self.constraints.append(Constraint(**data))
        print(f"Loaded {len(self.constraints)} constraints from {self.constraints_dir}")

    def evaluate_constraints(self, context: EvaluationContext) -> List[Constraint]:
        """
        Evaluates all relevant constraints for the given EvaluationContext.
        Returns a list of violated constraints.
        """
        violated_constraints: List[Constraint] = []
        target_gate = self._get_gate_name_from_transition(context.uow.state, context.target_state)

        for constraint in self.constraints:
            if target_gate in constraint.target_gates:
                try:
                    # Prepare the execution environment for the condition_expression
                    # This is a simplified approach. In a real system, you'd want
                    # a more secure sandboxed environment (e.g., restricted globals,
                    # limited built-ins) to prevent arbitrary code execution.
                    # For now, we'll expose 'context' directly.
                    local_vars = {"context": context}
                    
                    # Evaluate the condition. If it's False, the constraint is violated.
                    if not eval(constraint.condition_expression, {}, local_vars):
                        violated_constraints.append(constraint)
                except Exception as e:
                    print(f"Error evaluating constraint '{constraint.id}': {e}")
                    # Optionally, treat evaluation errors as violations or log them
                    violated_constraints.append(Constraint(
                        id=f"{constraint.id}-eval-error",
                        name=f"{constraint.name} (Evaluation Error)",
                        description=f"Constraint evaluation failed: {e}",
                        target_gates=constraint.target_gates,
                        condition_expression=constraint.condition_expression,
                        enforcement_level=ConstraintEnforcementLevel.HARD_BLOCK,
                        error_message=f"Constraint evaluation failed: {e}"
                    ))
        return violated_constraints

    def _get_gate_name_from_transition(self, from_state: UoWState, to_state: UoWState) -> GateName:
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
            # This should ideally be caught earlier or handled as an invalid transition
            raise ValueError(f"Unsupported UoW state transition: {from_state} -> {to_state}")

# Example usage (will be integrated into GateEvaluationEngine later)
if __name__ == "__main__":
    # Create a dummy constraint file
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
"""
    os.makedirs(".newfang/constraints", exist_ok=True)
    with open(".newfang/constraints/basic_uow_constraints.yaml", "w") as f:
        f.write(constraint_content)

    constraint_engine = ConstraintEngine()

    # Test Case 1: UoW with no acceptance criteria, trying to go Defined -> Ready
    from newfang.models.uow import UnitOfWork
    from newfang.lifecycle.engine import EvaluationContext

    uow_bad = UnitOfWork(id="test-uow-001", objective="Implement feature X", acceptance_criteria=[])
    context_bad = EvaluationContext(uow=uow_bad, target_state=UoWState.READY)
    violations_bad = constraint_engine.evaluate_constraints(context_bad)
    print("\n--- Test Case 1 (Violations Expected) ---")
    for v in violations_bad:
        print(f"VIOLATION: {v.name} - {v.error_message}")
    assert len(violations_bad) > 0

    # Test Case 2: UoW with acceptance criteria, trying to go Defined -> Ready
    uow_good = UnitOfWork(id="test-uow-002", objective="Implement feature Y", acceptance_criteria=["AC1", "AC2"])
    context_good = EvaluationContext(uow=uow_good, target_state=UoWState.READY)
    violations_good = constraint_engine.evaluate_constraints(context_good)
    print("\n--- Test Case 2 (No Violations Expected) ---")
    for v in violations_good:
        print(f"VIOLATION: {v.name} - {v.error_message}")
    assert len(violations_good) == 0

    # Test Case 3: UoW with empty objective
    uow_empty_obj = UnitOfWork(id="test-uow-003", objective="   ", acceptance_criteria=["AC1"])
    context_empty_obj = EvaluationContext(uow=uow_empty_obj, target_state=UoWState.READY)
    violations_empty_obj = constraint_engine.evaluate_constraints(context_empty_obj)
    print("\n--- Test Case 3 (Violations Expected for Empty Objective) ---")
    for v in violations_empty_obj:
        print(f"VIOLATION: {v.name} - {v.error_message}")
    assert len(violations_empty_obj) > 0
