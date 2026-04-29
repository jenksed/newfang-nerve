## 0. Core Primitive: Project Spine (Extended)
**Concept:** A continuously reconciled, executable graph of code, intent, and state. This is the central anchor for everything, now extended to include "Units of Work."
*   **[x] Design and Implement Project Spine Data Structures and Persistence**

### Structure
*   **Nodes:**
    *   Code (files, classes, functions)
    *   Documentation (markdown, specs)
    *   **Units of Work (UoW):** First-class nodes representing executable tasks (e.g., tickets, features).
    *   Decisions (ADR-style artifacts)
*   **Edges:**
    *   Imports / dependencies
    *   Ownership
    *   Spec ↔ Code alignment
    *   Temporal changes (git history)
    *   **UoW State Transitions:** Links between UoW states, including history and directionality rules.
    *   **Cross-UoW Dependencies:** Graph of UoW relationships, blocking, and parallelization.

### Units of Work (UoW) Schema (Critical)
```json
{
  "id": "UOW-123",
  "objective": "Increase checkout conversion by 10%",
  "acceptance_criteria": [...],
  "state": "Defined", // e.g., Defined, Ready, In Progress, Validation, Done
  "linked_code": [...],
  "confidence_score": 0.87,
  "drift_flags": [],
  "state_transition_history": [
    {"timestamp": "...", "from": "...", "to": "...", "gated_by": "...", "result": "..."}
  ],
  "dependencies": ["UOW-456"], // Cross-UoW Dependency Intelligence
  "simulation_results": { ... } // Simulation Mode
}
```
**Why this matters:** Enables tracking drift at the *unit level*, scoring delivery integrity, and gating execution.

---

## Layer 1: Data (Ingestion + Memory System)

### 1.1 Scanner → Spine Builder
*   **Function:** Ingests repository data and constructs the Project Spine, now including UoW and their dependencies.
*   **[x] Implement Initial Scanner and Spine Builder**
*   **FastAPI Service:**
    *   `POST /scan`: Initiates a scan.
    *   `POST /rescan`: Initiates a rescan.
    *   `GET /spine/{project_id}`: Retrieves the current Spine for a project.
*   **Pipeline:** Repo → File Parser → AST Extractor → Dependency Mapper → UoW Ingester → Spine Graph

### 1.2 Hybrid Memory Model (The Real Differentiator)
*   **Concept:** Multi-modal retrieval across semantic + structural + temporal axes, not just "RAG over a repo."
*   **Memory Layers:**
    *   **Hot:** Active files, recent commits, active UoW (Storage: In-memory + fast vector)
    *   **Warm:** Stable modules, docs, historical UoW (Storage: Vector DB - Qdrant/Chroma)
    *   **Cold:** Historical decisions, archived UoW, Failure Patterns (Storage: Object storage + indexed summaries)
*   **Indexing Strategy:**
    *   **Semantic Index:** Chunked docs + code, embeddings per function/module, UoW descriptions (Used for: chat, spec generation, UoW validation).
    *   **Structural Index:** AST relationships, call graphs, dependency trees, UoW linkages, Cross-UoW dependencies (Storage: Graph DB or in-memory graph).
    *   **Temporal Index:** Git commits → diff embeddings, change frequency heatmaps, UoW state transition history, Drift Trajectory.
*   **Retrieval Fusion:** When a query hits, combine Semantic Search (top-k) + Graph Traversal (neighbors) + Temporal Filter (recent changes) → Context Pack.

---

## Layer 2: Intelligence (Agent System + Control Plane)

### 2.1 The Conductor Agent: Lifecycle Orchestrator
*   **Concept:** Evolves from a task router to a **Lifecycle Orchestrator**, enforcing state transitions and maintaining delivery invariants.
*   **[x] Implement Conductor Agent (Basic Orchestration)**
*   **Responsibilities:** Enforce state transitions, Trigger agents at gates, Maintain delivery invariants, Log violations, Task routing, Memory scoping, Agent coordination, Conflict resolution, Confidence scoring, **Orchestrate Simulation Mode**, **Manage Constraint Engine**, **Log Human Overrides**.
*   **Control Loop:** Trigger → Conductor → Decompose Task / Evaluate Gate → Assign to Agents → Collect Results → Resolve Conflicts → Update Spine → Log + Score.

### 2.2 Agent Roles (Now Predictive & Enforcement-Focused)
*   **Auditor (Real-Time Gatekeeper):** Evolves from an observer to an **enforcement mechanism**. Instead of "This is wrong," it becomes "You cannot proceed." Plugs into the State Transition Engine.
    *   Detects drift (code vs docs vs intent), flags inconsistencies.
    *   **[x] Integrate Auditor Agent with Gate Evaluation Engine (Advanced Validators)**
    *   **New:** Validates UoW completeness, rejects vague work, forces clarity *before* execution.
    *   **New:** Monitors drift in real-time, blocks invalid transitions.
    *   **New:** Contributes to "Spec → Reality Drift Delta" tracking.
    *   **New:** Triggers "Auto-Scope Correction" proposals.
