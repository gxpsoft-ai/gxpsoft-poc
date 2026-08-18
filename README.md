# GxPSoft POC: AI-Agent-First, HITL-Second QMS

A reference implementation of a regulated Quality Management System (QMS) built on the **AI-Agent-First, HITL-Second** paradigm for 21 CFR Part 11, EU Annex 11, and FDA QMSR (ISO 13485:2016) compliance.

## Key Principles
1. **Agents investigate & prepare; humans decide & sign.**
2. **Deterministic state machine:** The core FSM and policy engine own record transitions, not the LLM.
3. **Claim-level evidence lineage:** Every material statement is backed by an inspectable citation.
4. **Reconstructable audit trail:** Complete decision provenance from raw event hash to e-signature.
