"""Policy engine for deterministic RBAC/ABAC and Action Class (A0-A5) enforcement."""

from typing import List, Optional, Set
from pydantic import BaseModel

from gxpsoft.models.enums import ActionClass, AuthorType, CaseSeverity, CaseState


class PolicyViolationError(Exception):
    """Exception raised when an action violates GxP autonomy or qualification policy."""
    def __init__(self, message: str, action_class: ActionClass, actor_id: str, actor_type: AuthorType):
        super().__init__(message)
        self.message = message
        self.action_class = action_class
        self.actor_id = actor_id
        self.actor_type = actor_type


class UserQualification(BaseModel):
    """User profile and GxP role qualification."""
    user_id: str
    full_name: str
    roles: List[str]
    is_active: bool = True
    authorized_sites: List[str] = ["SITE-SF-01"]


# Seed qualified users for the POC environment
QUALIFIED_USERS = {
    "USER-QA-LEAD-01": UserQualification(
        user_id="USER-QA-LEAD-01",
        full_name="Jane Doe",
        roles=["QA_LEAD", "INVESTIGATOR"],
    ),
    "USER-QA-MGR-01": UserQualification(
        user_id="USER-QA-MGR-01",
        full_name="Sarah Connor",
        roles=["QA_MANAGER", "APPROVER"],
    ),
    "USER-DIR-QA-01": UserQualification(
        user_id="USER-DIR-QA-01",
        full_name="Dr. Marcus Vance",
        roles=["DIRECTOR_QA", "FINAL_DISPOSITION"],
    ),
    "USER-OPERATOR-01": UserQualification(
        user_id="USER-OPERATOR-01",
        full_name="John Technician",
        roles=["OPERATOR"],  # Not qualified to sign GxP approvals
    ),
}

# Roles permitted to sign A4 Controlled GxP Actions
AUTHORIZED_SIGNER_ROLES: Set[str] = {"QA_LEAD", "QA_MANAGER", "DIRECTOR_QA"}


class PolicyEngine:
    """Evaluates regulatory guardrails and deterministic transition rules."""

    @staticmethod
    def validate_action(
        action_class: ActionClass,
        actor_type: AuthorType,
        actor_id: str,
        target_state: Optional[CaseState] = None,
        severity: Optional[CaseSeverity] = None,
        signature_id: Optional[str] = None
    ) -> bool:
        """Validates whether the requested action is permitted under GxP policy.
        
        Raises PolicyViolationError if unauthorized.
        """
        # Rule 1: A5 Prohibited actions are never permitted
        if action_class == ActionClass.A5_PROHIBITED:
            raise PolicyViolationError(
                message=f"Action is classified as A5_PROHIBITED and cannot be executed.",
                action_class=action_class,
                actor_id=actor_id,
                actor_type=actor_type
            )

        # Rule 2: Agents are strictly prohibited from A4 Controlled GxP Actions
        if action_class == ActionClass.A4_CONTROLLED_GXP_ACTION:
            if actor_type == AuthorType.AGENT:
                raise PolicyViolationError(
                    message=f"AI Agent '{actor_id}' is strictly prohibited from executing A4 Controlled GxP Actions.",
                    action_class=action_class,
                    actor_id=actor_id,
                    actor_type=actor_type
                )
            
            # Rule 3: A4 Actions require human actor and a valid electronic signature ID
            if actor_type != AuthorType.HUMAN:
                raise PolicyViolationError(
                    message=f"A4 Controlled GxP Actions require a qualified HUMAN actor.",
                    action_class=action_class,
                    actor_id=actor_id,
                    actor_type=actor_type
                )

            if not signature_id:
                raise PolicyViolationError(
                    message=f"A4 Controlled GxP Action for state '{target_state}' requires an Electronic Signature.",
                    action_class=action_class,
                    actor_id=actor_id,
                    actor_type=actor_type
                )

            # Rule 4: Human must be a qualified user with appropriate signing role
            user = QUALIFIED_USERS.get(actor_id)
            if not user or not user.is_active:
                raise PolicyViolationError(
                    message=f"User '{actor_id}' is not an active qualified GxP user in the system registry.",
                    action_class=action_class,
                    actor_id=actor_id,
                    actor_type=actor_type
                )

            if not any(role in AUTHORIZED_SIGNER_ROLES for role in user.roles):
                raise PolicyViolationError(
                    message=f"User '{actor_id}' lacks required QA signing roles ({AUTHORIZED_SIGNER_ROLES}). User roles: {user.roles}",
                    action_class=action_class,
                    actor_id=actor_id,
                    actor_type=actor_type
                )

        return True
