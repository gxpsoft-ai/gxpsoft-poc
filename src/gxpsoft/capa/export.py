"""Tamper-evident Decision Lineage regulatory export generator for 21 CFR Part 11 compliance."""

from datetime import datetime, timezone
from typing import Any, Dict, List
from pydantic import BaseModel, Field

from gxpsoft.core.crypto import compute_sha256
from gxpsoft.core.repository import repo
from gxpsoft.models.agent_run import AgentRun, DraftArtifact, ToolCall
from gxpsoft.models.audit import AuditLogEntry, SignatureRecord, StateTransition
from gxpsoft.models.case import QualityCase
from gxpsoft.models.event import QualityEvent
from gxpsoft.models.evidence import Claim


class DecisionLineageExport(BaseModel):
    """Complete, reconstructable regulatory audit dossier."""
    export_id: str = Field(description="Unique export manifest ID")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    regulatory_framework: List[str] = [
        "21 CFR Part 11 (Electronic Records; Electronic Signatures)",
        "EU GMP Annex 11 (Computerised Systems)",
        "FDA QMSR (21 CFR Part 820 / ISO 13485:2016)"
    ]
    case: QualityCase
    triggering_event: QualityEvent
    agent_runs: List[AgentRun] = Field(default_factory=list)
    draft_artifacts: List[DraftArtifact] = Field(default_factory=list)
    claims: List[Claim] = Field(default_factory=list)
    state_transitions: List[StateTransition] = Field(default_factory=list)
    electronic_signatures: List[SignatureRecord] = Field(default_factory=list)
    audit_trail_entries: List[AuditLogEntry] = Field(default_factory=list)
    audit_trail_integrity_verified: bool = True
    manifest_sha256: str = Field(default="")


class DecisionLineageExporter:
    """Generates 1-click reconstructable decision lineage export dossiers."""

    @staticmethod
    def generate_export(case_id: str) -> DecisionLineageExport:
        """Compiles the complete historical evidence and cryptographic lineage for a case."""
        case = repo.get_case(case_id)
        if not case:
            raise ValueError(f"QualityCase '{case_id}' not found.")

        event = repo.get_event(case.initial_event_id)
        if not event:
            raise ValueError(f"Initial event '{case.initial_event_id}' not found.")

        # Gather all related artifacts
        claims = repo.get_claims_for_case(case_id)
        drafts = repo.get_drafts_for_case(case_id)
        transitions = repo.get_transitions_for_case(case_id)
        signatures = [s for s in repo.signatures.values() if s.case_id == case_id]
        audit_entries = [e for e in repo.audit_ledger.entries if e.case_id == case_id or e.case_id is None]
        
        # Verify ledger integrity
        is_integrity_valid = repo.audit_ledger.verify_integrity()

        # Extract agent runs from audit ledger
        agent_runs = []
        for e in audit_entries:
            if e.event_type == "AGENT_RUN_COMPLETED":
                agent_runs.append(AgentRun(**e.data_snapshot))

        export_obj = DecisionLineageExport(
            export_id=f"EXP-{case_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            case=case,
            triggering_event=event,
            agent_runs=agent_runs,
            draft_artifacts=drafts,
            claims=claims,
            state_transitions=transitions,
            electronic_signatures=signatures,
            audit_trail_entries=audit_entries,
            audit_trail_integrity_verified=is_integrity_valid
        )

        # Compute tamper-evident manifest hash
        snapshot = export_obj.model_dump(mode="json", exclude={"manifest_sha256"})
        export_obj.manifest_sha256 = compute_sha256(snapshot)

        return export_obj
