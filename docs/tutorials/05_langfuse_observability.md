# Tutorial 5: Langfuse Observability & Distributed Tracing

This tutorial explains how full-stack observability is set up in GxPSoft using a local **Langfuse** server at **`http://localhost:3000`**.

---

## 1. Observability Architecture

GxPSoft instruments all AI agent runs, tool calls, and human review gates using Langfuse v4 tracing:

```
[Operational Event Ingested]
  │
  ▼
[InvestigationPipeline] (ObservationType: chain)
  ├── [SentinelAgent.evaluate_event] (ObservationType: agent)
  │     └── [ToolGateway: search_sops] (ObservationType: tool)
  ├── [NCInvestigatorAgent.investigate] (ObservationType: agent)
  │     ├── [ToolGateway: get_equipment_calibration] (ObservationType: tool)
  │     ├── [ToolGateway: get_batch_genealogy] (ObservationType: tool)
  │     ├── [ToolGateway: get_operator_training] (ObservationType: tool)
  │     ├── [ToolGateway: find_similar_deviations] (ObservationType: tool)
  │     └── [ToolGateway: stage_investigation_draft] (ObservationType: tool)
  ├── [HumanReviewService.approve_and_sign] (ObservationType: guardrail)
  └── [CAPAAgent.generate_capa] (ObservationType: agent)
        └── [ToolGateway: find_similar_deviations] (ObservationType: tool)
```

---

## 2. Configuration & Credentials

Set up your `.env` file from `.env.example`:

```bash
cp .env.example .env
```

Edit `.env`:
```env
# Local Langfuse Server
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key
LANGFUSE_SECRET_KEY=sk-lf-your-secret-key

# Local Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=muse-glimmer
```

> [!NOTE]
> If keys are not set, Langfuse client runs in non-blocking safe mode without crashing.

---

## 3. Observation Types Explained

| Langfuse Observation Type | Used in GxPSoft | What It Captures |
| :--- | :--- | :--- |
| `chain` | `InvestigationPipeline.run_pipeline` | Top-level workflow trace grouping all subagents and steps |
| `agent` | `SentinelAgent`, `NCInvestigatorAgent`, `CAPAAgent` | Agent execution node with prompt hashes, model settings, latency, and tokens |
| `tool` | `ToolGateway.invoke` | Function tool calls, input payloads, policy decisions, and tool response |
| `guardrail` | `HumanReviewService.approve_and_sign` | Human authorization gates, e-signature hashes, and override rationales |

---

## 4. Running the Live Tracing Demo

Execute the live demo script:

```bash
uv run python scripts/test_live_muse_glimmer.py
```

### Inspecting Traces in the Langfuse UI:
1. Open your browser to `http://localhost:3000`.
2. Navigate to **Traces**:
   - Click on the `InvestigationPipeline.run_pipeline` trace.
   - Inspect the sub-spans for `SentinelAgent`, `NCInvestigatorAgent`, `ToolGateway.invoke`, and `CAPAAgent`.
3. View **Generations & Tokens**:
   - Check input tokens, output tokens, latency (ms), and prompt hashes for `muse-glimmer`.
4. View **Agent Graph**:
   - Inspect the visual agent topology and multi-system tool execution sequence.

---

## Next Steps
Proceed to **[Tutorial 6: Golden Evals & GAMP 5 CSA Qualification](./06_evals_and_qualification.md)** to learn about automated validation reporting.