*   **Architect:** Infers system design, maps integrations + data models, contributes to UoW dependency intelligence.
*   **Spec Writer:** Generates PRDs, user stories, anchored to real code evidence, ensures objective clarity.
*   **Refactor Agent:** Suggests structural improvements, links to drift + complexity.
*   **New Agent: Simulator Agent:** Executes "Simulation Mode" for UoW, predicting effort, conflicts, and risks.
    *   **[x] Implement Robust Simulation Engine Logic**

---

## Layer 3: Lifecycle Control Layer (AI-DLC Inspired)
**Concept:** A first-class layer that manages the Delivery Lifecycle Engine (DLE). Every unit of work moves through defined states, and movement is **gated, not implied**. This is a **state machine with enforced invariants**.

### Core Concept: Gated Transitions
Every unit of work moves through states (e.g., `Defined → Ready → In Progress → Validation → Done`).
**Critically: Movement is gated, not implied.**

### Each Transition Requires:
*   Required artifacts
*   AI validation (via Auditor and other agents)
*   Human approval (optional but enforceable)
*   **Constraint Engine Check:** Non-negotiable system constraints.

### Example: Gate: Defined → Ready
*   **Constraints:** "No UoW enters Defined without objective."
*   **Requirements:** Business objective (structured), Acceptance criteria (pre-written), Scope boundaries.
*   **AI Checks (Auditor):** Are acceptance criteria testable? Is objective measurable? Is scope ambiguous?
*   **Simulation Mode:** Run simulation to assess risk before moving to Ready.
*   **Result:** If fail: **block transition**.

### Example: Gate: In Progress → Validation
*   **Constraints:** "No UoW enters Validation without linked code."
*   **Requirements:** Code linked to task, Tests present, Spec alignment.
*   **AI Checks (Auditor):** Does implementation match acceptance criteria? Any drift from defined scope?
*   **Auto-Scope Correction:** Propose adjustments if significant drift detected.
*   **Result:** If fail: **block transition**.

### Formalized “Backward Movement” Detection
*   **Added to Spine:** State transition history, Transition directionality rules.
*   **Detection Logic:** `if current_state < previous_state: flag = "regression"`
*   **Use Cases:** Scorecard penalty, Risk prediction, Workflow blocking.

### Constraint Engine (Hard Rules Layer)
*   **Concept:** Defines non-negotiable system constraints that must be met for state transitions.
*   **[x] Designed and Implemented**
*   **Examples:** "No UoW enters In Progress without acceptance criteria," "No merge without linked UoW," "No Done state without validation evidence."
*   **Implementation:** Configurable rules (`.newfang/constraints/`).

---

## Layer 4: Execution (Deterministic Workflows)
*   **Concept:** Workflows are programs, not prompts, now operating within the DLE and leveraging UoW dependency intelligence.
*   **Characteristics:** Versioned, Repo-native (`.newfang/workflows/`), Executable without chat.
*   **Integration with DLE:** Workflows can trigger UoW state transitions, and their execution can be gated by the DLE.
*   **Cross-UoW Dependency Intelligence:** Workflows can leverage the UoW dependency graph for smarter scheduling and forecasting.

---

## Layer 5: Interface (FastAPI + Desktop Runtime)

### 5.1 FastAPI Core
*   **API Domains:** `/chat`, `/workflows`, `/agents`, `/spine`, `/memory`, `/observability`, `/lifecycle`, `/simulation`, `/constraints`.
*   **WebSocket Chat:** `/ws/chat` (Chat becomes a query interface into the Spine + workflows—not the product itself).

### 5.2 Worker Architecture (Critical for Scaling Locally)
*   **Concept:** Async + distributed execution, even locally, optimized for performance.
*   **Suggested Stack:** FastAPI (control layer), Celery / Dramatiq / Arq (task queue), Redis (broker).
*   **Separate Worker Pools:** `workers/scanner/`, `workers/embeddings/`, `workers/agents/`, `workers/workflows/`, `workers/lifecycle/`, `workers/simulation/`.
*   **Task Flow:** User Action → API → Queue Task → Worker Executes → Update Spine → Notify via WebSocket.
*   **Performance Considerations:** Implement efficient task queuing, load balancing across worker pools, and resource management to ensure responsiveness and scalability on local machines.

### 5.3 Local AI Runtime
*   **Concept:** Turns the desktop app into an AI compute orchestrator, with a strong focus on performance.
*   **LLM Routing Layer:**
    ```python
    def route_task(task):
        if task.type == "scan":
            return small_model
        elif task.type == "reasoning":
            return mid_model
        elif task.type == "synthesis":
            return large_model
        elif task.type == "gate_evaluation":
            return mid_model
        elif task.type == "simulation": # New task type
            return large_model # or specialized model
    ```
*   **Additional Features:** VRAM-aware scheduling, Token budgeting, Fallback models.
*   **Performance Considerations:** Optimize LLM inference, manage model loading/unloading, and leverage hardware acceleration (e.g., GPU) for local execution.

---

