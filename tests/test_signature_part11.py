"""Unit tests for 21 CFR Part 11 Electronic Signature Service."""

import pytest

from gxpsoft.core.crypto import compute_sha256
from gxpsoft.core.repository import repo
from gxpsoft.core.signature import SignatureService, SignatureVerificationError
from gxpsoft.models.enums import SignatureMeaning


def test_successful_electronic_signature() -> None:
    content = {"case_id": "DEV-2026-001", "root_cause": "Probe RTD-04B expired calibration"}
    content_hash = compute_sha256(content)

    sig = SignatureService.create_signature(
        case_id="DEV-2026-001",
        user_id="USER-QA-LEAD-01",
        password_or_pin="LeadPass2026!",
        meaning=SignatureMeaning.APPROVED_ROOT_CAUSE,
        target_entity_type="QualityCase",
        target_entity_id="DEV-2026-001",
        target_content_hash=content_hash,
    )

    assert sig.user_full_name == "Jane Doe"
    assert sig.user_title == "QA_LEAD"
    assert sig.meaning == SignatureMeaning.APPROVED_ROOT_CAUSE
    assert sig.target_content_hash == content_hash
    assert len(sig.signature_hash) == 64

    # Verify retrieval from repo
    stored = repo.get_signature(sig.signature_id)
    assert stored is not None
    assert stored.signature_id == sig.signature_id

    # Verify signature verification method
    assert SignatureService.verify_signature(sig.signature_id, content_hash) is True
    assert SignatureService.verify_signature(sig.signature_id, "tampered_hash") is False


def test_signature_fails_with_invalid_credentials() -> None:
    with pytest.raises(SignatureVerificationError) as exc_info:
        SignatureService.create_signature(
            case_id="DEV-2026-001",
            user_id="USER-QA-LEAD-01",
            password_or_pin="WrongPassword!",
            meaning=SignatureMeaning.APPROVED_ROOT_CAUSE,
            target_entity_type="QualityCase",
            target_entity_id="DEV-2026-001",
            target_content_hash="abc",
        )
    assert "Invalid username or password" in str(exc_info.value)
