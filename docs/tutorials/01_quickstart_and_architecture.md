# Tutorial 1: Architecture & Controlled Autonomy Model

Welcome to **GxPSoft** — an AI-Agent-First, Human-in-the-Loop-Second Quality Management System (QMS) built for regulated life sciences manufacturing (21 CFR Part 11, EU Annex 11, GAMP 5).

---

## 1. Core Architectural Philosophy

Traditional electronic QMS (eQMS) systems are reactive and form-driven: humans spend hours copying telemetry from SCADA/MES, writing deviation descriptions, searching historical logs, and filling out CAPA paperwork.

GxPSoft implements the **Bifurcated Architecture**:
```
  [Operational Telemetry] ──> [Autonomous Agents] ──> [Staged Drafts & Decision Packets]
                                                              │
                                                              ▼
                                                   [Qualified Human Signs (e-Sig)]
                                                              │
                                                              ▼
                                                   [Deterministic State Machine & Ledger]
```

### The 5 Non-Negotiables
1. **Agents Investigate & Prepare. Humans Decide & Sign**: AI agents autonomously assemble multi-system evidence and stage drafts. Classification approvals, root-cause confirmations, and CAPA authorizations **strictly require a qualified human electronic signature** (§11.50).
2. **Deterministic QMS Core**: The Finite State Machine (FSM), RBAC/ABAC policy engine, and signature verifier are deterministic code. The LLM is **never** the state-transition authority.
3. **Line-Level Evidence Grounding**: 100% of material AI assertions cite exact source documents with line numbers and property paths.
4. **Controlled Autonomy Model ($A_0$–$A_5$)**: Strict fencing of what agents vs. humans can execute.
5. **Cryptographic Reconstructability**: Every state change, tool invocation, model prompt hash, and signature is recorded in an immutable, forward-chained SHA-256 audit ledger.

---

## 2. Controlled Autonomy Model ($A_0$ to $A_5$)

| Class | Name | Who Can Execute | Examples | Guardrail |
| :--- | :--- | :--- | :--- | :--- |
| **$A_0$** | Observe | Autonomous Agents & Humans | Read SCADA logs, search SOPs, query batch genealogy | Read-only; fully logged |
| **$A_1$** | Annotate | Autonomous Agents & Humans | Attach tags, calculate trend anomalies | Metadata updates; non-binding |
| **$A_2$** | Prepare / Draft | Autonomous Agents & Humans | Stage 5-Why RCA, draft CAPA action items | Staged in sandbox for QA review |
| **$A_3$** | Support Execution | Autonomous Agents & Humans | Schedule reminder, generate export dossier | Non-GxP execution |
| **$A_4$** | Controlled GxP Action | **Qualified Humans ONLY** | Approve deviation severity, confirm root cause, authorize CAPA | **Requires 21 CFR Part 11 electronic signature** |
| **$A_5$** | Prohibited | **Nobody (Blocked)** | Bypass state machine, forge e-signatures, delete audit entries | Rejected deterministically |

---

## 3. Environment & Prerequisites

### Prerequisites
- **Python 3.11+**
- **[`uv`](https://astral.sh/uv)** (Fast package manager): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **[Ollama](https://ollama.ai)**: Running locally with `muse-glimmer` (`ollama run muse-glimmer`)
- **[Langfuse](https://langfuse.com)**: Running locally on `http://localhost:3000` (Docker Compose or binary)

### Quick Setup
```bash
# 1. Clone repository
git clone https://github.com/gxpsoft-ai/gxpsoft-poc.git
cd gxpsoft-poc

# 2. Install dependencies with uv
uv sync --all-extras

# 3. Configure environment variables
cp .env.example .env

# 4. Verify test suite
uv run pytest -v
```

---

## 4. Launching the Platform

### Start the FastAPI Application
```bash
uv run uvicorn gxpsoft.api.main:app --reload --port 8000
```

- **Interactive Split-Screen Review UI**: `http://localhost:8000/ui/case/DEV-2026-0001`
- **Interactive OpenAPI Documentation**: `http://localhost:8000/docs`
- **Langfuse Observability Dashboard**: `http://localhost:3000`

---

## Next Steps
Proceed to **[Tutorial 2: Pydantic AI Agents & Local Ollama (`muse-glimmer`)](./02_pydantic_ai_agents_and_ollama.md)** to learn how autonomous agents are constructed, prompted, and executed.
