"""Unit tests for SentinelAgent triage, severity calculation, and case creation."""

from pathlib import Path
import pytest

from gxpsoft.agents.sentinel import SentinelAgent
from gxpsoft.core.repository import repo
from gxpsoft.evidence.indexer import evidence_indexer
from gxpsoft.ingestion.service import IngestionService
from gxpsoft.models.enums import CaseSeverity, CaseState


@pytest.fixture(autouse=True)
def index_fixtures(fixtures_dir: Path) -> None:
    evidence_indexer.index_document_directory(fixtures_dir / "documents")


def test_sentinel_evaluation_major_excursion(mes_event_payload: dict) -> None:
    payload = dict(mes_event_payload)
    payload["idempotency_key"] = "test:sentinel:major:001"
    payload["event_id"] = "EVT-SENTINEL-001"

    event, case = IngestionService.ingest_event(payload)
    assert case is not None
    assert case.state == CaseState.SIGNAL_RECEIVED

    result = SentinelAgent.evaluate_event(event=event, case=case)

    assert result["severity"] == CaseSeverity.MAJOR.value
    assert case.severity == CaseSeverity.MAJOR
    assert case.state == CaseState.CASE_CREATED
    assert "SOP-PRC-042" in result["rationale"]


def test_sentinel_evaluation_minor_excursion(mes_event_payload: dict) -> None:
    payload = dict(mes_event_payload)
    payload["idempotency_key"] = "test:sentinel:minor:002"
    payload["event_id"] = "EVT-SENTINEL-002"
    payload["payload"]["peak_value"] = 37.8
    payload["payload"]["duration_minutes"] = 8.0

    event, case = IngestionService.ingest_event(payload)
    assert case is not None

    result = SentinelAgent.evaluate_event(event=event, case=case)

    assert result["severity"] == CaseSeverity.MINOR.value
    assert case.severity == CaseSeverity.MINOR
    assert case.state == CaseState.CASE_CREATED
