"""Unit tests validating Langfuse observability integration, decorators, and fallback behavior."""

from pathlib import Path
import pytest

from gxpsoft.core.observability import (
    DEFAULT_LANGFUSE_HOST,
    flush_langfuse,
    get_langfuse_client,
    observe,
)
from gxpsoft.evidence.indexer import evidence_indexer
from gxpsoft.ingestion.service import IngestionService
from gxpsoft.agents.orchestrator import InvestigationPipeline


@pytest.fixture(autouse=True)
def index_fixtures(fixtures_dir: Path) -> None:
    evidence_indexer.index_document_directory(fixtures_dir / "documents")


def test_langfuse_default_host():
    """Verify that default host is configured for local Langfuse at http://localhost:3000."""
    assert DEFAULT_LANGFUSE_HOST == "http://localhost:3000"


def test_langfuse_client_initialization_without_keys():
    """Verify client handles missing keys safely without crashing."""
    client = get_langfuse_client()
    # In test environment without explicit keys, client is safely None
    assert client is None or hasattr(client, "flush")


def test_observe_decorator_execution():
    """Verify observe decorator runs wrapped functions seamlessly."""
    @observe(name="test_instrumented_fn", as_type="tool")
    def calculate_metrics(a: int, b: int) -> int:
        return a + b

    result = calculate_metrics(10, 25)
    assert result == 35


def test_end_to_end_instrumented_pipeline_execution(mes_event_payload: dict):
    """Verify full investigation pipeline runs through all @observe wrappers safely."""
    payload = dict(mes_event_payload)
    payload["idempotency_key"] = "test:obs:pipeline:001"
    payload["event_id"] = "EVT-OBS-001"

    event, case, summary = InvestigationPipeline.run_pipeline(payload)
    assert case.case_id.startswith("DEV-")
    assert summary["severity"] == "MAJOR"
    assert summary["claims_count"] == 5

    # Test trace flush
    flush_langfuse()
