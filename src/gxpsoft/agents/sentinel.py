"""Sentinel Agent for autonomous operational event normalization, triage, and signal classification."""

import time
from datetime import datetime, timezone
from typing import Any, Dict

from gxpsoft.core.crypto import compute_sha256
from gxpsoft.core.repository import repo
from gxpsoft.core.state_machine import CaseStateMachine
from gxpsoft.models.agent_run import AgentRun
from gxpsoft.models.case import QualityCase
from gxpsoft.models.enums import AuthorType, CaseSeverity, CaseState
from gxpsoft.models.event import QualityEvent
from gxpsoft.tools.gateway import ToolGateway


class SentinelAgent:
    """Sentinel Agent responsible for A0/A1 event intake, triage, and initial classification."""

    AGENT_NAME = "SentinelAgent"
    AGENT_VERSION = "1.0.0"
    MODEL_NAME = "gemini-3.7-flash"
    PROMPT_VERSION = "v1.2"

    @classmethod
    def evaluate_event(cls, event: QualityEvent, case: QualityCase) -> Dict[str, Any]:
        """Analyzes an operational event, queries relevant SOPs, and sets initial case severity."""
        start_time = time.perf_counter()
        agent_run_id = f"RUN-SENTINEL-{event.event_id[-8:]}"
        prompt_content = f"Evaluate {event.event_type} telemetry for batch {event.batch_id} against SOP limits."
        prompt_hash = compute_sha256(prompt_content)

        # 1. Search SOPs via ToolGateway
        sop_results = ToolGateway.invoke(
            tool_name="search_sops",
            arguments={"query": "Excursion Handling Classification Major Critical", "limit": 2},
            agent_run_id=agent_run_id,
            actor_id=cls.AGENT_NAME,
            actor_type=AuthorType.AGENT,
            case_id=case.case_id
        )

        # 2. Evaluate excursion logic based on SOP-PRC-042 rules
        payload = event.payload
        peak_val = payload.get("peak_value", 0.0)
        duration = payload.get("duration_minutes", 0.0)

        # Rule evaluation:
        # Major: > 38.5°C for > 10 min OR > 39.0°C regardless of duration
        # Critical: > 40.0°C
        if peak_val >= 40.0:
            assigned_severity = CaseSeverity.CRITICAL
            rationale = f"Peak value {peak_val}°C exceeds Critical threshold (>= 40.0°C)."
        elif peak_val >= 39.0 or (peak_val > 38.5 and duration > 10.0):
            assigned_severity = CaseSeverity.MAJOR
            rationale = (
                f"Peak temperature {peak_val}°C (> 39.0°C) with duration {duration} min "
                f"(> 10.0 min above 38.5°C limit) classified as MAJOR per SOP-PRC-042 Section 4.2."
            )
        else:
            assigned_severity = CaseSeverity.MINOR
            rationale = f"Excursion within minor handling parameters (peak {peak_val}°C for {duration} min)."

        # 3. Update case severity
        case.severity = assigned_severity
        case.metadata["triage_rationale"] = rationale
        repo.update_case(case)

        # 4. Advance FSM state: SIGNAL_RECEIVED -> CASE_CREATED (A0 Action)
        CaseStateMachine.transition(
            case_id=case.case_id,
            to_state=CaseState.CASE_CREATED,
            actor_id=cls.AGENT_NAME,
            actor_type=AuthorType.AGENT,
            rationale=rationale
        )

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        # 5. Record AgentRun provenance
        agent_run = AgentRun(
            run_id=agent_run_id,
            case_id=case.case_id,
            agent_name=cls.AGENT_NAME,
            agent_version=cls.AGENT_VERSION,
            model_name=cls.MODEL_NAME,
            prompt_version=cls.PROMPT_VERSION,
            prompt_hash=prompt_hash,
            input_payload={"event_id": event.event_id, "payload": event.payload},
            output_payload={"severity": assigned_severity.value, "rationale": rationale},
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
            "severity": assigned_severity.value,
            "rationale": rationale,
            "agent_run_id": agent_run_id
        }
