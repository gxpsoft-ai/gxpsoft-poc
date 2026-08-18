"""Structured output and dependency schemas for Pydantic AI agents."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from gxpsoft.models.enums import CaseSeverity


# ==========================================
# 1. Sentinel Agent Schemas
# ==========================================

class SentinelTriageOutput(BaseModel):
    """Structured output from Sentinel Agent triage evaluation."""
    severity: CaseSeverity = Field(description="Assigned case severity: MINOR, MAJOR, or CRITICAL")
    rationale: str = Field(description="Deterministic scientific/compliance rationale for the triage decision")
    sop_references: List[str] = Field(default_factory=list, description="Referenced SOP identifiers, e.g. SOP-PRC-042")


# ==========================================
# 2. NC Investigator Agent Schemas
# ==========================================

class ClaimCitationSchema(BaseModel):
    """Citation linking an atomic claim to an exact evidence document."""
    evidence_id: str
    locator: str
    quote_text: str
    relevance_score: float = Field(default=1.0, ge=0.0, le=1.0)
    match_method: str = Field(default="EXACT_EXTRACTION")


class AtomicClaimSchema(BaseModel):
    """Atomic factual claim with confidence and audit citation grounding."""
    claim_text: str
    confidence: float = Field(default=0.95, ge=0.0, le=1.0)
    uncertainty_notes: str = Field(default="None.")
    citations: List[ClaimCitationSchema] = Field(default_factory=list)


class FiveWhyEntry(BaseModel):
    """Single level in 5-Why root cause analysis tree."""
    level: int = Field(ge=1, le=5)
    statement: str


class HypothesisItem(BaseModel):
    """Ranked root cause hypothesis."""
    hypothesis_id: str
    rank: int
    title: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    evidence_summary: str


class ContainmentPlanSchema(BaseModel):
    """Immediate containment actions staged for QA review."""
    immediate_actions: List[str]


class NCInvestigationOutput(BaseModel):
    """Structured output from Nonconformance & Deviation Investigation Agent."""
    title: str
    severity_recommendation: str = Field(default="MAJOR")
    event_summary: str
    containment_plan: ContainmentPlanSchema
    five_why_analysis: List[Dict[str, str]]
    ranked_hypotheses: List[HypothesisItem]
    uncertainty_disclosure: str
    claims: List[AtomicClaimSchema]


# ==========================================
# 3. CAPA Generator Agent Schemas
# ==========================================

class CAPAActionItemSchema(BaseModel):
    """Single corrective or preventive action item in CAPA plan."""
    action_id: str
    action_type: str = Field(description="CORRECTIVE_IMMEDIATE, CORRECTIVE_SCOPE_ASSESSMENT, PREVENTIVE_SYSTEMIC, PREVENTIVE_TRAINING")
    title: str
    description: str
    target_owner: str
    due_days: int
    linked_root_cause: str


class EffectivenessPlanSchema(BaseModel):
    """Quantifiable post-CAPA effectiveness verification criteria."""
    verification_metric: str
    target_consecutive_clean_batches: int = Field(default=5)
    verification_window_days: int = Field(default=60)
    assigned_evaluator: str = Field(default="USER-QA-MGR-01")
    recurrence_action: str


class CAPAPlanOutput(BaseModel):
    """Structured output from CAPA Generator Agent."""
    title: str
    capa_actions: List[CAPAActionItemSchema]
    effectiveness_plan: EffectivenessPlanSchema
    status: str = Field(default="STAGED_FOR_QA_MANAGEMENT_AUTHORIZATION")
