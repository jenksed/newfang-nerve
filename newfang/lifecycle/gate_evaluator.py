from pydantic import BaseModel, Field
from typing import List, Dict, Any, Type, Optional
from abc import ABC, abstractmethod
from enum import Enum
import inspect
import sys # Needed for inspect.getmembers to work within __main__

from newfang.lifecycle.engine import EvaluationContext, GateName
from newfang.models.uow import UoWState

class ValidatorStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED" # If a validator's conditions for running are not met

class ValidatorResult(BaseModel):
    """
    The structured result returned by a single validator.
    """
    validator_id: str = Field(..., description="Unique identifier for the validator")
    name: str = Field(..., description="Human-readable name of the validator")
    status: ValidatorStatus
    message: str = Field(..., description="Summary message from the validator")
    score_contribution: float = Field(0.0, ge=-1.0, le=1.0, description="Contribution to the overall gate score (-1 for hard fail, 1 for strong pass)")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional detailed output (e.g., LLM response, specific findings)")
    
class BaseValidator(ABC):
    """
    Abstract base class for all validators.
    """
    @property
    @abstractmethod
    def id(self) -> str:
        """Unique identifier for the validator."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the validator."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Detailed description of what the validator checks."""
        pass

    @property
    @abstractmethod
    def target_gates(self) -> List[GateName]:
        """List of gates this validator applies to."""
        pass

    @abstractmethod
    async def validate(self, context: EvaluationContext) -> ValidatorResult:
        """
        Performs the validation logic.
        """
        pass

# --- Concrete Validator Implementations (Auditor Agent Checks) ---

class DeterministicAcceptanceCriteriaValidator(BaseValidator):
    """
    A deterministic validator that checks if acceptance criteria are present and non-empty.
    """
    id: str = "DET-AC-001"
    name: str = "Acceptance Criteria Presence Validator"
    description: str = "Checks if the UoW has at least one non-empty acceptance criterion."
    target_gates: List[GateName] = [GateName.DEFINED_TO_READY]

    async def validate(self, context: EvaluationContext) -> ValidatorResult:
        if not context.uow.acceptance_criteria:
            return ValidatorResult(
                validator_id=self.id,
                name=self.name,
                status=ValidatorStatus.FAIL,
                message="No acceptance criteria found for the UoW.",
                score_contribution=-0.5,
                details={"reason": "empty_acceptance_criteria"}
            )
        
        if all(not ac.strip() for ac in context.uow.acceptance_criteria):
            return ValidatorResult(
                validator_id=self.id,
                name=self.name,
                status=ValidatorStatus.FAIL,
                message="All acceptance criteria are empty or whitespace.",
                score_contribution=-0.7,
                details={"reason": "all_ac_empty"}
            )

        return ValidatorResult(
            validator_id=self.id,
            name=self.name,
            status=ValidatorStatus.PASS,
            message="Acceptance criteria are present and non-empty.",
            score_contribution=0.5
        )

class LLMAcceptanceCriteriaTestabilityValidator(BaseValidator):
    """
    An LLM-based validator that checks if acceptance criteria are testable.
    This is a placeholder for actual LLM interaction.
    """
    id: str = "LLM-AC-001"
    name: str = "LLM Acceptance Criteria Testability Validator"
    description: str = "Uses an LLM to assess if the UoW's acceptance criteria are clear, measurable, and testable."
    target_gates: List[GateName] = [GateName.DEFINED_TO_READY]

    async def validate(self, context: EvaluationContext) -> ValidatorResult:
        if not context.uow.acceptance_criteria:
            return ValidatorResult(
                validator_id=self.id,
                name=self.name,
                status=ValidatorStatus.SKIPPED,
                message="No acceptance criteria to evaluate for testability.",
                score_contribution=0.0
            )

        # --- Placeholder for actual LLM interaction ---
        # Simulate LLM response based on UoW objective and ACs
        llm_assessment = {
            "assessment": "The acceptance criteria appear clear and testable.",
            "testable_score": 0.9,
            "suggestions": []
        }
        
        if "ambiguous" in context.uow.objective.lower() or any("make it work" in ac.lower() for ac in context.uow.acceptance_criteria):
             llm_assessment["assessment"] = "Some acceptance criteria are vague or ambiguous, impacting testability."
             llm_assessment["testable_score"] = 0.3
             llm_assessment["suggestions"].append("Refine vague acceptance criteria to be specific and measurable.")
elif len(context.uow.acceptance_criteria) > 5:
            llm_assessment["assessment"] = "Many acceptance criteria, consider breaking down for better testability."
            llm_assessment["testable_score"] = 0.6
            llm_assessment["suggestions"].append("Break down complex UoW into smaller, more manageable parts.")

        score = (llm_assessment["testable_score"] * 2) - 1.0 # Normalize to -1.0 to 1.0
        status = ValidatorStatus.PASS if score >= 0 else ValidatorStatus.FAIL
        message = llm_assessment["assessment"]

        return ValidatorResult(
            validator_id=self.id,
            name=self.name,
            status=status,
            message=message,
            score_contribution=score,
            details={"llm_response": llm_assessment}
        )

