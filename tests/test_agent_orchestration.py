"""Integration tests for the complete automated InvestigationPipeline."""

from pathlib import Path
import pytest

from gxpsoft.agents.orchestrator import InvestigationPipeline
from gxpsoft.core.repository import repo
from gxpsoft.evidence.indexer import evidence_indexer
from gxpsoft.models.enums import CaseSeverity, CaseState


@pytest.fixture(autouse=True)
def index_fixtures(fixtures_dir: Path) -> None:
    evidence_indexer.index_document_directory(fixtures_dir / "documents")


def test_end_to_end_investigation_pipeline(mes_event_payload: dict) -> None:
    payload = dict(mes_event_payload)
    payload["idempotency_key"] = "test:pipeline:e2e:001"
    payload["event_id"] = "EVT-PIPE-001"

    event, case, summary = InvestigationPipeline.run_pipeline(payload)

    # 1. Verify Event and Case state
    assert event.event_id == "EVT-PIPE-001"
    assert case.severity == CaseSeverity.MAJOR
    assert case.state == CaseState.CONTAINMENT_PROPOSED
    assert summary["claims_count"] == 5

    # 2. Verify Audit Ledger integrity across the multi-agent run
    assert repo.audit_ledger.verify_integrity() is True

    # 3. Verify AgentRuns logged
    case_audit_entries = [e for e in repo.audit_ledger.entries if e.case_id == case.case_id]
    event_types = [e.event_type for e in case_audit_entries]

    assert "CASE_INITIALIZED" in event_types
    assert "AGENT_RUN_COMPLETED" in event_types
    assert "TOOL_INVOKED" in event_types
    assert "STATE_TRANSITION" in event_types
