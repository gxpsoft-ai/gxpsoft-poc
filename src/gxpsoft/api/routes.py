"""REST API routes for GxP events, state transitions, signatures, and audit trails."""

from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from gxpsoft.core.policy import PolicyViolationError
from gxpsoft.core.repository import repo
from gxpsoft.core.signature import SignatureService, SignatureVerificationError
from gxpsoft.core.state_machine import CaseStateMachine, InvalidTransitionError
from gxpsoft.ingestion.service import DuplicateEventError, IngestionService
from gxpsoft.models.audit import AuditLogEntry, SignatureRecord
from gxpsoft.models.case import QualityCase
from gxpsoft.models.enums import AuthorType, CaseSeverity, CaseState, SignatureMeaning
from gxpsoft.models.event import QualityEvent
from gxpsoft.review.packet_builder import DecisionPacket, DecisionPacketBuilder
from gxpsoft.review.service import HumanReviewService, OverrideRationaleRequiredError

router = APIRouter(prefix="/api/v1")
ui_router = APIRouter()


class SignRequest(BaseModel):
    case_id: str
    user_id: str
    password_or_pin: str
    meaning: SignatureMeaning
    target_entity_type: str
    target_entity_id: str
    target_content_hash: str


class TransitionRequest(BaseModel):
    to_state: CaseState
    actor_id: str
    actor_type: AuthorType
    signature_id: Optional[str] = None
    rationale: Optional[str] = None


class IngestResponse(BaseModel):
    event: QualityEvent
    case: Optional[QualityCase] = None


class AuditTrailResponse(BaseModel):
    case_id: Optional[str]
    entry_count: int
    integrity_verified: bool
    entries: List[AuditLogEntry]


class RedlineRequest(BaseModel):
    user_id: str
    updated_structured_content: Optional[Dict[str, Any]] = None
    severity_override: Optional[CaseSeverity] = None
    override_rationale: Optional[str] = None


class ApproveAndSignRequest(BaseModel):
    user_id: str
    password_or_pin: str
    meaning: SignatureMeaning
    rationale: str


class ApproveAndSignResponse(BaseModel):
    case: QualityCase
    signature: SignatureRecord


@router.post("/events/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_event(payload: Dict[str, Any]) -> IngestResponse:
    """Ingests a raw operational event payload (MES, LIMS, ERP)."""
    try:
        event, case = IngestionService.ingest_event(payload)
        return IngestResponse(event=event, case=case)
    except DuplicateEventError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(e), "existing_event_id": e.existing_event.event_id}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to ingest event: {str(e)}"
        )


@router.get("/cases", response_model=List[QualityCase])
async def list_cases() -> List[QualityCase]:
    """Lists all active QualityCases."""
    return repo.list_cases()


@router.get("/cases/{case_id}", response_model=QualityCase)
async def get_case(case_id: str) -> QualityCase:
    """Retrieves a single QualityCase by ID."""
    case = repo.get_case(case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"QualityCase '{case_id}' not found."
        )
    return case


@router.get("/cases/{case_id}/decision-packet", response_model=DecisionPacket)
async def get_decision_packet(case_id: str) -> DecisionPacket:
    """Compiles the structured Decision Packet for human review ('QMS opens the human')."""
    try:
        return DecisionPacketBuilder.build_packet(case_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/cases/{case_id}/review/redline", response_model=QualityCase)
async def record_redline(case_id: str, req: RedlineRequest) -> QualityCase:
    """Records human edits and severity overrides with mandatory rationale."""
    try:
        return HumanReviewService.record_redline(
            case_id=case_id,
            user_id=req.user_id,
            updated_structured_content=req.updated_structured_content,
            severity_override=req.severity_override,
            override_rationale=req.override_rationale
        )
    except OverrideRationaleRequiredError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/cases/{case_id}/review/approve-and-sign", response_model=ApproveAndSignResponse)
async def approve_and_sign(case_id: str, req: ApproveAndSignRequest) -> ApproveAndSignResponse:
    """Authenticates user, applies 21 CFR Part 11 e-signature, and transitions state."""
    try:
        case, sig = HumanReviewService.approve_and_sign(
            case_id=case_id,
            user_id=req.user_id,
            password_or_pin=req.password_or_pin,
            meaning=req.meaning,
            rationale=req.rationale
        )
        return ApproveAndSignResponse(case=case, signature=sig)
    except SignatureVerificationError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except PolicyViolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/signatures/sign", response_model=SignatureRecord, status_code=status.HTTP_201_CREATED)
async def create_signature(req: SignRequest) -> SignatureRecord:
    """Authenticates and executes a 21 CFR Part 11 Electronic Signature."""
    try:
        sig = SignatureService.create_signature(
            case_id=req.case_id,
            user_id=req.user_id,
            password_or_pin=req.password_or_pin,
            meaning=req.meaning,
            target_entity_type=req.target_entity_type,
            target_entity_id=req.target_entity_id,
            target_content_hash=req.target_content_hash
        )
        return sig
    except SignatureVerificationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/cases/{case_id}/transition", response_model=QualityCase)
async def transition_case(case_id: str, req: TransitionRequest) -> QualityCase:
    """Executes a validated deterministic state transition."""
    try:
        case = CaseStateMachine.transition(
            case_id=case_id,
            to_state=req.to_state,
            actor_id=req.actor_id,
            actor_type=req.actor_type,
            signature_id=req.signature_id,
            rationale=req.rationale
        )
        return case
    except PolicyViolationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "PolicyViolationError",
                "message": e.message,
                "action_class": e.action_class.value,
                "actor_id": e.actor_id
            }
        )
    except InvalidTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "InvalidTransitionError", "message": str(e)}
        )


@router.get("/cases/{case_id}/audit-trail", response_model=AuditTrailResponse)
async def get_audit_trail(case_id: str) -> AuditTrailResponse:
    """Retrieves the complete cryptographic audit trail with hash chain verification."""
    case = repo.get_case(case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"QualityCase '{case_id}' not found."
        )

    entries = [e for e in repo.audit_ledger.entries if e.case_id == case_id or e.case_id is None]
    is_valid = repo.audit_ledger.verify_integrity()

    return AuditTrailResponse(
        case_id=case_id,
        entry_count=len(entries),
        integrity_verified=is_valid,
        entries=entries
    )


# UI Routes
@ui_router.get("/ui/case/{case_id}", response_class=HTMLResponse)
async def serve_case_ui(case_id: str) -> HTMLResponse:
    """Serves the interactive decision packet review console."""
    html_path = Path(__file__).parent.parent / "ui" / "dashboard.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Dashboard UI not found</h1>", status_code=404)