class ObjectiveMeasurabilityValidator(BaseValidator):
    """
    An LLM-based validator that checks if the UoW's objective is measurable.
    """
    id: str = "LLM-OBJ-001"
    name: str = "LLM Objective Measurability Validator"
    description: str = "Uses an LLM to assess if the UoW's objective is clear, quantifiable, and measurable."
    target_gates: List[GateName] = [GateName.DEFINED_TO_READY]

    async def validate(self, context: EvaluationContext) -> ValidatorResult:
        if not context.uow.objective.strip():
            return ValidatorResult(
                validator_id=self.id,
                name=self.name,
                status=ValidatorStatus.FAIL,
                message="UoW objective is empty.",
                score_contribution=-0.8
            )
        
        # Simulate LLM assessment
        llm_assessment = {
            "assessment": "The objective appears measurable.",
            "measurable_score": 0.8,
            "suggestions": []
        }

        if "improve" in context.uow.objective.lower() and "by" not in context.uow.objective.lower():
            llm_assessment["assessment"] = "Objective is vague, lacks specific quantification."
            llm_assessment["measurable_score"] = 0.2
            llm_assessment["suggestions"].append("Add specific metrics and targets to the objective (e.g., 'improve X by Y%').")
elif "ambiguous" in context.uow.objective.lower():
            llm_assessment["assessment"] = "Objective is ambiguous and hard to measure."
            llm_assessment["measurable_score"] = 0.1
            llm_assessment["suggestions"].append("Clarify the objective to be specific and unambiguous.")

        score = (llm_assessment["measurable_score"] * 2) - 1.0 # Normalize to -1.0 to 1.0
        status = ValidatorStatus.PASS if score >= 0 else ValidatorStatus.FAIL
        message = llm_assessment["assessment"]

        return ValidatorResult(
            validator_id=self.id,
            name=self.name,
            status=status,
            message=message,
            score_contribution=score,
            details={"llm_response": llm_assessment}
        )

class LinkedCodePresenceValidator(BaseValidator):
    """
    A deterministic validator that checks if the UoW has linked code when moving to In Progress.
    """
    id: str = "DET-CODE-001"
    name: str = "Linked Code Presence Validator"
    description: str = "Checks if the UoW has linked code artifacts before starting implementation."
    target_gates: List[GateName] = [GateName.READY_TO_IN_PROGRESS]

    async def validate(self, context: EvaluationContext) -> ValidatorResult:
        if context.uow.state == UoWState.READY and context.target_state == UoWState.IN_PROGRESS:
            if not context.uow.linked_code:
                return ValidatorResult(
                    validator_id=self.id,
                    name=self.name,
                    status=ValidatorStatus.FAIL,
                    message="No linked code found for UoW moving to In Progress.",
                    score_contribution=-0.6,
                    details={"reason": "no_linked_code"}
                )
            if all(not lc.strip() for lc in context.uow.linked_code):
                return ValidatorResult(
                    validator_id=self.id,
                    name=self.name,
                    status=ValidatorStatus.FAIL,
                    message="All linked code entries are empty or whitespace.",
                    score_contribution=-0.7,
                    details={"reason": "empty_linked_code"}
                )
        return ValidatorResult(
            validator_id=self.id,
            name=self.name,
            status=ValidatorStatus.PASS,
            message="Linked code is present or not required for this transition.",
            score_contribution=0.3
        )

class SpineAlignmentValidator(BaseValidator):
    """
    A placeholder LLM-based validator that checks UoW alignment with the Project Spine.
    """
    id: str = "LLM-SPINE-001"
    name: str = "LLM Spine Alignment Validator"
    description: str = "Uses an LLM to assess if the UoW's objective and ACs align with the broader Project Spine (e.g., existing architecture, other UoWs)."
    target_gates: List[GateName] = [GateName.DEFINED_TO_READY, GateName.READY_TO_IN_PROGRESS]

    async def validate(self, context: EvaluationContext) -> ValidatorResult:
        # This would involve querying the actual Project Spine (context.current_project_spine)
        # and feeding relevant parts to an LLM along with the UoW details.
        
        # Simulate LLM assessment
        llm_assessment = {
            "assessment": "UoW appears to align well with the current project context.",
            "alignment_score": 0.9,
            "suggestions": []
        }

        if "refactor" in context.uow.objective.lower() and not context.uow.linked_code:
            llm_assessment["assessment"] = "Refactor UoW without linked code might indicate misalignment or missing information."
            llm_assessment["alignment_score"] = 0.4
            llm_assessment["suggestions"].append("Ensure refactor UoWs have clear linked code or architectural context.")

        score = (llm_assessment["alignment_score"] * 2) - 1.0 # Normalize to -1.0 to 1.0
        status = ValidatorStatus.PASS if score >= 0 else ValidatorStatus.FAIL
        message = llm_assessment["assessment"]

        return ValidatorResult(
            validator_id=self.id,
            name=self.name,
            status=status,
            message=message,
            score_contribution=score,
            details={"llm_response": llm_assessment}
        )


