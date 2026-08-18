# GxPSoft Developer & Architect Tutorials

Welcome to the comprehensive guide to building, running, and extending **GxPSoft** — an AI-Agent-First, Human-in-the-Loop-Second Quality Management System powered by **Pydantic AI**, local **`muse-glimmer`** via **Ollama**, and **Langfuse** observability.

---

## 📚 Tutorial Curriculum

| # | Tutorial | Focus Area |
| :---: | :--- | :--- |
| **01** | **[Architecture & Controlled Autonomy Model](./01_quickstart_and_architecture.md)** | Core principles, Action Classes ($A_0$–$A_5$), prerequisites, and quickstart. |
| **02** | **[Pydantic AI Agents & Local Ollama (`muse-glimmer`)](./02_pydantic_ai_agents_and_ollama.md)** | Sentinel, NC Investigator, and CAPA agents with typed Pydantic outputs and local LLM execution. |
| **03** | **[Governed Tool Gateway & Evidence Graph](./03_governed_tools_and_evidence_graph.md)** | GxP tool policy enforcement, rate control, document indexing, and line-level citation grounding. |
| **04** | **[21 CFR Part 11 Compliance & Cryptographic Audit Trail](./04_cfr_part11_and_crypto_audit.md)** | Forward SHA-256 hash chaining, electronic signatures, tamper detection, and decision packets. |
| **05** | **[Langfuse Observability & Distributed Tracing](./05_langfuse_observability.md)** | Full tracing setup with local Langfuse server at `http://localhost:3000`. |
| **06** | **[Golden Evals & GAMP 5 CSA Qualification](./06_evals_and_qualification.md)** | Automated qualification suite, continuous evals, and CSA validation summary reports. |

---

## 🚀 Quick Commands Cheatsheet

```bash
# 1. Run all unit and integration tests (63 tests)
uv run pytest -v

# 2. Run the 5 Regulated Golden Evaluation Scenarios
uv run python -c "from gxpsoft.evals.runner import GoldenEvalRunner; from pathlib import Path; rep = GoldenEvalRunner.run_all(Path('fixtures')); print(f'Passed: {rep.passed_tests}/{rep.total_tests}')"

# 3. Execute the full end-to-end live pipeline with muse-glimmer & Langfuse
uv run python scripts/test_live_muse_glimmer.py

# 4. Start the development server
uv run uvicorn gxpsoft.api.main:app --reload --port 8000
```
