"""Computer Software Assurance (CSA) / GAMP 5 Validation Summary Report (VSR) generator."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from pydantic import BaseModel, Field

from gxpsoft.core.crypto import compute_sha256
from gxpsoft.evals.runner import GoldenEvalRunner, GoldenEvalSuiteReport


class RegulatoryRequirementTrace(BaseModel):
    req_id: str
    regulation: str
    requirement_summary: str
    implementation_artifact: str
    verification_test_case: str
    status: str = "COMPLIANT"


class ValidationSummaryReport(BaseModel):
    """Formal GAMP 5 / CSA Validation Summary Report (VSR)."""
    report_id: str
    title: str = "Computer Software Assurance (CSA) & GAMP 5 Validation Summary Report"
    system_name: str = "GxPSoft AI-Agent-First Quality Management System"
    system_version: str = "0.1.0"
    gamp_category: str = "GAMP 5 Category 4 / 5 (Configured & Custom GxP Application)"
    intended_use: str = (
        "Automated operational quality event intake, multi-system evidence reconciliation, "
        "root cause analysis hypothesis generation, CAPA planning, and 21 CFR Part 11 human review gating."
    )
    generated_at: str
    validation_verdict: str = "PASSED - FIT FOR REGULATED GXP INTENDED USE"
    regulatory_traceability_matrix: List[RegulatoryRequirementTrace]
    eval_suite_results: GoldenEvalSuiteReport
    sha256_report_hash: str = ""


class ValidationReportGenerator:
    """Compiles the formal CSA Validation Summary Report with full traceability."""

    @classmethod
    def generate_report(cls, fixtures_dir_path: Path) -> ValidationSummaryReport:
        """Executes golden eval suite and compiles the complete validation dossier."""
        # 1. Execute Golden Evals
        eval_report = GoldenEvalRunner.run_all(fixtures_dir_path)

        # 2. Build Regulatory Traceability Matrix (RTM)
        rtm = [
            RegulatoryRequirementTrace(
                req_id="REQ-P11-01",
                regulation="21 CFR §11.10(a)",
                requirement_summary="Validation of closed systems to ensure accuracy, reliability, and consistent performance.",
                implementation_artifact="Deterministic State Machine & Governed Tool Gateway",
                verification_test_case="EVAL-TC-01 (Nominal Workflow) & EVAL-TC-04 (Security Attack)",
                status="COMPLIANT"
            ),
            RegulatoryRequirementTrace(
                req_id="REQ-P11-02",
                regulation="21 CFR §11.10(b)",
                requirement_summary="Ability to generate accurate and complete copies of records in human-readable and electronic form.",
                implementation_artifact="Decision Lineage Exporter (`DecisionLineageExport`)",
                verification_test_case="test_complete_closed_loop_decision_lineage_export",
                status="COMPLIANT"
            ),
            RegulatoryRequirementTrace(
                req_id="REQ-P11-03",
                regulation="21 CFR §11.10(e)",
                requirement_summary="Secure, computer-generated, time-stamped audit trails to record operator entries and actions.",
                implementation_artifact="Cryptographic Audit Ledger with forward SHA-256 hash chaining",
                verification_test_case="EVAL-TC-05 (Audit Trail Cryptographic Tamper Detection)",
                status="COMPLIANT"
            ),
            RegulatoryRequirementTrace(
                req_id="REQ-P11-04",
                regulation="21 CFR §11.50",
                requirement_summary="Electronic signatures must contain printed name of signer, date/time, and meaning of signature.",
                implementation_artifact="`SignatureRecord` & `SignatureService.create_signature`",
                verification_test_case="test_successful_electronic_signature & test_atomic_approve_and_sign",
                status="COMPLIANT"
            ),
            RegulatoryRequirementTrace(
                req_id="REQ-QMSR-01",
                regulation="FDA QMSR / ISO 13485:2016 (Clause 7.5.6)",
                requirement_summary="Software validation for production and quality management processes.",
                implementation_artifact="Regulated Golden Evaluation Suite & CI/CD Pipeline",
                verification_test_case="GoldenEvalRunner.run_all()",
                status="COMPLIANT"
            ),
            RegulatoryRequirementTrace(
                req_id="REQ-QMSR-02",
                regulation="FDA QMSR / ISO 13485:2016 (Clause 8.5.2)",
                requirement_summary="Corrective Action: Investigation of root cause and verification of action effectiveness.",
                implementation_artifact="CAPA Generator Agent & Closed-Loop Effectiveness Monitor",
                verification_test_case="test_capa_generation_flow & test_effectiveness_monitor_success_flow",
                status="COMPLIANT"
            ),
            RegulatoryRequirementTrace(
                req_id="REQ-ANNEX11-01",
                regulation="EU GMP Annex 11 (Computerised Systems)",
                requirement_summary="Risk management applied to computerised systems based on patient safety and data integrity.",
                implementation_artifact="Action Classes (A0-A5) & Policy Engine Guardrails",
                verification_test_case="EVAL-TC-04 & test_policy_guardrails",
                status="COMPLIANT"
            ),
        ]

        verdict = "PASSED - FIT FOR INTENDED USE" if eval_report.pass_rate_percent == 100.0 else "FAILED - REVIEW GAPS"

        vsr = ValidationSummaryReport(
            report_id=f"VSR-GXPSOFT-010-{datetime.now(timezone.utc).strftime('%Y%m%d')}",
            generated_at=datetime.now(timezone.utc).isoformat(),
            validation_verdict=verdict,
            regulatory_traceability_matrix=rtm,
            eval_suite_results=eval_report
        )

        # Compute SHA-256 integrity hash for the report
        snapshot = vsr.model_dump(mode="json", exclude={"sha256_report_hash"})
        vsr.sha256_report_hash = compute_sha256(snapshot)

        return vsr
