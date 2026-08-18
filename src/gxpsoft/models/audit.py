"""Audit trail, Electronic Signatures, and State Transition models for 21 CFR Part 11."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
import uuid

from gxpsoft.models.enums import ActionClass, AuthorType, CaseState, SignatureMeaning
from gxpsoft.core.crypto import compute_audit_hash, compute_sha256


class SignatureRecord(BaseModel):
    """21 CFR Part 11 compliant Electronic Signature artifact."""
    signature_id: str = Field(default_factory=lambda: f"SIG-{uuid.uuid4().hex[:8].upper()}")
    case_id: str
    user_id: str
    user_full_name: str
    user_title: str
    meaning: SignatureMeaning
    signed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    target_entity_type: str = Field(description="e.g. QualityCase, DraftArtifact, StateTransition")
    target_entity_id: str
    target_content_hash: str = Field(description="SHA-256 hash of the content being signed")
    signature_hash: str = Field(default="")

    def model_post_init(self, __context: Any) -> None:
        if not self.signature_hash:
            payload = f"{self.user_id}|{self.signed_at.isoformat()}|{self.meaning.value}|{self.target_content_hash}"
            self.signature_hash = compute_sha256(payload)


class Decision(BaseModel):
    """Human or policy-evaluated decision record."""
    decision_id: str = Field(default_factory=lambda: f"DEC-{uuid.uuid4().hex[:8].upper()}")
    case_id: str
    decision_type: str = Field(description="e.g. CLASSIFICATION_APPROVAL, ROOT_CAUSE_CONFIRMATION, OVERRIDE")
    action_class: ActionClass = Field(default=ActionClass.A4_CONTROLLED_GXP_ACTION)
    actor_type: AuthorType = Field(default=AuthorType.HUMAN)
    actor_id: str
    rationale: str
    signature_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StateTransition(BaseModel):
    """Immutable log of state machine movement."""
    transition_id: str = Field(default_factory=lambda: f"TRN-{uuid.uuid4().hex[:8].upper()}")
    case_id: str
    from_state: CaseState
    to_state: CaseState
    actor_type: AuthorType
    actor_id: str
    action_class: ActionClass
    policy_rule: str = Field(description="The deterministic policy rule permitting this transition")
    signature_id: Optional[str] = Field(default=None, description="Required for A4 transitions")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditLogEntry(BaseModel):
    """Append-only audit trail node with cryptographic forward hash-chaining."""
    entry_id: str = Field(default_factory=lambda: f"AUD-{uuid.uuid4().hex[:10].upper()}")
    sequence_number: int
    case_id: Optional[str] = None
    event_type: str = Field(description="e.g. EVENT_INGESTED, DRAFT_STAGED, SIGNATURE_APPLIED, STATE_CHANGED")
    entity_type: str
    entity_id: str
    actor_id: str
    actor_type: AuthorType
    data_snapshot: Dict[str, Any]
    data_hash: str = Field(default="")
    prev_hash: str = Field(default="0" * 64, description="Hash of previous entry, or 64 zeros for genesis")
    entry_hash: str = Field(default="")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_post_init(self, __context: Any) -> None:
        if not self.data_hash:
            self.data_hash = compute_sha256(self.data_snapshot)
        if not self.entry_hash:
            self.entry_hash = compute_audit_hash(
                prev_hash=self.prev_hash,
                timestamp=self.timestamp.isoformat(),
                event_type=self.event_type,
                entity_id=self.entity_id,
                actor_id=self.actor_id,
                data_hash=self.data_hash
            )
