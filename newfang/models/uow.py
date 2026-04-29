from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime

class UoWState(str, Enum):
    """
    Represents the possible states a Unit of Work can be in.
    """
    DEFINED = "Defined"
    READY = "Ready"
    IN_PROGRESS = "In Progress"
    VALIDATION = "Validation"
    DONE = "Done"

class UoWTransition(BaseModel):
    """
    Records a historical state transition for a Unit of Work.
    """
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    from_state: UoWState
    to_state: UoWState
    gated_by: Optional[str] = None  # Identifier of the gate that allowed/blocked the transition
    result: str  # e.g., "ALLOW", "BLOCK", "OVERRIDE"
    reason: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class UnitOfWork(BaseModel):
    """
    Represents a Unit of Work (UoW) as a first-class node in the Project Spine.
    """
    id: str = Field(..., description="Unique identifier for the Unit of Work")
    objective: str = Field(..., description="The business objective of this UoW")
    acceptance_criteria: List[str] = Field(default_factory=list, description="List of acceptance criteria")
    state: UoWState = Field(UoWState.DEFINED, description="Current state of the UoW")
    linked_code: List[str] = Field(default_factory=list, description="References to code artifacts (e.g., file paths, commit SHAs)")
    confidence_score: float = Field(0.0, ge=0.0, le=1.0, description="System's confidence in UoW's readiness/quality")
    drift_flags: List[str] = Field(default_factory=list, description="Flags indicating detected drift")
    state_transition_history: List[UoWTransition] = Field(default_factory=list, description="Historical record of state transitions")
    dependencies: List[str] = Field(default_factory=list, description="List of UoW IDs that this UoW depends on")
    simulation_results: Optional[Dict[str, Any]] = Field(None, description="Results from the latest simulation run")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata for the UoW")

    def add_transition(self, from_state: UoWState, to_state: UoWState, result: str, gated_by: Optional[str] = None, reason: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        Adds a new transition record to the UoW's history and updates its current state.
        """
        transition = UoWTransition(
            from_state=from_state,
            to_state=to_state,
            gated_by=gated_by,
            result=result,
            reason=reason,
            details=details
        )
        self.state_transition_history.append(transition)
        self.state = to_state

    def get_latest_state(self) -> UoWState:
        """
        Returns the current state of the UoW.
        """
        return self.state

    def get_state_regression_count(self) -> int:
        """
        Calculates the number of times the UoW has moved backward in its lifecycle.
        This is a simplified heuristic and might need refinement based on actual state graph.
        """
        regression_count = 0
        state_order = {state: i for i, state in enumerate(UoWState)}
        for i in range(1, len(self.state_transition_history)):
            prev_transition = self.state_transition_history[i-1]
            current_transition = self.state_transition_history[i]
            if state_order.get(current_transition.to_state, 0) < state_order.get(prev_transition.to_state, 0):
                regression_count += 1
        return regression_count
