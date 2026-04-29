from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import os

from newfang.models.uow import UoWState
from newfang.lifecycle.engine import GateName, GateDecision

class OverrideOutcome(str, Enum):
    SUCCESS = "success" # The override led to a successful progression
    FAILURE = "failure" # The override led to issues later
    UNKNOWN = "unknown" # Outcome not yet determined

class OverrideEntry(BaseModel):
    """
    Represents a single entry in the Human Override Ledger.
    """
    uow_id: str = Field(..., description="ID of the Unit of Work that was overridden")
    gate: GateName = Field(..., description="The gate where the override occurred")
    original_decision: GateDecision = Field(..., description="The original decision from the Gate Evaluation Engine")
    failed_checks: List[str] = Field(default_factory=list, description="List of constraint/validation violations that led to the original decision")
    override_by: str = Field(..., description="Identifier of the user who performed the override")
    reason: str = Field(..., description="Justification provided by the user for the override")
    outcome: OverrideOutcome = Field(OverrideOutcome.UNKNOWN, description="The eventual outcome of the override (success/failure/unknown)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of the override event")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional details related to the override")

class OverrideLedger:
    """
    Manages the recording and retrieval of human override events.
    For a local-first system, this will use a simple file-based storage (JSONL).
    """
    def __init__(self, ledger_file_path: str = ".newfang/observability/override_ledger.jsonl"):
        self.ledger_file_path = ledger_file_path
        os.makedirs(os.path.dirname(ledger_file_path), exist_ok=True)
        # Ensure the file exists
        if not os.path.exists(self.ledger_file_path):
            with open(self.ledger_file_path, 'w') as f:
                pass # Create empty file

    def record_override(self, entry: OverrideEntry):
        """
        Records a new override entry to the ledger.
        """
        with open(self.ledger_file_path, 'a') as f:
            f.write(entry.json() + "\n")
        print(f"Override recorded for UoW {entry.uow_id} at gate {entry.gate} by {entry.override_by}")

    def get_overrides_for_uow(self, uow_id: str) -> List[OverrideEntry]:
        """
        Retrieves all override entries for a specific Unit of Work.
        """
        overrides: List[OverrideEntry] = []
        if not os.path.exists(self.ledger_file_path):
            return overrides

        with open(self.ledger_file_path, 'r') as f:
            for line in f:
                try:
                    entry_data = json.loads(line)
                    entry = OverrideEntry(**entry_data)
                    if entry.uow_id == uow_id:
                        overrides.append(entry)
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON from ledger: {e} in line: {line.strip()}")
        return overrides

    def get_all_overrides(self) -> List[OverrideEntry]:
        """
        Retrieves all override entries from the ledger.
        """
        overrides: List[OverrideEntry] = []
        if not os.path.exists(self.ledger_file_path):
            return overrides

        with open(self.ledger_file_path, 'r') as f:
            for line in f:
                try:
                    entry_data = json.loads(line)
                    overrides.append(OverrideEntry(**entry_data))
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON from ledger: {e} in line: {line.strip()}")
        return overrides

# Example usage
if __name__ == "__main__":
    ledger_path = ".newfang/observability/test_override_ledger.jsonl"
    # Clean up previous test ledger if it exists
    if os.path.exists(ledger_path):
        os.remove(ledger_path)

    override_ledger = OverrideLedger(ledger_file_path=ledger_path)

    # Record some overrides
    entry1 = OverrideEntry(
        uow_id="UOW-001",
        gate=GateName.DEFINED_TO_READY,
        original_decision=GateDecision.BLOCK,
        failed_checks=["UOW-AC-001: No acceptance criteria"],
        override_by="dev_user_1",
        reason="Product owner approved, will add AC later.",
        details={"jira_ticket": "JIRA-123"}
    )
    override_ledger.record_override(entry1)

    entry2 = OverrideEntry(
        uow_id="UOW-002",
        gate=GateName.READY_TO_IN_PROGRESS,
        original_decision=GateDecision.CONDITIONAL,
        failed_checks=["LLM-SIM-001: High risk simulation"],
        override_by="lead_dev_a",
        reason="Urgent hotfix, accepting risk.",
        outcome=OverrideOutcome.FAILURE # Example of updating outcome later
    )
    override_ledger.record_override(entry2)

    entry3 = OverrideEntry(
        uow_id="UOW-001",
        gate=GateName.READY_TO_IN_PROGRESS,
        original_decision=GateDecision.CONDITIONAL,
        failed_checks=["UOW-WARN-NAMING: Naming convention violation"],
        override_by="dev_user_1",
        reason="Minor warning, not critical for progress."
    )
    override_ledger.record_override(entry3)

    print("\n--- All Overrides ---")
    all_overrides = override_ledger.get_all_overrides()
    for entry in all_overrides:
        print(entry.json(indent=2))

    print("\n--- Overrides for UOW-001 ---")
    uow1_overrides = override_ledger.get_overrides_for_uow("UOW-001")
    for entry in uow1_overrides:
        print(entry.json(indent=2))

    # Clean up test ledger
    os.remove(ledger_path)
