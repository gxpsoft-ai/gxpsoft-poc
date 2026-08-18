# Tutorial 3: Governed Tool Gateway & Evidence Graph

In an autonomous GxP system, AI agents must never have direct, unmediated access to enterprise APIs or database writes. This tutorial covers the **Governed Tool Gateway** and the **Line-Level Evidence Graph**.

---

## 1. Why a Governed Tool Gateway?

Traditional agent frameworks execute tools as raw Python functions or HTTP requests without compliance controls. In GxPSoft, every tool invocation passes through the [`ToolGateway`](file:///home/d3lee/my-repos/gxpsoft-poc/src/gxpsoft/tools/gateway.py):

```
Agent Action ──> [ToolGateway] ──> 1. PolicyEngine.validate_action(ActionClass)
                               ──> 2. Execute Typed Tool
                               ──> 3. Record ToolCall Provenance (latency, payload)
                               ──> 4. Append to Cryptographic AuditLedger
                               ──> 5. Langfuse Distributed Trace (@observe as_type="tool")
```

### Registered Tools & Action Class Classification
| Tool Name | Target System | Action Class | Description |
| :--- | :--- | :--- | :--- |
| `search_sops` | DMS | $A_0$ (Observe) | Full-text and hybrid section retrieval over SOPs |
| `get_equipment_calibration` | CMMS | $A_0$ (Observe) | Retrieves NIST sensor calibration registers |
| `get_batch_genealogy` | MES / ERP | $A_0$ (Observe) | Retrieves batch bill-of-materials and in-process assay samples |
| `get_operator_training` | LMS | $A_0$ (Observe) | Queries operator training curriculum qualifications |
| `find_similar_deviations` | QMS | $A_0$ (Observe) | Vector / semantic search over historical deviation records |
| `stage_investigation_draft` | Staging DB | $A_2$ (Prepare) | Stages draft report and registers atomic claims for QA review |

---

## 2. Policy Engine Guardrail Check

Before a tool executes, [`PolicyEngine.validate_action`](file:///home/d3lee/my-repos/gxpsoft-poc/src/gxpsoft/core/policy.py) ensures:
- Agents are permitted for $A_0, A_1, A_2, A_3$.
- Agents are **strictly blocked** from $A_4$ (Controlled GxP Actions) and $A_5$ (Prohibited).
- Humans attempting $A_4$ actions possess qualified roles (`QA_LEAD`, `QA_DIRECTOR`) and valid electronic signature credentials.

---

## 3. Evidence Graph & Line-Level Citations

In regulated quality investigations, generic assertions ("the sensor was expired") are inadmissible without line-level provenance.

### The Evidence Model ([`models/evidence.py`](file:///home/d3lee/my-repos/gxpsoft-poc/src/gxpsoft/models/evidence.py))
Every document in `fixtures/documents/` is indexed by [`EvidenceIndexer`](file:///home/d3lee/my-repos/gxpsoft-poc/src/gxpsoft/evidence/indexer.py):
- Parsed into sections and line ranges (e.g. `L22-L35`).
- Fingerprinted with SHA-256 payload hashes.

### Atomic Claim with Exact Quote Citations
When `NCInvestigatorAgent` stages a draft, it binds assertions to [`EvidenceClaim`](file:///home/d3lee/my-repos/gxpsoft-poc/src/gxpsoft/models/evidence.py#L24):

```python
{
    "claim_text": "Primary temperature sensor RTD-04B on Bioreactor BR-04 was 10 days past its 90-day NIST calibration due date (Expired 2026-02-08).",
    "author_id": "NCInvestigatorAgent",
    "confidence": 0.99,
    "uncertainty_notes": "None. Direct record match from CMMS calibration register.",
    "citations": [
        {
            "evidence_id": "EVD-CALIB-04",
            "locator": "Equipment BR-04 -> Sensor RTD-04B",
            "quote_text": "calibration_status: EXPIRED, days_overdue_as_of_event: 10",
            "relevance_score": 1.0,
            "match_method": "EXACT_EXTRACTION"
        }
    ]
}
```

---

## Next Steps
Proceed to **[Tutorial 4: 21 CFR Part 11 Compliance & Cryptographic Audit Trail](./04_cfr_part11_and_crypto_audit.md)** to see how electronic signatures and tamper-evident ledgers work.
