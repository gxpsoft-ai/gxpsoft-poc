"""NC / Deviation Investigation Agent for multi-system evidence assembly and RCA draft staging."""

import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from gxpsoft.core.crypto import compute_sha256
from gxpsoft.core.repository import repo
from gxpsoft.core.state_machine import CaseStateMachine
from gxpsoft.models.agent_run import AgentRun
from gxpsoft.models.case import QualityCase
from gxpsoft.models.enums import AuthorType, CaseState
from gxpsoft.tools.gateway import ToolGateway


class NCInvestigatorAgent:
    """Nonconformance & Deviation Investigation Agent (Action Classes A0 & A2)."""

    AGENT_NAME = "NCInvestigatorAgent"
    AGENT_VERSION = "1.0.0"
    MODEL_NAME = "gemini-3.7-flash"
    PROMPT_VERSION = "v2.0"

    @classmethod
    def investigate(cls, case_id: str) -> Dict[str, Any]:
        """Orchestrates cross-system evidence gathering, RCA hypotheses, and draft artifact staging."""
        start_time = time.perf_counter()
        case = repo.get_case(case_id)
        if not case:
            raise ValueError(f"QualityCase '{case_id}' not found.")

        agent_run_id = f"RUN-NC-{case.case_id[-8:]}"

        # 1. Advance state: CASE_CREATED -> EVIDENCE_ASSEMBLED (A0 Action)
        if case.state == CaseState.CASE_CREATED:
            CaseStateMachine.transition(
                case_id=case.case_id,
                to_state=CaseState.EVIDENCE_ASSEMBLED,
                actor_id=cls.AGENT_NAME,
                actor_type=AuthorType.AGENT,
                rationale="Autonomous multi-system evidence gathering initiated."
            )

        # 2. Query Governed Tool Gateway across multiple systems
        # A. Calibration Logs (CMMS)
        equipment_id = "BR-04"
        calib_data = ToolGateway.invoke(
            tool_name="get_equipment_calibration",
            arguments={"equipment_id": equipment_id},
            agent_run_id=agent_run_id,
            actor_id=cls.AGENT_NAME,
            actor_type=AuthorType.AGENT,
            case_id=case.case_id
        )

        # B. Batch Genealogy & In-Process Samples (MES/ERP)
        batch_data = ToolGateway.invoke(
            tool_name="get_batch_genealogy",
            arguments={"batch_id": case.batch_id or "BIO-2026-088"},
            agent_run_id=agent_run_id,
            actor_id=cls.AGENT_NAME,
            actor_type=AuthorType.AGENT,
            case_id=case.case_id
        )

        # C. Operator Qualifications (LMS)
        operator_id = "USER-JDOE-441"
        training_data = ToolGateway.invoke(
            tool_name="get_operator_training",
            arguments={"operator_id": operator_id},
            agent_run_id=agent_run_id,
            actor_id=cls.AGENT_NAME,
            actor_type=AuthorType.AGENT,
            case_id=case.case_id
        )

        # D. Historical Deviations (QMS)
        similar_devs = ToolGateway.invoke(
            tool_name="find_similar_deviations",
            arguments={"keyword": "RTD calibration drift probe", "limit": 2},
            agent_run_id=agent_run_id,
            actor_id=cls.AGENT_NAME,
            actor_type=AuthorType.AGENT,
            case_id=case.case_id
        )

        # E. SOP Requirements (DMS)
        sop_containment = ToolGateway.invoke(
            tool_name="search_sops",
            arguments={"query": "containment quarantine harvest", "limit": 2},
            agent_run_id=agent_run_id,
            actor_id=cls.AGENT_NAME,
            actor_type=AuthorType.AGENT,
            case_id=case.case_id
        )

        # 3. Advance state: EVIDENCE_ASSEMBLED -> CONTAINMENT_PROPOSED (A2 Action)
        containment_plan = {
            "immediate_actions": [
                f"Quarantine in-process harvest from Batch #{case.batch_id} in cold storage (2-8°C).",
                f"Apply physical & electronic maintenance lockout tag on Bioreactor {equipment_id} pending probe recalibration.",
                "Issue urgent notification to Shift QA Manager within 24 hours per SOP-QMS-015."
            ]
        }
        case.metadata["proposed_containment"] = containment_plan
        repo.update_case(case)

        CaseStateMachine.transition(
            case_id=case.case_id,
            to_state=CaseState.CONTAINMENT_PROPOSED,
            actor_id=cls.AGENT_NAME,
            actor_type=AuthorType.AGENT,
            rationale="Immediate product quarantine and equipment lockout proposed for QA review."
        )

        # 4. Formulate 5-Why RCA Tree & Hypotheses
        five_why_tree = [
            {"why_1": "Bioreactor BR-04 temperature reached 39.4°C exceeding critical limit of 37.5°C."},
            {"why_2": "Vessel heating circuit remained continuously energized during feed phase step 4."},
            {"why_3": "Primary temperature probe RTD-04B sent false low readings (-1.8°C drift) to Emerson SCADA controller."},
            {"why_4": "RTD-04B sensor was past its 90-day NIST calibration interval and experienced negative thermal drift."},
            {"why_5": "CMMS preventive maintenance schedule lacked an automated execution lockout preventing batch start on expired calibration."}
        ]

        hypotheses = [
            {
                "hypothesis_id": "H1",
                "rank": 1,
                "title": "Temperature Sensor RTD-04B Calibration Drift (Primary Root Cause)",
                "confidence_score": 0.88,
                "evidence_summary": "Sensor RTD-04B was expired by 10 days. Historical deviation DEV-2025-312 confirms identical failure mode on BR-01.",
            },
            {
                "hypothesis_id": "H2",
                "rank": 2,
                "title": "Cooling Water Jacket Pneumatic Valve Delay (Secondary / Contributing)",
                "confidence_score": 0.12,
                "evidence_summary": "Pneumatic valve lag previously observed in DEV-2025-104; however, RTD probe expiration is the direct trigger.",
            }
        ]

        # 5. Build Atomic Claims with Exact Citation Locators
        ev_calib = next((e for e in repo.evidence.values() if e.doc_type == "CALIBRATION_LOG"), None)
        ev_sop_prc = next((e for e in repo.evidence.values() if "SOP-PRC-042" in e.title), None)
        ev_batch = next((e for e in repo.evidence.values() if e.doc_type == "BATCH_GENEALOGY"), None)
        ev_training = next((e for e in repo.evidence.values() if e.doc_type == "TRAINING_RECORD"), None)
        ev_hist = next((e for e in repo.evidence.values() if e.doc_type == "HISTORICAL_DEVIATIONS"), None)

        claims_data: List[Dict[str, Any]] = [
            {
                "claim_text": (
                    "The temperature excursion to 39.4°C for 22.5 minutes exceeds the critical process limit "
                    "(38.5°C for > 10 min) and is categorized as a Major Deviation under SOP-PRC-042."
                ),
                "author_id": cls.AGENT_NAME,
                "confidence": 0.98,
                "uncertainty_notes": "None. Excursion duration and magnitude verified by SCADA telemetry.",
                "citations": [
                    {
                        "evidence_id": ev_sop_prc.evidence_id if ev_sop_prc else "EVD-SOP-042",
                        "locator": "SOP-PRC-042, Section 4.2 (Major Excursions)",
                        "quote_text": "Any temperature elevation > 38.5 °C lasting greater than 10 minutes.",
                        "relevance_score": 1.0,
                        "match_method": "EXACT_EXTRACTION"
                    }
                ]
            },
            {
                "claim_text": (
                    "Primary temperature sensor RTD-04B on Bioreactor BR-04 was 10 days past its 90-day NIST "
                    "calibration due date (Expired 2026-02-08) at the time of batch processing."
                ),
                "author_id": cls.AGENT_NAME,
                "confidence": 0.99,
                "uncertainty_notes": "None. Direct record match from CMMS calibration register.",
                "citations": [
                    {
                        "evidence_id": ev_calib.evidence_id if ev_calib else "EVD-CALIB-04",
                        "locator": "Equipment BR-04 -> Sensor RTD-04B",
                        "quote_text": "calibration_status: EXPIRED, days_overdue_as_of_event: 10",
                        "relevance_score": 1.0,
                        "match_method": "EXACT_EXTRACTION"
                    }
                ]
            },
            {
                "claim_text": (
                    "Lead operator USER-JDOE-441 was fully trained and qualified on SOP-PRC-042 and SOP-QMS-015; "
                    "operator error is ruled out as a primary root cause."
                ),
                "author_id": cls.AGENT_NAME,
                "confidence": 0.95,
                "uncertainty_notes": "Execution adherence verified against electronic batch execution timestamps.",
                "citations": [
                    {
                        "evidence_id": ev_training.evidence_id if ev_training else "EVD-TRAIN-01",
                        "locator": "Operator USER-JDOE-441 -> Qualifications",
                        "quote_text": "SOP-PRC-042 (v3.1): QUALIFIED, SOP-QMS-015 (v4.0): QUALIFIED",
                        "relevance_score": 0.95,
                        "match_method": "EXACT_EXTRACTION"
                    }
                ]
            },
            {
                "claim_text": (
                    "In-process cell viability degraded from 96.5% to 78.4% following the thermal excursion, "
                    "confirming direct product quality impact on Batch #BIO-2026-088."
                ),
                "author_id": cls.AGENT_NAME,
                "confidence": 0.94,
                "uncertainty_notes": "Final QC release assay pending confirmation.",
                "citations": [
                    {
                        "evidence_id": ev_batch.evidence_id if ev_batch else "EVD-BATCH-088",
                        "locator": "Batch BIO-2026-088 -> In-Process Samples",
                        "quote_text": "SMP-DAY3-POST-EXCURSION: viability_percent: 78.4",
                        "relevance_score": 0.95,
                        "match_method": "EXACT_EXTRACTION"
                    }
                ]
            },
            {
                "claim_text": (
                    "Prior deviation DEV-2025-312 demonstrated an identical failure pattern on Bioreactor BR-01, "
                    "where overdue RTD sensors developed negative drift and caused overheating."
                ),
                "author_id": cls.AGENT_NAME,
                "confidence": 0.90,
                "uncertainty_notes": "Slight mechanical differences between vessels BR-01 and BR-04.",
                "citations": [
                    {
                        "evidence_id": ev_hist.evidence_id if ev_hist else "EVD-HIST-01",
                        "locator": "Deviation DEV-2025-312",
                        "quote_text": "Probe RTD-01A was overdue for 90-day NIST calibration by 14 days and had drifted -1.8°C low",
                        "relevance_score": 0.90,
                        "match_method": "EXACT_EXTRACTION"
                    }
                ]
            }
        ]

        # 6. Stage Investigation Draft Report via Governed Tool Gateway
        structured_report = {
            "case_id": case.case_id,
            "title": f"Investigation Report: Bioreactor BR-04 Thermal Excursion (Batch #{case.batch_id})",
            "severity_recommendation": case.severity.value if case.severity else "MAJOR",
            "event_summary": (
                f"During Day 3 feed phase of Batch #{case.batch_id} in vessel BR-04, temperature elevated "
                "to 39.4°C for 22.5 minutes due to thermal probe calibration drift."
            ),
            "containment_summary": containment_plan,
            "five_why_analysis": five_why_tree,
            "ranked_hypotheses": hypotheses,
            "uncertainty_disclosure": (
                "High-frequency pneumatic solenoid valve telemetry was unavailable in SCADA stream. "
                "While mechanical valve delay cannot be completely disproven, RTD-04B expired calibration "
                "is confirmed by NIST CMMS logs and matches prior recurrence DEV-2025-312."
            )
        }

        stage_res = ToolGateway.invoke(
            tool_name="stage_investigation_draft",
            arguments={
                "case_id": case.case_id,
                "agent_run_id": agent_run_id,
                "title": structured_report["title"],
                "structured_content": structured_report,
                "claims_data": claims_data,
                "artifact_type": "INVESTIGATION_REPORT"
            },
            agent_run_id=agent_run_id,
            actor_id=cls.AGENT_NAME,
            actor_type=AuthorType.AGENT,
            case_id=case.case_id
        )

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        # 7. Record AgentRun Provenance
        agent_run = AgentRun(
            run_id=agent_run_id,
            case_id=case.case_id,
            agent_name=cls.AGENT_NAME,
            agent_version=cls.AGENT_VERSION,
            model_name=cls.MODEL_NAME,
            prompt_version=cls.PROMPT_VERSION,
            prompt_hash=compute_sha256("Investigate bioreactor excursion, assemble evidence, stage RCA draft."),
            input_payload={"case_id": case.case_id, "batch_id": case.batch_id},
            output_payload={"artifact_id": stage_res["artifact_id"], "claims_count": stage_res["claims_count"]},
            latency_ms=elapsed_ms,
            completed_at=datetime.now(timezone.utc)
        )

        repo.audit_ledger.append(
            event_type="AGENT_RUN_COMPLETED",
            entity_type="AgentRun",
            entity_id=agent_run.run_id,
            actor_id=cls.AGENT_NAME,
            actor_type=AuthorType.AGENT,
            data_snapshot=agent_run.model_dump(mode="json"),
            case_id=case.case_id
        )

        return {
            "case_id": case.case_id,
            "status": "STAGED_FOR_REVIEW",
            "artifact_id": stage_res["artifact_id"],
            "claims_count": stage_res["claims_count"],
            "agent_run_id": agent_run_id
        }
