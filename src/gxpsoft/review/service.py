"""Human review and electronic signing service handling redlines, overrides, and approvals."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from gxpsoft.core.crypto import compute_sha256
from gxpsoft.core.observability import observe
from gxpsoft.core.policy import QUALIFIED_USERS
from gxpsoft.core.repository import repo
from gxpsoft.core.signature import SignatureService
from gxpsoft.core.state_machine import CaseStateMachine
from gxpsoft.models.audit import SignatureRecord
from gxpsoft.models.case import QualityCase
from gxpsoft.models.enums import AuthorType, CaseSeverity, CaseState, SignatureMeaning


class OverrideRationaleRequiredError(Exception):
    """Raised when a human reviewer overrides agent recommendations without mandatory justification."""
    pass


class HumanReviewService:
    """Service handling human redlines, severity overrides, and 21 CFR Part 11 e-signatures."""

    @staticmethod
    def record_redline(
        case_id: str,
        user_id: str,
        updated_structured_content: Optional[Dict[str, Any]] = None,
        severity_override: Optional[CaseSeverity] = None,
        override_rationale: Optional[str] = None
    ) -> QualityCase:
        """Applies human edits and overrides with mandatory rationale tracking."""
        case = repo.get_case(case_id)
        if not case:
            raise ValueError(f"QualityCase '{case_id}' not found.")

        # If human overrides severity, require explicit justification
        if severity_override and severity_override != case.severity:
            if not override_rationale or len(override_rationale.strip()) < 10:
                raise OverrideRationaleRequiredError(
                    f"Overriding severity from {case.severity} to {severity_override} "
                    "requires a detailed justification rationale (minimum 10 characters)."
                )
            old_severity = case.severity
            case.severity = severity_override
            case.metadata["severity_override"] = {
                "overridden_by": user_id,
                "previous_severity": old_severity.value if old_severity else None,
                "new_severity": severity_override.value,
                "rationale": override_rationale,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        # Update draft artifact if modified
        drafts = repo.get_drafts_for_case(case_id)
        if drafts and updated_structured_content:
            latest_draft = drafts[-1]
            latest_draft.structured_content = updated_structured_content
            latest_draft.status = "MODIFIED_BY_HUMAN"

        case.updated_at = datetime.now(timezone.utc)
        repo.update_case(case)

        repo.audit_ledger.append(
            event_type="HUMAN_REDLINE_RECORDED",
            entity_type="QualityCase",
            entity_id=case_id,
            actor_id=user_id,
            actor_type=AuthorType.HUMAN,
            data_snapshot={
                "case_id": case_id,
                "severity_override": severity_override.value if severity_override else None,
                "override_rationale": override_rationale,
                "has_draft_updates": bool(updated_structured_content)
            },
            case_id=case_id
        )

        return case

    @staticmethod
    @observe(name="HumanReviewService.approve_and_sign", as_type="guardrail")
    def approve_and_sign(
        case_id: str,
        user_id: str,
        password_or_pin: str,
        meaning: SignatureMeaning,
        rationale: str
    ) -> Tuple[QualityCase, SignatureRecord]:
        """Atomically authenticates user, applies Part 11 e-signature, and executes state transition."""
        case = repo.get_case(case_id)
        if not case:
            raise ValueError(f"QualityCase '{case_id}' not found.")

        # Determine target state based on current state & meaning
        if case.state in (CaseState.CONTAINMENT_PROPOSED, CaseState.EVIDENCE_ASSEMBLED, CaseState.CASE_CREATED):
            target_state = CaseState.HUMAN_CLASSIFICATION_APPROVED
        elif case.state in (CaseState.INVESTIGATION_DRAFTED, CaseState.HUMAN_CLASSIFICATION_APPROVED):
            target_state = CaseState.ROOT_CAUSE_CONFIRMED
        elif case.state in (CaseState.CAPA_DRAFTED, CaseState.ROOT_CAUSE_CONFIRMED):
            target_state = CaseState.CAPA_AUTHORIZED
        elif case.state in (CaseState.EFFECTIVENESS_VERIFIED, CaseState.CAPA_AUTHORIZED):
            target_state = CaseState.CLOSED
        else:
            target_state = CaseState.CLOSED

        # 1. Compute target content hash for cryptographic signature
        drafts = repo.get_drafts_for_case(case_id)
        latest_draft = drafts[-1] if drafts else None
        target_payload = {
            "case_id": case.case_id,
            "state": case.state.value,
            "severity": case.severity.value if case.severity else None,
            "draft_content": latest_draft.structured_content if latest_draft else {},
            "rationale": rationale
        }
        content_hash = compute_sha256(target_payload)

        # 2. Issue 21 CFR Part 11 Electronic Signature
        sig = SignatureService.create_signature(
            case_id=case_id,
            user_id=user_id,
            password_or_pin=password_or_pin,
            meaning=meaning,
            target_entity_type="DecisionPacket",
            target_entity_id=case_id,
            target_content_hash=content_hash
        )

        # 3. Execute deterministic FSM state transition
        updated_case = CaseStateMachine.transition(
            case_id=case_id,
            to_state=target_state,
            actor_id=user_id,
            actor_type=AuthorType.HUMAN,
            signature_id=sig.signature_id,
            rationale=rationale
        )

        return updated_case, sig
