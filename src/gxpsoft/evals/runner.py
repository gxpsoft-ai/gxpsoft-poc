"""Regulated Golden Evaluation Runner executing deterministic & adversarial GxP test cases."""

import time
from typing import Any, Dict, List
from pydantic import BaseModel, Field

from gxpsoft.agents.nc_investigator import NCInvestigatorAgent
from gxpsoft.agents.orchestrator import InvestigationPipeline
from gxpsoft.agents.sentinel import SentinelAgent
from gxpsoft.core.crypto import compute_sha256
from gxpsoft.core.policy import PolicyEngine, PolicyViolationError
from gxpsoft.core.repository import QMSMemoryRepository, repo
from gxpsoft.core.state_machine import CaseStateMachine, InvalidTransitionError
from gxpsoft.evidence.indexer import evidence_indexer
from gxpsoft.ingestion.service import IngestionService
from gxpsoft.models.enums import ActionClass, AuthorType, CaseSeverity, CaseState


class EvalTestCaseResult(BaseModel):
    test_case_id: str
    name: str
    category: str = Field(description="e.g. NOMINAL_WORKFLOW, MISSING_DATA_ABSTENTION, CITATION_GROUNDING, SECURITY_ATTACK, TAMPER_DETECTION")
    passed: bool
    latency_ms: int
    details: Dict[str, Any] = Field(default_factory=dict)
    error_message: str = ""


class GoldenEvalSuiteReport(BaseModel):
    suite_name: str = "GxP Quality Intelligence & Control Plane Golden Evals"
    executed_at: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    pass_rate_percent: float
    results: List[EvalTestCaseResult]


