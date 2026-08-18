"""Decision Packet builder compiling cases, drafts, atomic claims, and source evidence for human review."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from gxpsoft.core.policy import AUTHORIZED_SIGNER_ROLES, QUALIFIED_USERS
from gxpsoft.core.repository import repo
from gxpsoft.models.agent_run import DraftArtifact
from gxpsoft.models.case import QualityCase
from gxpsoft.models.enums import ActionClass, CaseState, SignatureMeaning
from gxpsoft.models.event import QualityEvent
from gxpsoft.models.evidence import Claim, EvidenceObject


class HydratedCitation(BaseModel):
    """Citation with full source evidence context."""
    link_id: str
    evidence_id: str
    doc_title: str
    doc_type: str
    locator: str
    quote_text: str
    source_uri: str
    relevance_score: float


class HydratedClaim(BaseModel):
    """Atomic claim with fully resolved citation evidence."""
    claim_id: str
    claim_text: str
    confidence: float
    uncertainty_notes: Optional[str] = None
    alternative_explanations: List[str] = Field(default_factory=list)
    citations: List[HydratedCitation] = Field(default_factory=list)
    is_verified_by_human: bool = False


class PolicyGateInfo(BaseModel):
    """Policy engine status and signing requirements."""
    action_class: ActionClass = ActionClass.A4_CONTROLLED_GXP_ACTION
    current_state: CaseState
    target_state: CaseState
    required_signature_meaning: SignatureMeaning
    authorized_roles: List[str]
    is_human_signature_mandatory: bool = True


class DecisionPacket(BaseModel):
    """Complete structured decision packet for human review ('QMS opens the human')."""
    case_id: str
    case: QualityCase
    initial_event: Optional[QualityEvent] = None
    latest_draft: Optional[DraftArtifact] = None
    claims: List[HydratedClaim] = Field(default_factory=list)
    policy_gate: PolicyGateInfo
    available_actions: List[str] = ["ACCEPT_AND_SIGN", "EDIT_INLINE", "OVERRIDE_SEVERITY", "REJECT"]


class DecisionPacketBuilder:
    """Compiles the complete context required for qualified human decision making."""

    @staticmethod
    def build_packet(case_id: str) -> DecisionPacket:
        """Assembles a DecisionPacket for the given case."""
        case = repo.get_case(case_id)
        if not case:
            raise ValueError(f"QualityCase '{case_id}' not found.")

        # 1. Fetch initial triggering event
        event = repo.get_event(case.initial_event_id)

        # 2. Fetch latest draft artifact
        drafts = repo.get_drafts_for_case(case_id)
        latest_draft = drafts[-1] if drafts else None

        # 3. Hydrate claims and evidence citations
        claims = repo.get_claims_for_case(case_id)
        hydrated_claims: List[HydratedClaim] = []

        for c in claims:
            hydrated_citations: List[HydratedCitation] = []
            for cite in c.citations:
                ev_obj = repo.get_evidence(cite.evidence_id)
                doc_title = ev_obj.title if ev_obj else "Controlled Document"
                doc_type = ev_obj.doc_type if ev_obj else "DOCUMENT"
                source_uri = ev_obj.uri if ev_obj else ""

                hydrated_citations.append(
                    HydratedCitation(
                        link_id=cite.link_id,
                        evidence_id=cite.evidence_id,
                        doc_title=doc_title,
                        doc_type=doc_type,
                        locator=cite.locator,
                        quote_text=cite.quote_text,
                        source_uri=source_uri,
                        relevance_score=cite.relevance_score or 1.0
                    )
                )

            hydrated_claims.append(
                HydratedClaim(
                    claim_id=c.claim_id,
                    claim_text=c.claim_text,
                    confidence=c.confidence,
                    uncertainty_notes=c.uncertainty_notes,
                    alternative_explanations=c.alternative_explanations,
                    citations=hydrated_citations,
                    is_verified_by_human=c.is_verified_by_human
                )
            )

        # 4. Determine Policy Gate Information based on state
        if case.state in (CaseState.CONTAINMENT_PROPOSED, CaseState.EVIDENCE_ASSEMBLED, CaseState.CASE_CREATED):
            target_state = CaseState.HUMAN_CLASSIFICATION_APPROVED
            sig_meaning = SignatureMeaning.APPROVED_CLASSIFICATION
        elif case.state == CaseState.HUMAN_CLASSIFICATION_APPROVED:
            target_state = CaseState.ROOT_CAUSE_CONFIRMED
            sig_meaning = SignatureMeaning.APPROVED_ROOT_CAUSE
        elif case.state == CaseState.CAPA_DRAFTED:
            target_state = CaseState.CAPA_AUTHORIZED
            sig_meaning = SignatureMeaning.APPROVED_CAPA
        else:
            target_state = CaseState.CLOSED
            sig_meaning = SignatureMeaning.APPROVED_CLOSURE

        policy_gate = PolicyGateInfo(
            action_class=ActionClass.A4_CONTROLLED_GXP_ACTION,
            current_state=case.state,
            target_state=target_state,
            required_signature_meaning=sig_meaning,
            authorized_roles=list(AUTHORIZED_SIGNER_ROLES),
            is_human_signature_mandatory=True
        )

        return DecisionPacket(
            case_id=case_id,
            case=case,
            initial_event=event,
            latest_draft=latest_draft,
            claims=hydrated_claims,
            policy_gate=policy_gate
        )
