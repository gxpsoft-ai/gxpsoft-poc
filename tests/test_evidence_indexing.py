"""Unit tests verifying EvidenceIndexer and exact locator generation."""

from pathlib import Path
import pytest

from gxpsoft.core.repository import repo
from gxpsoft.evidence.indexer import EvidenceIndexer


def test_indexing_markdown_and_json_fixtures(fixtures_dir: Path) -> None:
    indexer = EvidenceIndexer()
    doc_dir = fixtures_dir / "documents"
    count = indexer.index_document_directory(doc_dir)

    assert count >= 6
    assert len(indexer.chunks) > 10

    # Verify SOP chunk locators have line numbers
    sop_chunks = [c for c in indexer.chunks if c.doc_type == "SOP"]
    assert len(sop_chunks) > 0
    assert any("Lines" in c.locator for c in sop_chunks)

    # Verify sensor chunks have exact property locators
    calib_chunks = [c for c in indexer.chunks if c.doc_type == "CALIBRATION_LOG"]
    assert len(calib_chunks) >= 3
    rtd_chunk = next(c for c in calib_chunks if "RTD-04B" in c.locator)
    assert "RTD-04B" in rtd_chunk.text
    assert "EXPIRED" in rtd_chunk.text
