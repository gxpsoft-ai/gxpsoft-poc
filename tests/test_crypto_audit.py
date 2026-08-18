"""Unit tests for cryptographic audit ledger and tamper-evident hash chaining."""

from datetime import datetime, timezone
import pytest

from gxpsoft.core.crypto import canonical_json, compute_sha256
from gxpsoft.core.ledger import AuditLedger
from gxpsoft.models.enums import AuthorType


def test_canonical_json_determinism() -> None:
    data1 = {"b": 2, "a": 1, "nested": {"z": 10, "y": 20}}
    data2 = {"nested": {"y": 20, "z": 10}, "a": 1, "b": 2}
    assert canonical_json(data1) == canonical_json(data2)
    assert compute_sha256(data1) == compute_sha256(data2)


def test_audit_ledger_hash_chain_integrity() -> None:
    ledger = AuditLedger()
    assert ledger.latest_hash == "0" * 64

    # Entry 1: Genesis event
    e1 = ledger.append(
        event_type="EVENT_INGESTED",
        entity_type="QualityEvent",
        entity_id="EVT-001",
        actor_id="INGESTION_SERVICE",
        actor_type=AuthorType.SYSTEM,
        data_snapshot={"event_id": "EVT-001", "temp": 39.4},
        case_id="DEV-001",
    )
    assert e1.sequence_number == 1
    assert e1.prev_hash == "0" * 64
    assert ledger.latest_hash == e1.entry_hash

    # Entry 2: Agent draft staged
    e2 = ledger.append(
        event_type="DRAFT_STAGED",
        entity_type="DraftArtifact",
        entity_id="ART-001",
        actor_id="NCAgent-v1.0",
        actor_type=AuthorType.AGENT,
        data_snapshot={"artifact_id": "ART-001", "hypotheses": ["Sensor Drift"]},
        case_id="DEV-001",
    )
    assert e2.sequence_number == 2
    assert e2.prev_hash == e1.entry_hash
    assert ledger.latest_hash == e2.entry_hash

    # Entry 3: Human e-signature
    e3 = ledger.append(
        event_type="SIGNATURE_APPLIED",
        entity_type="SignatureRecord",
        entity_id="SIG-001",
        actor_id="USER-QA-LEAD",
        actor_type=AuthorType.HUMAN,
        data_snapshot={"meaning": "APPROVED_ROOT_CAUSE", "user": "Jane Doe"},
        case_id="DEV-001",
    )
    assert e3.sequence_number == 3
    assert e3.prev_hash == e2.entry_hash
    assert ledger.latest_hash == e3.entry_hash

    # Verify ledger passes integrity check
    assert ledger.verify_integrity() is True


def test_audit_ledger_detects_tampering() -> None:
    ledger = AuditLedger()
    ledger.append(
        event_type="EVENT_INGESTED",
        entity_type="QualityEvent",
        entity_id="EVT-001",
        actor_id="INGESTION_SERVICE",
        actor_type=AuthorType.SYSTEM,
        data_snapshot={"temp": 39.4},
    )
    ledger.append(
        event_type="DRAFT_STAGED",
        entity_type="DraftArtifact",
        entity_id="ART-001",
        actor_id="NCAgent-v1.0",
        actor_type=AuthorType.AGENT,
        data_snapshot={"hypotheses": ["Sensor Drift"]},
    )
    assert ledger.verify_integrity() is True

    # Tamper with entry 1's data snapshot
    ledger.entries[0].data_snapshot["temp"] = 37.0

    # Verification must fail
    assert ledger.verify_integrity() is False
