# Tutorial 4: 21 CFR Part 11 Compliance & Cryptographic Audit Trail

GxPSoft is architected to satisfy the strictest regulatory requirements of **21 CFR Part 11**, **EU Annex 11**, and **FDA QMSR**. This tutorial covers the **Cryptographic Audit Ledger**, **Electronic Signatures**, and **Decision Packets**.

---

## 1. Regulatory Requirements Addressed

| 21 CFR Part 11 Section | Regulatory Requirement | GxPSoft Implementation |
| :--- | :--- | :--- |
| **§11.10(e)** | Secure, computer-generated, time-stamped audit trails | Append-only, sequential, forward-chained SHA-256 [`AuditLedger`](file:///home/d3lee/my-repos/gxpsoft-poc/src/gxpsoft/core/ledger.py) |
| **§11.50** | Signature manifestations (Name, Date/Time, Meaning) | [`SignatureRecord`](file:///home/d3lee/my-repos/gxpsoft-poc/src/gxpsoft/models/audit.py#L12) binding printed name, timestamp, and explicit [`SignatureMeaning`](file:///home/d3lee/my-repos/gxpsoft-poc/src/gxpsoft/models/enums.py) |
| **§11.70** | Signature linking to electronic records | Electronic signatures cryptographically bind the SHA-256 hash of the exact reviewed decision packet |
| **§11.200** | Two distinct electronic signature components | User ID + credential validation with role-based qualification checks |

---

## 2. Forward-Chained Cryptographic Audit Ledger

Every system action (event intake, agent run, tool call, redline, state transition, and signature) is appended as an [`AuditLogEntry`](file:///home/d3lee/my-repos/gxpsoft-poc/src/gxpsoft/models/audit.py#L59):

```
Entry N-1 [entry_hash: e3b0c442...] ───┐
                                       ├──> Entry N [entry_hash = SHA-256(prev_hash + timestamp + event + data_hash)]
                                       │
Entry N   [prev_hash: e3b0c442...]  ───┘
```

### Tamper-Detection Algorithm ([`core/ledger.py`](file:///home/d3lee/my-repos/gxpsoft-poc/src/gxpsoft/core/ledger.py#L54))
If any past audit entry, payload snapshot, or transition record is altered, deleted, or inserted out of sequence, the entire forward hash chain breaks:

```python
# Verifies full ledger integrity
is_valid = repo.audit_ledger.verify_integrity()
# Returns False immediately if any historical record was mutated
```

---

## 3. 21 CFR Part 11 Electronic Signatures

When a QA reviewer approves an action, [`HumanReviewService.approve_and_sign`](file:///home/d3lee/my-repos/gxpsoft-poc/src/gxpsoft/review/service.py#L82) executes:

1. **User Authentication**: Validates user ID, password/PIN, and role qualifications.
2. **Content Hashing**: Calculates `target_content_hash = SHA-256(case + state + draft_content + rationale)`.
3. **Signature Hash Creation**: `signature_hash = SHA-256(user_id | timestamp | meaning | target_content_hash)`.
4. **FSM State Transition**: Deterministic transition with attached signature ID.
5. **Audit Trail Logging**: Creates `SIGNATURE_APPLIED` entry in the cryptographic ledger.

---

## 4. Decision Packets & 1-Click Lineage Export

Inspectors require complete reconstructability of how an AI-assisted quality decision was made.

### Decision Packet Structure ([`review/packet_builder.py`](file:///home/d3lee/my-repos/gxpsoft-poc/src/gxpsoft/review/packet_builder.py))
- Case metadata & current state.
- Chronological state transition audit trail.
- Agent execution provenance (`AgentRun`, model names, prompt hashes, latency, tokens).
- Staged draft artifacts with human redlines and severity override justifications.
- All atomic claims with line-level citations.
- Complete electronic signature records.

### 1-Click Inspection Export Dossier
The endpoint `GET /api/case/{case_id}/export/lineage` produces a standardized JSON / PDF inspection packet exportable during FDA/EMA regulatory audits.

---

## Next Steps
Proceed to **[Tutorial 5: Langfuse Observability & Distributed Tracing](./05_langfuse_observability.md)** to see how every agent and tool run is monitored on `http://localhost:3000`.
