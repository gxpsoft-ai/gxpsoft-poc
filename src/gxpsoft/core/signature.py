"""21 CFR Part 11 compliant Electronic Signature generation and verification service."""

from datetime import datetime, timezone
from typing import Dict, Optional

from gxpsoft.core.crypto import compute_sha256
from gxpsoft.core.policy import QUALIFIED_USERS, AUTHORIZED_SIGNER_ROLES
from gxpsoft.core.repository import repo
from gxpsoft.models.audit import SignatureRecord
from gxpsoft.models.enums import AuthorType, SignatureMeaning


# Mock user credential registry for POC (in production: SAML/OIDC + MFA)
MOCK_USER_CREDENTIALS: Dict[str, str] = {
    "USER-QA-LEAD-01": "LeadPass2026!",
    "USER-QA-MGR-01": "MgrPass2026!",
    "USER-DIR-QA-01": "DirPass2026!",
    "USER-OPERATOR-01": "OpPass2026!",
}


class SignatureVerificationError(Exception):
    """Raised when signature verification or credentials fail."""
    pass


class SignatureService:
    """Manages creation, verification, and audit of 21 CFR Part 11 electronic signatures."""

    @staticmethod
    def create_signature(
        case_id: str,
        user_id: str,
        password_or_pin: str,
        meaning: SignatureMeaning,
        target_entity_type: str,
        target_entity_id: str,
        target_content_hash: str
    ) -> SignatureRecord:
        """Authenticates user and generates a legally binding electronic signature record."""
        # 1. Authenticate user credentials
        expected_pass = MOCK_USER_CREDENTIALS.get(user_id)
        if not expected_pass or expected_pass != password_or_pin:
            raise SignatureVerificationError("Invalid username or password/PIN for electronic signature.")

        # 2. Verify user qualification in registry
        user_qual = QUALIFIED_USERS.get(user_id)
        if not user_qual or not user_qual.is_active:
            raise SignatureVerificationError(f"User '{user_id}' is not an active authorized user.")

        # 3. Create SignatureRecord
        signed_at = datetime.now(timezone.utc)
        sig = SignatureRecord(
            case_id=case_id,
            user_id=user_id,
            user_full_name=user_qual.full_name,
            user_title=user_qual.roles[0],
            meaning=meaning,
            signed_at=signed_at,
            target_entity_type=target_entity_type,
            target_entity_id=target_entity_id,
            target_content_hash=target_content_hash
        )

        # 4. Persist in repository
        repo.add_signature(sig)

        # 5. Append to Audit Ledger
        repo.audit_ledger.append(
            event_type="SIGNATURE_APPLIED",
            entity_type="SignatureRecord",
            entity_id=sig.signature_id,
            actor_id=user_id,
            actor_type=AuthorType.HUMAN,
            data_snapshot=sig.model_dump(mode="json"),
            case_id=case_id,
            timestamp=signed_at
        )

        return sig

    @staticmethod
    def verify_signature(signature_id: str, expected_content_hash: str) -> bool:
        """Verifies that a signature exists and matches the target content hash."""
        sig = repo.get_signature(signature_id)
        if not sig:
            return False
        return sig.target_content_hash == expected_content_hash
