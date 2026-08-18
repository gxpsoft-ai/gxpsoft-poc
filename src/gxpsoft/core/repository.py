"""Thread-safe in-memory repository for QMS entities, cases, signatures, and audit ledger."""

import threading
from typing import Dict, List, Optional

from gxpsoft.models.case import QualityCase
from gxpsoft.models.event import QualityEvent
from gxpsoft.models.audit import AuditLogEntry, SignatureRecord, StateTransition
from gxpsoft.models.evidence import Claim, EvidenceObject
from gxpsoft.models.agent_run import DraftArtifact
from gxpsoft.core.ledger import AuditLedger


class QMSMemoryRepository:
    """Thread-safe centralized repository for the QMS POC."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.events: Dict[str, QualityEvent] = {}
        self.idempotency_index: Dict[str, str] = {}  # idempotency_key -> event_id
        self.cases: Dict[str, QualityCase] = {}
        self.evidence: Dict[str, EvidenceObject] = {}
        self.claims: Dict[str, Claim] = {}
        self.drafts: Dict[str, DraftArtifact] = {}
        self.signatures: Dict[str, SignatureRecord] = {}
        self.transitions: List[StateTransition] = []
        self.audit_ledger = AuditLedger()

    def add_event(self, event: QualityEvent) -> QualityEvent:
        with self._lock:
            self.events[event.event_id] = event
            self.idempotency_index[event.idempotency_key] = event.event_id
            return event

    def get_event(self, event_id: str) -> Optional[QualityEvent]:
        with self._lock:
            return self.events.get(event_id)

    def find_event_by_idempotency_key(self, key: str) -> Optional[QualityEvent]:
        with self._lock:
            event_id = self.idempotency_index.get(key)
            if event_id:
                return self.events.get(event_id)
            return None

    def add_case(self, case: QualityCase) -> QualityCase:
        with self._lock:
            self.cases[case.case_id] = case
            return case

    def get_case(self, case_id: str) -> Optional[QualityCase]:
        with self._lock:
            return self.cases.get(case_id)

    def update_case(self, case: QualityCase) -> QualityCase:
        with self._lock:
            self.cases[case.case_id] = case
            return case

    def list_cases(self) -> List[QualityCase]:
        with self._lock:
            return list(self.cases.values())

    def add_signature(self, sig: SignatureRecord) -> SignatureRecord:
        with self._lock:
            self.signatures[sig.signature_id] = sig
            return sig

    def get_signature(self, signature_id: str) -> Optional[SignatureRecord]:
        with self._lock:
            return self.signatures.get(signature_id)

    def add_transition(self, transition: StateTransition) -> StateTransition:
        with self._lock:
            self.transitions.append(transition)
            return transition

    def get_transitions_for_case(self, case_id: str) -> List[StateTransition]:
        with self._lock:
            return [t for t in self.transitions if t.case_id == case_id]

    def add_evidence(self, evidence: EvidenceObject) -> EvidenceObject:
        with self._lock:
            self.evidence[evidence.evidence_id] = evidence
            return evidence

    def get_evidence(self, evidence_id: str) -> Optional[EvidenceObject]:
        with self._lock:
            return self.evidence.get(evidence_id)

    def add_claim(self, claim: Claim) -> Claim:
        with self._lock:
            self.claims[claim.claim_id] = claim
            return claim

    def get_claims_for_case(self, case_id: str) -> List[Claim]:
        with self._lock:
            return [c for c in self.claims.values() if c.case_id == case_id]

    def add_draft(self, draft: DraftArtifact) -> DraftArtifact:
        with self._lock:
            self.drafts[draft.artifact_id] = draft
            return draft

    def get_drafts_for_case(self, case_id: str) -> List[DraftArtifact]:
        with self._lock:
            return [d for d in self.drafts.values() if d.case_id == case_id]


# Singleton instance for application runtime
repo = QMSMemoryRepository()
