"""Cryptographic utility functions for tamper-evident hashing and audit lineage."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict


def canonical_json(data: Any) -> str:
    """Produces a deterministic, canonical JSON representation.
    
    Keys are sorted recursively, datetime objects are serialized as ISO 8601 UTC strings,
    and whitespace is eliminated.
    """
    def default_serializer(obj: Any) -> Any:
        if isinstance(obj, datetime):
            if obj.tzinfo is None:
                obj = obj.replace(tzinfo=timezone.utc)
            return obj.isoformat()
        if hasattr(obj, "model_dump"):
            return obj.model_dump(mode="json")
        if hasattr(obj, "dict"):
            return obj.dict()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    return json.dumps(data, default=default_serializer, sort_keys=True, separators=(",", ":"))


def compute_sha256(data: Any) -> str:
    """Computes SHA-256 hex digest for any string, bytes, or JSON-serializable object."""
    if isinstance(data, str):
        payload_bytes = data.encode("utf-8")
    elif isinstance(data, bytes):
        payload_bytes = data
    else:
        payload_bytes = canonical_json(data).encode("utf-8")
    return hashlib.sha256(payload_bytes).hexdigest()


def compute_audit_hash(
    prev_hash: str,
    timestamp: str,
    event_type: str,
    entity_id: str,
    actor_id: str,
    data_hash: str
) -> str:
    """Computes the chained SHA-256 hash for an audit log entry."""
    payload = f"{prev_hash}|{timestamp}|{event_type}|{entity_id}|{actor_id}|{data_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
