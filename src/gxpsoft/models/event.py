"""Quality Event model representing raw operational signals (MES, LIMS, ERP, IoT)."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
import uuid

from gxpsoft.models.enums import EventStatus
from gxpsoft.core.crypto import compute_sha256


class QualityEvent(BaseModel):
    """Canonical operational event envelope."""
    event_id: str = Field(default_factory=lambda: f"EVT-{uuid.uuid4().hex[:12].upper()}")
    event_type: str = Field(description="e.g. MES_TEMP_EXCURSION, LIMS_OOS_ASSAY")
    source_system: str = Field(description="Source system e.g. MES, LIMS, SCADA, ERP")
    source_record_id: str = Field(description="Original ID in the source system")
    source_location: Optional[str] = Field(default=None, description="Physical site, line, or room")
    occurred_at: datetime = Field(description="Timestamp when event occurred in source system")
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: str = Field(default="1.0")
    payload: Dict[str, Any] = Field(description="Raw structured payload from source")
    payload_hash: str = Field(default="")
    idempotency_key: str = Field(description="Unique key to prevent duplicate processing")
    tenant_id: str = Field(default="default-tenant")
    site_id: str = Field(default="site-01")
    product_id: Optional[str] = None
    batch_id: Optional[str] = None
    status: EventStatus = Field(default=EventStatus.INGESTED)

    def model_post_init(self, __context: Any) -> None:
        if not self.payload_hash:
            self.payload_hash = compute_sha256(self.payload)