## Layer 6: Observability (Trust Layer)
*   **Must Have:** Agent logs, Decision traces, "Why this output?", Lifecycle transition logs, Simulation results, Constraint violations.
*   **Diff:** Model claim vs actual code, UoW state vs actual progress, Spec → Reality Drift Delta.
*   **Human Override Ledger (Auditable):**
    ```json
    {
      "uow_id": "...",
      "gate": "Defined → Ready",
      "failed_checks": ["missing acceptance criteria"],
      "override_by": "user_id",
      "reason": "...",
      "outcome": "success | failure",
      "timestamp": "..."
    }
    ```
    *   **[x] Designed and Implemented**
*   **Explainability UX:** Instant clarity for gate failures (Reason, Fix, Impact).

### Failure Handling and Override Flows
*   **Concept:** A robust system for managing gate failures, allowing for human intervention with accountability.
*   **Override Mechanism:** Implement a clear process for users to override a BLOCK or CONDITIONAL decision.
*   **Override Ledger Integration:** Every override must be logged in the Human Override Ledger, capturing `uow_id`, `gate`, `failed_checks`, `override_by`, `reason`, `outcome`, and `timestamp`.
*   **Accountability:** Overrides should require explicit user input and justification, feeding into the Learning Layer for analysis.
*   **Notification System:** Alert relevant users/teams about gate failures and overrides.

---

## Layer 7: Insight (Your Monetization Engine)

### 7.1 Success Scorecard (Dangerously Good)
*   **Health Score:**
    ```text
    Health Score =
        Drift Score +
        Spec Alignment +
        Test Coverage +
        Delivery Integrity +
        Flow Efficiency +
        Simulation Accuracy + // New
        Constraint Compliance // New
    ```
*   **New Metrics:**
    *   **Gate Compliance Rate:** % of transitions that passed all requirements.
    *   **Acceptance Criteria Timing:** Written before vs after dev.
    *   **State Regression Count:** Number of backward transitions.
    *   **Objective Clarity Score:** Measurable vs vague goals.
    *   **Time-to-Decision Compression:** Time between gate failure → resolution, Spec creation → approval.
*   **Output:** 0–100 score, Trend over time, Benchmark vs other projects.

### 7.2 Risk Prediction
*   **Concept:** AI-driven alerts for delivery risks, now incorporating lifecycle integrity, simulation, and constraint data.
*   **Examples:** Drift ↑ + PR slowdown → delivery risk; High dependency churn → instability risk; Low Gate Compliance Rate → process breakdown risk; High State Regression Count → project instability risk; **High Simulation Risk Profile → pre-execution warning.**

---

## Layer 8: Learning Layer (Your Moat)
*   **Concept:** Continuously learn from workflow successes/failures, patterns, and architectures, now including behavioral enforcement data, simulation outcomes, and override data.
*   **Outcome:** Smarter agents, better defaults, industry-specific playbooks over time, **Adaptive enforcement**.
*   **New Moat:** **Behavioral enforcement data** – learning what "good delivery" actually looks like, which teams follow process vs drift, and what patterns predict failure.
*   **Failure Pattern Library:** Capture reusable failure archetypes to auto-detect patterns, auto-suggest fixes, and preemptively block similar setups.
*   **Delivery Fingerprints:** Formalize Project / Team Fingerprints (architecture style, workflow behavior, drift patterns, velocity profile) for comparison, prediction, and playbook recommendations.

---

## Strategic Refocus: Winning Entry Point
*   **Shift:** From "Audit + Onboarding" to **"AI-Enforced Delivery System."**
*   **MVP Positioning:** Instead of "We analyze your repo," it's **"We ensure every unit of work is valid before it starts."**
*   **Immediate Use Case:** Drop into an agency, hook into Git + tickets, start blocking bad work. High-value instantly.

---

## Final Synthesis: What You Just Unlocked
NewFang becomes a **predictive, enforced, self-improving execution system** for software delivery. It guarantees the conditions required for predictable outcomes—and adapts when reality deviates.

### Loop:
```text
Define →
    Simulate → // New
        Validate (Gated) →
            Execute →
                Monitor →
                    Gate →
                        Score →
                            Learn →
                                Improve next cycle
```

---

## The Real Make-or-Break Decisions
*   **State Machine Schema:** Exact states, transition rules, required artifacts per gate.
*   **UoW Contract:** What *must* exist before work begins.
*   **Gate Evaluation Engine:** How AI validates each transition deterministically.
*   **Simulation Engine:** How to accurately predict outcomes and risks.
*   **Constraint Engine:** How to define and enforce hard rules flexibly.

---

**Important Considerations for Implementation:**
*   Make gates *fast*.
*   Make feedback *actionable* (Explainability UX).
*   Allow *override with accountability* (Human Override Ledger).

---

**Top 3 to build next (Prioritized):**
1.  **Simulation Mode:** Immediate differentiation, moves from "valid work" to "predictably successful work."
2.  **Constraint Engine:** Provides hard guarantees, separates AI suggestions from system-enforced invariants.
3.  **Human Override Ledger:** Critical for adoption and feeds the Learning Layer for adaptive enforcement.
