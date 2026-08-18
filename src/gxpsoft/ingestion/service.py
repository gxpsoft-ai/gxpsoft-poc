"""Canonical operational event ingestion service with deduplication and audit logging."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from gxpsoft.core.crypto import compute_sha256
from gxpsoft.core.repository import repo
from gxpsoft.models.case import QualityCase
from gxpsoft.models.enums import AuthorType, CaseSeverity, CaseState, CaseType, EventStatus
from gxpsoft.models.event import QualityEvent


class DuplicateEventError(Exception):
    """Raised when an event with identical idempotency key is re-ingested."""
    def __init__(self, message: str, existing_event: QualityEvent):
        super().__init__(message)
        self.existing_event = existing_event


class IngestionService:
    """Ingestion engine for MES, LIMS, ERP, and IoT quality events."""

    @staticmethod
    def ingest_event(payload_dict: Dict[str, Any], auto_create_case: bool = True) -> Tuple[QualityEvent, Optional[QualityCase]]:
        """Processes a raw operational event payload.
        
        Performs idempotency check, SHA-256 hashing, repository registration,
        audit logging, and automatic initial case generation.
        """
        # Instantiate and validate QualityEvent
        event = QualityEvent(**payload_dict)

        # 1. Deduplication check
        existing = repo.find_event_by_idempotency_key(event.idempotency_key)
        if existing:
            event.status = EventStatus.DUPLICATE
            raise DuplicateEventError(
                message=f"Duplicate event detected for idempotency key '{event.idempotency_key}'.",
                existing_event=existing
            )

        # 2. Register event in repository
        event.status = EventStatus.INGESTED
        repo.add_event(event)

        # 3. Log to Cryptographic Audit Ledger
        repo.audit_ledger.append(
            event_type="EVENT_INGESTED",
            entity_type="QualityEvent",
            entity_id=event.event_id,
            actor_id="INGESTION_SERVICE",
            actor_type=AuthorType.SYSTEM,
            data_snapshot={
                "event_id": event.event_id,
                "event_type": event.event_type,
                "source_system": event.source_system,
                "payload_hash": event.payload_hash,
                "idempotency_key": event.idempotency_key,
                "batch_id": event.batch_id,
            },
            timestamp=event.received_at
        )

        case = None
        if auto_create_case:
            case = IngestionService._create_initial_case(event)

        return event, case

    @staticmethod
    def _create_initial_case(event: QualityEvent) -> QualityCase:
        """Initializes a new QualityCase in SIGNAL_RECEIVED state."""
        title = f"{event.event_type} on {event.source_system} ({event.batch_id or 'No Batch'})"
        desc = f"Automatic case triggered by {event.source_system} event {event.source_record_id}."

        case = QualityCase(
            case_type=CaseType.DEVIATION,
            title=title,
            description=desc,
            state=CaseState.SIGNAL_RECEIVED,
            initial_event_id=event.event_id,
            product_id=event.product_id,
            batch_id=event.batch_id,
            site_id=event.site_id,
            metadata={"source_event_type": event.event_type}
        )

        repo.add_case(case)
        event.status = EventStatus.CASE_ATTACHED

        # Audit case creation
        repo.audit_ledger.append(
            event_type="CASE_INITIALIZED",
            entity_type="QualityCase",
            entity_id=case.case_id,
            actor_id="INGESTION_SERVICE",
            actor_type=AuthorType.SYSTEM,
            data_snapshot={
                "case_id": case.case_id,
                "state": case.state.value,
                "initial_event_id": event.event_id,
                "batch_id": case.batch_id
            },
            case_id=case.case_id,
            timestamp=case.created_at
        )

        return case
