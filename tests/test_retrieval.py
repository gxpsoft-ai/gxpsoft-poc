"""Unit tests verifying search retrieval over indexed GxP documents."""

from pathlib import Path
import pytest

from gxpsoft.evidence.indexer import EvidenceIndexer


@pytest.fixture
def populated_indexer(fixtures_dir: Path) -> EvidenceIndexer:
    indexer = EvidenceIndexer()
    indexer.index_document_directory(fixtures_dir / "documents")
    return indexer


def test_search_sops_for_temperature_excursion(populated_indexer: EvidenceIndexer) -> None:
    results = populated_indexer.search("temperature excursion critical limits", doc_type="SOP", limit=3)
    assert len(results) > 0
    top_chunk, score = results[0]
    assert "SOP-PRC-042" in top_chunk.doc_title or "SOP-QMS-015" in top_chunk.doc_title
    assert "temperature" in top_chunk.text.lower()
    assert score > 0.3


def test_search_historical_deviations(populated_indexer: EvidenceIndexer) -> None:
    results = populated_indexer.search("RTD calibration drift probe", doc_type="HISTORICAL_DEVIATIONS", limit=2)
    assert len(results) > 0
    top_chunk, score = results[0]
    assert "DEV-2025-312" in top_chunk.heading or "RTD" in top_chunk.text
