"""CAPA Generator Agent for drafting corrective/preventive action plans and effectiveness criteria."""

import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from gxpsoft.core.crypto import compute_sha256
from gxpsoft.core.repository import repo
from gxpsoft.core.state_machine import CaseStateMachine
from gxpsoft.models.agent_run import AgentRun, DraftArtifact
from gxpsoft.models.case import QualityCase
from gxpsoft.models.enums import AuthorType, CaseState
from gxpsoft.tools.gateway import ToolGateway


class CAPAAgent:
    """CAPA Generator Agent (Action Classes A0 & A2)."""

    AGENT_NAME = "CAPAAgent"
    AGENT_VERSION = "1.0.0"
    MODEL_NAME = "gemini-3.7-flash"
    PROMPT_VERSION = "v1.5"

    @classmethod
    def generate_capa(cls, case_id: str) -> Dict[str, Any]:
        """Generates a structured CAPA action plan tied directly to confirmed root-cause claims."""
        start_time = time.perf_counter()
        case = repo.get_case(case_id)
        if not case:
            raise ValueError(f"QualityCase '{case_id}' not found.")

        agent_run_id = f"RUN-CAPA-{case.case_id[-8:]}"

        # 1. Search prior effective CAPAs via ToolGateway
        history = ToolGateway.invoke(
            tool_name="find_similar_deviations",
            arguments={"keyword": "RTD calibration drift probe CAPA", "limit": 2},
            agent_run_id=agent_run_id,
            actor_id=cls.AGENT_NAME,
            actor_type=AuthorType.AGENT,
            case_id=case.case_id
        )

        # 2. Formulate Corrective and Preventive Actions
        capa_actions = [
            {
                "action_id": "ACT-01",
                "action_type": "CORRECTIVE_IMMEDIATE",
                "title": "Replace and 3-Point NIST Recalibrate Probe RTD-04B",
                "description": (
                    "Remove expired RTD-04B sensor on Bioreactor BR-04. Install new factory-certified "
                    "Class A PT100 RTD sensor and perform 3-point NIST-traceable calibration across 30°C–45°C range."
                ),
                "target_owner": "Instrumentation Maintenance Lead",
                "due_days": 7,
                "linked_root_cause": "RTD-04B sensor expired 10 days prior to batch run with negative calibration drift."
            },
            {
                "action_id": "ACT-02",
                "action_type": "CORRECTIVE_SCOPE_ASSESSMENT",
                "title": "Retrospective Batch Quality & Viability Impact Assessment",
                "description": (
                    "Perform formal impact assessment on all batches processed in BR-04 between 2026-02-08 "
                    "(expiration date) and 2026-08-18 (excursion discovery) to verify no uncontained thermal excursions occurred."
                ),
                "target_owner": "Quality Assurance Specialist",
                "due_days": 14,
                "linked_root_cause": "Uncontained operation of BR-04 past probe calibration due date."
            },
            {
                "action_id": "ACT-03",
                "action_type": "PREVENTIVE_SYSTEMIC",
                "title": "Automated CMMS Hard-Lockout for Overdue Calibration",
                "description": (
                    "Implement automated software interlock between CMMS (Maintenance) and Emerson MES/SCADA. "
                    "If any vessel sensor is within 7 days of calibration expiration, initiate alert; "
                    "if past due, enforce hard lockout preventing batch recipe initiation per SOP-PRC-042 Section 5.2."
                ),
                "target_owner": "Automation & IT Systems Lead",
                "due_days": 30,
                "linked_root_cause": "Absence of automated electronic recipe lockout when sensor calibration expired."
            },
            {
                "action_id": "ACT-04",
                "action_type": "PREVENTIVE_TRAINING",
                "title": "Maintenance & Operator Training on Pre-Flight Calibration Checks",
                "description": (
                    "Conduct mandatory training for all upstream bioprocess technicians and shift leads on "
                    "verifying sensor NIST calibration dates in the electronic equipment logbook prior to vessel setup."
                ),
                "target_owner": "Training Coordinator",
                "due_days": 21,
                "linked_root_cause": "Failure to detect expired calibration status during pre-run line clearance."
            }
        ]

        # 3. Formulate Quantifiable Effectiveness Verification Criteria
        effectiveness_plan = {
            "verification_metric": (
                "Zero temperature excursions (> 0.5°C deviation from 37.0°C setpoint for > 5 min) "
                "across the next 5 consecutive commercial production batches processed in Bioreactor BR-04."
            ),
            "target_consecutive_clean_batches": 5,
            "verification_window_days": 60,
            "assigned_evaluator": "USER-QA-MGR-01",
            "recurrence_action": "Immediate escalation and mandatory CAPA reopening if temperature drift recurs."
        }

        # 4. Advance FSM state: ROOT_CAUSE_CONFIRMED -> CAPA_DRAFTED (A2 Action)
        if case.state == CaseState.ROOT_CAUSE_CONFIRMED:
            CaseStateMachine.transition(
                case_id=case.case_id,
                to_state=CaseState.CAPA_DRAFTED,
                actor_id=cls.AGENT_NAME,
                actor_type=AuthorType.AGENT,
                rationale="CAPA action plan and effectiveness verification criteria staged for QA Management approval."
            )

        # 5. Stage CAPA Plan DraftArtifact
        structured_content = {
            "case_id": case.case_id,
            "title": f"CAPA Action Plan: Bioreactor BR-04 Temperature Probe Drift (Case #{case.case_id})",
            "capa_actions": capa_actions,
            "effectiveness_plan": effectiveness_plan,
            "status": "STAGED_FOR_QA_MANAGEMENT_AUTHORIZATION"
        }

        draft = DraftArtifact(
            case_id=case.case_id,
            agent_run_id=agent_run_id,
            artifact_type="CAPA_PLAN",
            title=structured_content["title"],
            structured_content=structured_content,
            claim_ids=[c.claim_id for c in repo.get_claims_for_case(case.case_id)],
            status="STAGED_FOR_REVIEW"
        )
        repo.add_draft(draft)

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        # 6. Record AgentRun Provenance
        agent_run = AgentRun(
            run_id=agent_run_id,
            case_id=case.case_id,
            agent_name=cls.AGENT_NAME,
            agent_version=cls.AGENT_VERSION,
            model_name=cls.MODEL_NAME,
            prompt_version=cls.PROMPT_VERSION,
            prompt_hash=compute_sha256("Generate CAPA actions and effectiveness verification plan."),
            input_payload={"case_id": case.case_id},
            output_payload={"artifact_id": draft.artifact_id, "actions_count": len(capa_actions)},
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
            "artifact_id": draft.artifact_id,
            "actions_count": len(capa_actions),
            "state": case.state.value,
            "agent_run_id": agent_run_id
        }
