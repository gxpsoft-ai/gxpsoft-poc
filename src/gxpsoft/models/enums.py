"""Enumerations for GxP Quality Management System."""

from enum import Enum


class ActionClass(str, Enum):
    """Controlled autonomy action classes defined in the architecture blueprint."""
    A0_OBSERVE = "A0_OBSERVE"  # Autonomous, read-only, fully logged (read records, calculate trend)
    A1_ANNOTATE = "A1_ANNOTATE"  # Autonomous with reversible changes (add tags, link candidates)
    A2_PREPARE = "A2_PREPARE"  # Draft deviation, RCA, CAPA, redline (human review required before promotion)
    A3_EXECUTE_SUPPORT = "A3_EXECUTE_SUPPORT"  # Reversible support action (request evidence, notify reviewer)
    A4_CONTROLLED_GXP_ACTION = "A4_CONTROLLED_GXP_ACTION"  # Controlled GxP action (human approval + e-sig mandatory)
    A5_PROHIBITED = "A5_PROHIBITED"  # Technically impossible (bypass approval, simulate signature)


class CaseState(str, Enum):
    """Deterministic Quality Case lifecycle states."""
    SIGNAL_RECEIVED = "SIGNAL_RECEIVED"
    CASE_CREATED = "CASE_CREATED"
    EVIDENCE_ASSEMBLED = "EVIDENCE_ASSEMBLED"
    CONTAINMENT_PROPOSED = "CONTAINMENT_PROPOSED"
    HUMAN_CLASSIFICATION_APPROVED = "HUMAN_CLASSIFICATION_APPROVED"
    INVESTIGATION_DRAFTED = "INVESTIGATION_DRAFTED"
    ROOT_CAUSE_CONFIRMED = "ROOT_CAUSE_CONFIRMED"
    CAPA_DRAFTED = "CAPA_DRAFTED"
    CAPA_AUTHORIZED = "CAPA_AUTHORIZED"
    EFFECTIVENESS_VERIFIED = "EFFECTIVENESS_VERIFIED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"


class CaseSeverity(str, Enum):
    """Standard GxP risk severity classifications."""
    MINOR = "MINOR"
    MAJOR = "MAJOR"
    CRITICAL = "CRITICAL"


class CaseType(str, Enum):
    """Types of Quality Cases."""
    DEVIATION = "DEVIATION"
    NONCONFORMANCE = "NONCONFORMANCE"
    CAPA = "CAPA"
    COMPLAINT = "COMPLAINT"
    CHANGE_CONTROL = "CHANGE_CONTROL"
    AUDIT_FINDING = "AUDIT_FINDING"


class AuthorType(str, Enum):
    """Attribution of who generated a claim, record, or decision."""
    AGENT = "AGENT"
    HUMAN = "HUMAN"
    SYSTEM = "SYSTEM"


class SignatureMeaning(str, Enum):
    """21 CFR Part 11 compliant electronic signature meanings."""
    AUTHORED = "AUTHORED"
    REVIEWED = "REVIEWED"
    APPROVED_CLASSIFICATION = "APPROVED_CLASSIFICATION"
    APPROVED_ROOT_CAUSE = "APPROVED_ROOT_CAUSE"
    APPROVED_CAPA = "APPROVED_CAPA"
    APPROVED_CLOSURE = "APPROVED_CLOSURE"
    REJECTED = "REJECTED"


class EventStatus(str, Enum):
    """Processing status of an ingested raw event."""
    INGESTED = "INGESTED"
    NORMALIZED = "NORMALIZED"
    CASE_ATTACHED = "CASE_ATTACHED"
    DUPLICATE = "DUPLICATE"
    DISMISSED = "DISMISSED"
