"""Quality Case model representing durable work objects across deviations, CAPAs, and complaints."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid

from gxpsoft.models.enums import CaseSeverity, CaseState, CaseType


class QualityCase(BaseModel):
    """Core durable Quality Case entity."""
    case_id: str = Field(default_factory=lambda: f"DEV-2026-{uuid.uuid4().hex[:6].upper()}")
    case_type: CaseType = Field(default=CaseType.DEVIATION)
    title: str
    description: str
    state: CaseState = Field(default=CaseState.SIGNAL_RECEIVED)
    severity: Optional[CaseSeverity] = None
    initial_event_id: str = Field(description="Foreign key linking to triggering QualityEvent")
    product_id: Optional[str] = None
    batch_id: Optional[str] = None
    site_id: str = Field(default="site-01")
    owner_id: Optional[str] = Field(default=None, description="Assigned human quality owner")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)
