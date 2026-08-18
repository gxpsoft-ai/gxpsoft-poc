"""Unit tests verifying IngestionService with deduplication and case attachment."""

import pytest

from gxpsoft.core.repository import repo
from gxpsoft.ingestion.service import DuplicateEventError, IngestionService
from gxpsoft.models.enums import CaseState, EventStatus


def test_successful_event_ingestion(mes_event_payload: dict) -> None:
    event, case = IngestionService.ingest_event(mes_event_payload)

    assert event.event_id == "EVT-MES-20260818-001"
    assert event.status == EventStatus.CASE_ATTACHED
    assert case is not None
    assert case.state == CaseState.SIGNAL_RECEIVED
    assert case.batch_id == "BIO-2026-088"
    assert case.initial_event_id == event.event_id

    # Verify event stored in repository
    stored_event = repo.get_event(event.event_id)
    assert stored_event is not None
    assert stored_event.payload_hash == event.payload_hash


def test_duplicate_event_rejection(mes_event_payload: dict) -> None:
    # First ingestion succeeds
    payload = dict(mes_event_payload)
    payload["idempotency_key"] = "test:unique:dup:key:001"
    payload["event_id"] = "EVT-DUP-TEST-01"

    event1, case1 = IngestionService.ingest_event(payload)
    assert event1 is not None

    # Second ingestion with same idempotency key fails
    with pytest.raises(DuplicateEventError) as exc_info:
        IngestionService.ingest_event(payload)

    assert "Duplicate event detected" in str(exc_info.value)
    assert exc_info.value.existing_event.event_id == "EVT-DUP-TEST-01"