class GateEvaluator:
    """
    Manages and runs a collection of validators for a given gate.
    """
    def __init__(self):
        self.validators: Dict[str, BaseValidator] = {}
        self._discover_validators()

    def _discover_validators(self):
        """
        Discovers and registers all concrete implementations of BaseValidator
        in the current module or a specified plugin directory.
        """
        # Dynamically discover validators in the current module
        for name, obj in inspect.getmembers(sys.modules[__name__]):
            if inspect.isclass(obj) and issubclass(obj, BaseValidator) and obj is not BaseValidator:
                validator_instance = obj()
                self.validators[validator_instance.id] = validator_instance
        print(f"Discovered {len(self.validators)} validators.")

    async def evaluate_validators(self, context: EvaluationContext) -> List[ValidatorResult]:
        """
        Runs all relevant validators for the current gate transition.
        """
        results: List[ValidatorResult] = []
        target_gate = self._get_gate_name_from_transition(context.uow.state, context.target_state)

        for validator_id, validator in self.validators.items():
            if target_gate in validator.target_gates:
                try:
                    result = await validator.validate(context)
                    results.append(result)
                except Exception as e:
                    results.append(ValidatorResult(
                        validator_id=validator_id,
                        name=validator.name,
                        status=ValidatorStatus.ERROR,
                        message=f"Validator encountered an error: {e}",
                        score_contribution=0.0,
                        details={"error": str(e)}
                    ))
        return results

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
            raise ValueError(f"Unsupported UoW state transition: {from_state} -> {to_state}")

# Example usage (will be integrated into GateEvaluationEngine later)
if __name__ == "__main__":
    import asyncio
    
    # Create a dummy UoW
    from newfang.models.uow import UnitOfWork
    uow_test = UnitOfWork(
        id="test-uow-001",
        objective="Implement user authentication with OAuth",
        acceptance_criteria=[
            "Users can log in using Google OAuth.",
            "Users can log out.",
            "Session tokens are securely managed."
        ]
    )

    # Create an EvaluationContext
    context_test = EvaluationContext(uow=uow_test, target_state=UoWState.READY)

    # Initialize and run the GateEvaluator
    gate_evaluator = GateEvaluator()

    async def run_evaluation():
        print("\n--- Validator Results (Good UoW) ---")
        results = await gate_evaluator.evaluate_validators(context_test)
        for res in results:
            print(f"Validator: {res.name} ({res.validator_id})")
            print(f"  Status: {res.status}")
            print(f"  Message: {res.message}")
            print(f"  Score Contribution: {res.score_contribution}")
            if res.details:
                print(f"  Details: {res.details}")
            print("-" * 20)
        
        # Test with a UoW that should fail deterministic AC check
        uow_no_ac = UnitOfWork(
            id="test-uow-002",
            objective="Fix a minor bug",
            acceptance_criteria=[]
        )
        context_no_ac = EvaluationContext(uow=uow_no_ac, target_state=UoWState.READY)
        print("\n--- Validator Results (No AC) ---")
        results_no_ac = await gate_evaluator.evaluate_validators(context_no_ac)
        for res in results_no_ac:
            print(f"Validator: {res.name} ({res.validator_id})")
            print(f"  Status: {res.status}")
            print(f"  Message: {res.message}")
            print(f"  Score Contribution: {res.score_contribution}")
            print("-" * 20)

        # Test with a UoW that should trigger LLM issue for ambiguous objective
        uow_ambiguous_obj = UnitOfWork(
            id="test-uow-003",
            objective="Ambiguous feature implementation",
            acceptance_criteria=["Make it work", "Ensure good UX"]
        )
        context_ambiguous_obj = EvaluationContext(uow=uow_ambiguous_obj, target_state=UoWState.READY)
        print("\n--- Validator Results (Ambiguous Objective) ---")
        results_ambiguous_obj = await gate_evaluator.evaluate_validators(context_ambiguous_obj)
        for res in results_ambiguous_obj:
            print(f"Validator: {res.name} ({res.validator_id})")
            print(f"  Status: {res.status}")
            print(f"  Message: {res.message}")
            print(f"  Score Contribution: {res.score_contribution}")
            if res.details:
                print(f"  Details: {res.details}")
            print("-" * 20)

        # Test UoW moving to IN_PROGRESS without linked code
        uow_no_linked_code = UnitOfWork(
            id="test-uow-004",
            objective="Start coding new feature",
            acceptance_criteria=["AC1"],
            state=UoWState.READY,
            linked_code=[]
        )
        context_no_linked_code = EvaluationContext(uow=uow_no_linked_code, target_state=UoWState.IN_PROGRESS)
        print("\n--- Validator Results (No Linked Code for IN_PROGRESS) ---")
        results_no_linked_code = await gate_evaluator.evaluate_validators(context_no_linked_code)
        for res in results_no_linked_code:
            print(f"Validator: {res.name} ({res.validator_id})")
            print(f"  Status: {res.status}")
            print(f"  Message: {res.message}")
            print(f"  Score Contribution: {res.score_contribution}")
            print("-" * 20)

    asyncio.run(run_evaluation())