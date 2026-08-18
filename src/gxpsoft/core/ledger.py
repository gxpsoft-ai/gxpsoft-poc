"""Cryptographic Audit Ledger maintaining 21 CFR Part 11 append-only tamper-evident records."""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from gxpsoft.models.audit import AuditLogEntry
from gxpsoft.models.enums import AuthorType
from gxpsoft.core.crypto import compute_audit_hash, compute_sha256


class AuditLedger:
    """In-memory / persistence ledger managing forward-hash-chained audit logs."""

    def __init__(self) -> None:
        self.entries: List[AuditLogEntry] = []

    @property
    def latest_hash(self) -> str:
        """Returns the hash of the latest audit entry or genesis hash."""
        if not self.entries:
            return "0" * 64
        return self.entries[-1].entry_hash

    def append(
        self,
        event_type: str,
        entity_type: str,
        entity_id: str,
        actor_id: str,
        actor_type: AuthorType,
        data_snapshot: Dict[str, Any],
        case_id: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> AuditLogEntry:
        """Appends a new immutable audit record to the ledger, computing the chain hash."""
        ts = timestamp or datetime.now(timezone.utc)
        seq = len(self.entries) + 1
        prev = self.latest_hash
        data_hash = compute_sha256(data_snapshot)
        entry_hash = compute_audit_hash(
            prev_hash=prev,
            timestamp=ts.isoformat(),
            event_type=event_type,
            entity_id=entity_id,
            actor_id=actor_id,
            data_hash=data_hash
        )

        entry = AuditLogEntry(
            sequence_number=seq,
            case_id=case_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            actor_type=actor_type,
            data_snapshot=data_snapshot,
            data_hash=data_hash,
            prev_hash=prev,
            entry_hash=entry_hash,
            timestamp=ts
        )
        self.entries.append(entry)
        return entry

    def verify_integrity(self) -> bool:
        """Validates the entire cryptographic hash chain of the audit trail.
        
        Returns True if all hashes are valid and unbroken, False otherwise.
        """
        for i, entry in enumerate(self.entries):
            expected_prev = "0" * 64 if i == 0 else self.entries[i - 1].entry_hash
            if entry.prev_hash != expected_prev:
                return False

            # Verify data hash
            recomputed_data_hash = compute_sha256(entry.data_snapshot)
            if entry.data_hash != recomputed_data_hash:
                return False

            # Verify entry hash
            recomputed_entry_hash = compute_audit_hash(
                prev_hash=entry.prev_hash,
                timestamp=entry.timestamp.isoformat(),
                event_type=entry.event_type,
                entity_id=entry.entity_id,
                actor_id=entry.actor_id,
                data_hash=entry.data_hash
            )
            if entry.entry_hash != recomputed_entry_hash:
                return False

        return True