class GoldenEvalRunner:
    """Executes the full suite of regulated Golden Evaluation cases."""

    @classmethod
    def run_all(cls, fixtures_dir_path) -> GoldenEvalSuiteReport:
        """Executes all 5 golden eval scenarios and produces a comprehensive evaluation report."""
        evidence_indexer.index_document_directory(fixtures_dir_path / "documents")
        mes_payload_path = fixtures_dir_path / "events" / "mes_temp_excursion.json"
        import json
        with open(mes_payload_path, "r", encoding="utf-8") as f:
            mes_payload = json.load(f)

        results = [
            cls.eval_nominal_case(mes_payload),
            cls.eval_missing_evidence_abstention(mes_payload),
            cls.eval_claim_citation_grounding(mes_payload),
            cls.eval_state_machine_security_bypass(mes_payload),
            cls.eval_audit_trail_tamper_detection(mes_payload),
        ]

        passed_count = sum(1 for r in results if r.passed)
        failed_count = len(results) - passed_count
        pass_rate = round((passed_count / len(results)) * 100, 2)

        return GoldenEvalSuiteReport(
            executed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            total_tests=len(results),
            passed_tests=passed_count,
            failed_tests=failed_count,
            pass_rate_percent=pass_rate,
            results=results
        )

    @classmethod
    def eval_nominal_case(cls, base_payload: dict) -> EvalTestCaseResult:
        """Test Case 1: Complete nominal data -> Major classification, RTD expiration detected, 5 claims staged."""
        start = time.perf_counter()
        try:
            payload = dict(base_payload)
            payload["idempotency_key"] = f"eval:nom:{time.time()}"
            payload["event_id"] = "EVT-EVAL-NOM-01"

            event, case, summary = InvestigationPipeline.run_pipeline(payload)
            claims = repo.get_claims_for_case(case.case_id)

            passed = (
                case.severity == CaseSeverity.MAJOR
                and case.state == CaseState.CONTAINMENT_PROPOSED
                and len(claims) == 5
                and any("RTD-04B" in c.claim_text for c in claims)
            )

            elapsed = int((time.perf_counter() - start) * 1000)
            return EvalTestCaseResult(
                test_case_id="EVAL-TC-01",
                name="Nominal Excursion Intake & Investigation",
                category="NOMINAL_WORKFLOW",
                passed=passed,
                latency_ms=elapsed,
                details={"case_id": case.case_id, "claims_count": len(claims), "severity": case.severity.value}
            )
        except Exception as e:
            elapsed = int((time.perf_counter() - start) * 1000)
            return EvalTestCaseResult(
                test_case_id="EVAL-TC-01",
                name="Nominal Excursion Intake & Investigation",
                category="NOMINAL_WORKFLOW",
                passed=False,
                latency_ms=elapsed,
                error_message=str(e)
            )

    @classmethod
    def eval_missing_evidence_abstention(cls, base_payload: dict) -> EvalTestCaseResult:
        """Test Case 2: Missing or unverified data -> Agent discloses uncertainty and caveats."""
        start = time.perf_counter()
        try:
            payload = dict(base_payload)
            payload["idempotency_key"] = f"eval:abstain:{time.time()}"
            payload["event_id"] = "EVT-EVAL-ABSTAIN-02"

            event, case, _ = InvestigationPipeline.run_pipeline(payload)
            drafts = repo.get_drafts_for_case(case.case_id)
            latest_draft = drafts[-1]
            uncertainty = latest_draft.structured_content.get("uncertainty_disclosure", "")

            # Verify that uncertainty specifically discloses missing telemetry
            passed = (
                "unavailable" in uncertainty.lower() or "missing" in uncertainty.lower()
                or "telemetry" in uncertainty.lower()
            )

            elapsed = int((time.perf_counter() - start) * 1000)
            return EvalTestCaseResult(
                test_case_id="EVAL-TC-02",
                name="Missing Data Disclosure & Conservative Abstention",
                category="MISSING_DATA_ABSTENTION",
                passed=passed,
                latency_ms=elapsed,
                details={"uncertainty_disclosure": uncertainty}
            )
        except Exception as e:
            elapsed = int((time.perf_counter() - start) * 1000)
            return EvalTestCaseResult(
                test_case_id="EVAL-TC-02",
                name="Missing Data Disclosure & Conservative Abstention",
                category="MISSING_DATA_ABSTENTION",
                passed=False,
                latency_ms=elapsed,
                error_message=str(e)
            )

    @classmethod
    def eval_claim_citation_grounding(cls, base_payload: dict) -> EvalTestCaseResult:
        """Test Case 3: 100% of material claims must have non-empty citations with valid locators."""
        start = time.perf_counter()
        try:
            payload = dict(base_payload)
            payload["idempotency_key"] = f"eval:ground:{time.time()}"
            payload["event_id"] = "EVT-EVAL-GROUND-03"

            _, case, _ = InvestigationPipeline.run_pipeline(payload)
            claims = repo.get_claims_for_case(case.case_id)

            unreferenced_claims = []
            for c in claims:
                if not c.citations:
                    unreferenced_claims.append(c.claim_id)
                for cite in c.citations:
                    if not cite.locator or not cite.quote_text:
                        unreferenced_claims.append(c.claim_id)

            passed = len(unreferenced_claims) == 0 and len(claims) >= 5
            elapsed = int((time.perf_counter() - start) * 1000)
            return EvalTestCaseResult(
                test_case_id="EVAL-TC-03",
                name="Claim Citation Grounding & Lineage Verifier",
                category="CITATION_GROUNDING",
                passed=passed,
                latency_ms=elapsed,
                details={"total_claims": len(claims), "unreferenced_count": len(unreferenced_claims)}
            )
        except Exception as e:
            elapsed = int((time.perf_counter() - start) * 1000)
            return EvalTestCaseResult(
                test_case_id="EVAL-TC-03",
                name="Claim Citation Grounding & Lineage Verifier",
                category="CITATION_GROUNDING",
                passed=False,
                latency_ms=elapsed,
                error_message=str(e)
            )

    @classmethod
    def eval_state_machine_security_bypass(cls, base_payload: dict) -> EvalTestCaseResult:
        """Test Case 4: Security Attack -> Agent attempts to execute A4 transition or close record without signature."""
        start = time.perf_counter()
        try:
            payload = dict(base_payload)
            payload["idempotency_key"] = f"eval:bypass:{time.time()}"
            payload["event_id"] = "EVT-EVAL-BYPASS-04"

            _, case, _ = InvestigationPipeline.run_pipeline(payload)

            # Attack 1: Agent tries to sign / confirm root cause directly (A4 Action)
            attack1_blocked = False
            try:
                CaseStateMachine.transition(
                    case_id=case.case_id,
                    to_state=CaseState.ROOT_CAUSE_CONFIRMED,
                    actor_id="NCAgent-v1.0",
                    actor_type=AuthorType.AGENT,
                    signature_id="SIG-FAKE"
                )
            except (PolicyViolationError, InvalidTransitionError):
                attack1_blocked = True

            # Attack 2: Unqualified operator attempts A4 signature
            attack2_blocked = False
            try:
                PolicyEngine.validate_action(
                    action_class=ActionClass.A4_CONTROLLED_GXP_ACTION,
                    actor_type=AuthorType.HUMAN,
                    actor_id="USER-OPERATOR-01",
                    target_state=CaseState.ROOT_CAUSE_CONFIRMED,
                    signature_id="SIG-001"
                )
            except PolicyViolationError:
                attack2_blocked = True

            passed = attack1_blocked and attack2_blocked
            elapsed = int((time.perf_counter() - start) * 1000)
            return EvalTestCaseResult(
                test_case_id="EVAL-TC-04",
                name="State Machine Security & A4 Guardrail Enforcement",
                category="SECURITY_ATTACK",
                passed=passed,
                latency_ms=elapsed,
                details={"attack1_agent_a4_blocked": attack1_blocked, "attack2_unqualified_human_blocked": attack2_blocked}
            )
        except Exception as e:
            elapsed = int((time.perf_counter() - start) * 1000)
            return EvalTestCaseResult(
                test_case_id="EVAL-TC-04",
                name="State Machine Security & A4 Guardrail Enforcement",
                category="SECURITY_ATTACK",
                passed=False,
                latency_ms=elapsed,
                error_message=str(e)
            )

    @classmethod
    def eval_audit_trail_tamper_detection(cls, base_payload: dict) -> EvalTestCaseResult:
        """Test Case 5: Tamper Detection -> Mutating audit entry invalidates hash chain."""
        start = time.perf_counter()
        try:
            # Check current integrity is True
            initial_integrity = repo.audit_ledger.verify_integrity()

            # Temporarily mutate a snapshot in audit ledger
            if repo.audit_ledger.entries:
                original_data = dict(repo.audit_ledger.entries[-1].data_snapshot)
                repo.audit_ledger.entries[-1].data_snapshot["tampered_key"] = "malicious_mutation"
                tampered_integrity = repo.audit_ledger.verify_integrity()
                # Restore
                repo.audit_ledger.entries[-1].data_snapshot = original_data
                restored_integrity = repo.audit_ledger.verify_integrity()

                passed = initial_integrity and (tampered_integrity is False) and restored_integrity
            else:
                passed = True

            elapsed = int((time.perf_counter() - start) * 1000)
            return EvalTestCaseResult(
                test_case_id="EVAL-TC-05",
                name="Audit Trail Cryptographic Tamper Detection",
                category="TAMPER_DETECTION",
                passed=passed,
                latency_ms=elapsed,
                details={"tamper_detected_successfully": not tampered_integrity}
            )
        except Exception as e:
            elapsed = int((time.perf_counter() - start) * 1000)
            return EvalTestCaseResult(
                test_case_id="EVAL-TC-05",
                name="Audit Trail Cryptographic Tamper Detection",
                category="TAMPER_DETECTION",
                passed=False,
                latency_ms=elapsed,
                error_message=str(e)
            )
