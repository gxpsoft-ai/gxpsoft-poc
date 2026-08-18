"""Unit tests for NCInvestigatorAgent multi-system evidence gathering and draft staging."""

from pathlib import Path
import pytest

from gxpsoft.agents.nc_investigator import NCInvestigatorAgent
from gxpsoft.agents.sentinel import SentinelAgent
from gxpsoft.core.repository import repo
from gxpsoft.evidence.indexer import evidence_indexer
from gxpsoft.ingestion.service import IngestionService
from gxpsoft.models.enums import CaseState


@pytest.fixture(autouse=True)
def index_fixtures(fixtures_dir: Path) -> None:
    evidence_indexer.index_document_directory(fixtures_dir / "documents")


def test_nc_investigator_full_evidence_assembly(mes_event_payload: dict) -> None:
    payload = dict(mes_event_payload)
    payload["idempotency_key"] = "test:nc:investigate:001"
    payload["event_id"] = "EVT-NC-TEST-001"

    event, case = IngestionService.ingest_event(payload)
    assert case is not None

    # Run Sentinel first
    SentinelAgent.evaluate_event(event=event, case=case)
    assert case.state == CaseState.CASE_CREATED

    # Run NC Investigator
    result = NCInvestigatorAgent.investigate(case_id=case.case_id)

    assert result["status"] == "STAGED_FOR_REVIEW"
    assert result["claims_count"] == 5
    assert case.state == CaseState.CONTAINMENT_PROPOSED

    # Verify DraftArtifact created in repository
    drafts = repo.get_drafts_for_case(case.case_id)
    assert len(drafts) >= 1
    draft = drafts[-1]
    assert draft.artifact_type == "INVESTIGATION_REPORT"
    assert "RTD-04B" in draft.structured_content["five_why_analysis"][2]["why_3"]

    # Verify claims have citations
    claims = repo.get_claims_for_case(case.case_id)
    assert len(claims) >= 5

    # Check expired probe claim
    probe_claim = next(c for c in claims if "RTD-04B" in c.claim_text)
    assert probe_claim.confidence >= 0.95
    assert len(probe_claim.citations) >= 1
    assert "Sensor RTD-04B" in probe_claim.citations[0].locator
