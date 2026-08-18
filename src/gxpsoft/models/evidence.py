"""Evidence and Claim models for verifiable quality reasoning and citation lineage."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid

from gxpsoft.models.enums import AuthorType
from gxpsoft.core.crypto import compute_sha256


class EvidenceObject(BaseModel):
    """Immutable evidence artifact registered in the Evidence Graph."""
    evidence_id: str = Field(default_factory=lambda: f"EVD-{uuid.uuid4().hex[:8].upper()}")
    uri: str = Field(description="Storage URI or file path")
    title: str
    doc_type: str = Field(description="e.g. SOP, BATCH_RECORD, CALIBRATION_LOG, TRAINING_RECORD, PRIOR_DEVIATION")
    version: str = Field(default="1.0")
    source_system: str = Field(description="e.g. DMS, CMMS, LMS, MES")
    content_hash: str = Field(default="", description="SHA-256 hash of the exact evidence content")
    raw_content: Optional[str] = Field(default=None, description="Full text or excerpt for retrieval")
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if self.raw_content and not self.content_hash:
            self.content_hash = compute_sha256(self.raw_content)


class ClaimEvidenceLink(BaseModel):
    """Discrete citation mapping a Claim to an EvidenceObject."""
    link_id: str = Field(default_factory=lambda: f"LNK-{uuid.uuid4().hex[:8].upper()}")
    evidence_id: str
    locator: str = Field(description="Exact location, e.g., 'Section 4.2.1, Line 14' or 'Page 2, Table 1'")
    quote_text: str = Field(description="Exact excerpt quote from the source evidence")
    relevance_score: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    match_method: str = Field(default="EXACT_EXTRACTION", description="e.g. EXACT_EXTRACTION, VECTOR_RAG, HYBRID")


class Claim(BaseModel):
    """Atomic, reviewable assertion produced by an agent or human."""
    claim_id: str = Field(default_factory=lambda: f"CLM-{uuid.uuid4().hex[:8].upper()}")
    case_id: str
    claim_text: str = Field(description="The specific statement/assertion being made")
    author_type: AuthorType = Field(default=AuthorType.AGENT)
    author_id: str = Field(description="Agent name/version or user ID")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Routing/triage confidence score")
    uncertainty_notes: Optional[str] = Field(default=None, description="Explicit statement of what is unknown or unverified")
    alternative_explanations: List[str] = Field(default_factory=list, description="Contending hypotheses or caveats")
    citations: List[ClaimEvidenceLink] = Field(default_factory=list, description="Direct supporting evidence links")
    is_verified_by_human: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
