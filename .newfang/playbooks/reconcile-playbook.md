# Playbook: Project Reconciliation

## Objective
Detect drift between the intended project state (documentation) and the current implementation (code).

## Outcomes
- A list of inconsistencies between README.md and src/.
- Identification of implemented features that are missing from the roadmap.
- Identification of planned features that have no code evidence.

## Verification Steps
1. Scan `docs/` for feature requirements.
2. Scan `src/` for matching implementation patterns.
3. Compare versions and dependencies mentioned in `PROJECT_BRIEF.md` vs `pyproject.toml`.
4. Report drift as "High", "Medium", or "Low" priority.
