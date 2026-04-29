import asyncio
from pathlib import Path
from typing import List, Dict, Any
from newfang.models.project import ProjectState, DriftReport, DriftItem, DriftType
from newfang.utils.llm import LLMClient
from newfang.utils.config import AppConfig

class Reconciler:
    def __init__(self, config: AppConfig):
        self.config = config
        self.llm = LLMClient(base_url=config.endpoints.ollama, provider="ollama")

    async def reconcile(self, state: ProjectState, playbook_name: str = "reconcile-playbook.md") -> DriftReport:
        playbook_path = Path(state.root) / ".newfang" / "playbooks" / playbook_name
        playbook_content = playbook_path.read_text() if playbook_path.exists() else "Identify drift between docs and code."

        # Strategy: Sample a few key files for the audit
        # In a real app, we would use embeddings/index to find the right files
        doc_samples = self._read_files(state.root, [f.path for f in state.docs_files[:5]])
        code_samples = self._read_files(state.root, [f.path for f in state.code_files[:5]])

        prompt = self._build_prompt(playbook_content, doc_samples, code_samples)
        
        # Using the 'auditor' model from config
        response = await self.llm.chat(
            model=self.config.models.auditor,
            messages=[
                {"role": "system", "content": "You are the NewFang Audit Engine. Your job is to detect drift between documentation and implementation."},
                {"role": "user", "content": prompt}
            ]
        )

        return self._parse_response(state.name, response.content)

    def _read_files(self, root: str, paths: List[str]) -> str:
        content = ""
        for path in paths:
            full_path = Path(root) / path
            if full_path.exists() and full_path.is_file():
                content += f"\n--- FILE: {path} ---\n"
                # Limit content to avoid context overflow for now
                content += full_path.read_text()[:2000]
        return content

    def _build_prompt(self, playbook: str, docs: str, code: str) -> str:
        return f"""
FOLLOW THIS PLAYBOOK:
{playbook}

DOCUMENTATION EVIDENCE:
{docs}

CODE EVIDENCE:
{code}

TASK:
Identify any drift where the code does not match the documentation, or where the documentation is missing reality.
Return a structured report with:
1. Title
2. Description
3. Severity (High, Medium, Low)
4. Type (stale_docs, undocumented_code, missing_implementation)
"""

    def _parse_response(self, project_name: str, content: str) -> DriftReport:
        # For the MVP, we'll do a basic parsing of the LLM text.
        # Future: Use JSON output mode for perfect parsing.
        report = DriftReport(project_name=project_name)
        
        # Mocking a few items based on LLM output for demonstration if parsing fails
        # In real usage, we would use the content directly
        report.items.append(DriftItem(
            title="LLM Audit Feedback",
            description=content[:500] + "...",
            severity="Medium",
            type=DriftType.STALE_DOCS
        ))
        
        return report
