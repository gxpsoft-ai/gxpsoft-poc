# Tutorial 2: Pydantic AI Agents & Local Ollama (`muse-glimmer`)

This tutorial covers the autonomous agent architecture in GxPSoft built with **Pydantic AI** and powered by the local **`muse-glimmer`** LLM through **Ollama**.

---

## 1. Why Pydantic AI?

In regulated GxP environments, unstructured natural language generation is a non-compliance liability. Agents must provide:
1. **Strict Type Safety**: Guaranteed schema validation on all inputs and outputs using Pydantic models.
2. **Deterministic Fallbacks & Retries**: Seamless retry loops (`retries=3`) when local LLMs generate slight schema mismatches.
3. **Tool Provenance**: Native function calling with audit hooks for every invocation.

---

## 2. Centralized Model Configuration (`core/ai_config.py`)

All agents initialize their models via [`src/gxpsoft/core/ai_config.py`](file:///home/d3lee/my-repos/gxpsoft-poc/src/gxpsoft/core/ai_config.py):

```python
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

def get_agent_model(model_name: Optional[str] = None) -> Model:
    selected_model = model_name or os.getenv("OLLAMA_MODEL", "muse-glimmer")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    # Point OpenAIProvider to Ollama's /v1 endpoint
    provider = OpenAIProvider(
        base_url=f"{base_url.rstrip('/')}/v1",
        api_key=os.getenv("OLLAMA_API_KEY", "ollama")
    )
    return OpenAIChatModel(selected_model, provider=provider)
```

---

## 3. The 3 Regulated AI Agents

### Agent 1: `SentinelAgent` (Triage & Signal Classification)
- **Role**: Ingests operational telemetry (e.g. MES bioreactor temperature excursion) and evaluates it against standard operating procedure (SOP) thresholds.
- **Output Schema**: [`SentinelTriageOutput`](file:///home/d3lee/my-repos/gxpsoft-poc/src/gxpsoft/models/agent_schemas.py#L12)
  ```python
  class SentinelTriageOutput(BaseModel):
      severity: CaseSeverity  # MINOR, MAJOR, or CRITICAL
      rationale: str          # Scientific justification citing SOP-PRC-042
      sop_references: List[str]
  ```
- **Execution Flow**:
  1. Searches SOPs via `ToolGateway.invoke("search_sops", ...)`.
  2. Runs Pydantic AI agent against `muse-glimmer`.
  3. Updates case severity and advances state machine: `SIGNAL_RECEIVED` $\rightarrow$ `CASE_CREATED`.
  4. Records `AgentRun` entry in `AuditLedger`.

---

### Agent 2: `NCInvestigatorAgent` (Multi-System Evidence Assembly & 5-Why RCA)
- **Role**: Correlates data across 5 enterprise systems (CMMS, MES/ERP, LMS, QMS, DMS) to find root cause.
- **Output Schema**: [`NCInvestigationOutput`](file:///home/d3lee/my-repos/gxpsoft-poc/src/gxpsoft/models/agent_schemas.py#L55)
  - `containment_plan`: Immediate product quarantine and equipment lockout actions.
  - `five_why_analysis`: 5-Why causal chain.
  - `ranked_hypotheses`: Hypotheses with calibrated confidence scores (e.g. $88\%$ RTD probe calibration drift).
  - `claims`: Atomic factual statements bound to exact evidence locators and quote text.
  - `uncertainty_disclosure`: Explicit disclosure of unobserved variables (e.g. missing high-frequency solenoid telemetry).
- **Execution Flow**:
  1. Advances state: `CASE_CREATED` $\rightarrow$ `EVIDENCE_ASSEMBLED`.
  2. Queries Governed Tools (CMMS calibration logs, MES batch records, LMS operator training, QMS similar deviations).
  3. Formulates RCA with `muse-glimmer`.
  4. Stages `DraftArtifact` (type `INVESTIGATION_REPORT`) and transitions to `CONTAINMENT_PROPOSED`.

---

### Agent 3: `CAPAAgent` (Causal Corrective & Preventive Action Planner)
- **Role**: Drafts an actionable CAPA package tied directly to verified root-cause claims.
- **Output Schema**: [`CAPAPlanOutput`](file:///home/d3lee/my-repos/gxpsoft-poc/src/gxpsoft/models/agent_schemas.py#L82)
  - `capa_actions`:
    - `CORRECTIVE_IMMEDIATE`: Replace and 3-point NIST recalibrate sensor RTD-04B.
    - `CORRECTIVE_SCOPE_ASSESSMENT`: Retrospective batch impact assessment on all batches processed since expiration date.
    - `PREVENTIVE_SYSTEMIC`: Automated CMMS $\leftrightarrow$ MES software lockout interlock preventing recipe start on expired calibration.
    - `PREVENTIVE_TRAINING`: Upstream bioprocess technician line clearance training.
  - `effectiveness_plan`: Quantifiable verification criteria (e.g., 5 consecutive clean batches over 60 days with zero excursions $> 0.5^\circ\text{C}$).
- **Execution Flow**:
  1. Runs after human confirms root cause (`ROOT_CAUSE_CONFIRMED`).
  2. Generates CAPA draft with `muse-glimmer`.
  3. Stages `DraftArtifact` (type `CAPA_PLAN`) and transitions to `CAPA_DRAFTED`.

---

## 4. Running a Live Agent Execution

You can run a live execution script calling `muse-glimmer` directly:

```bash
uv run python -c "
from gxpsoft.agents.sentinel import SentinelAgent
prompt = 'Batch BIO-2026-088 reached 39.4°C for 22.5 min. SOP-PRC-042 limit: >38.5°C for 10 min is Major. Classify.'
res = SentinelAgent.pydantic_agent.run_sync(prompt)
print(res.output.model_dump_json(indent=2))
"
```

Output:
```json
{
  "severity": "MAJOR",
  "rationale": "Peak temperature 39.4°C for Batch BIO-2026-088 meets SOP-PRC-042 MAJOR criteria: Peak temperature >= 39.0°C. Additionally, peak > 38.5°C for duration 22.5 min exceeds >10.0 minutes threshold. Classification is MAJOR.",
  "sop_references": [
    "SOP-PRC-042"
  ]
}
```

---

## Next Steps
Proceed to **[Tutorial 3: Governed Tool Gateway & Evidence Graph](./03_governed_tools_and_evidence_graph.md)** to explore how tool access is audited, rate-controlled, and validated against GxP policy.
