"""Closed-loop CAPA effectiveness verification monitor and recurrence detector."""

from datetime import datetime, timezone
from typing import Any, Dict, List

from gxpsoft.core.repository import repo
from gxpsoft.core.state_machine import CaseStateMachine
from gxpsoft.models.enums import AuthorType, CaseState


class RecurrenceDetectedError(Exception):
    """Raised when an excursion recurs during the CAPA effectiveness monitoring period."""
    pass


class EffectivenessMonitor:
    """Evaluates post-implementation production telemetry against CAPA effectiveness criteria."""

    @staticmethod
    def evaluate_batch_results(
        case_id: str,
        batch_results: List[Dict[str, Any]],
        evaluator_id: str = "EFFECTIVENESS_MONITOR_SYSTEM"
    ) -> Dict[str, Any]:
        """Evaluates subsequent batches to determine if the CAPA effectiveness criteria are satisfied."""
        case = repo.get_case(case_id)
        if not case:
            raise ValueError(f"QualityCase '{case_id}' not found.")

        # Check for recurrence in the telemetry stream
        failed_batches = []
        clean_batches = []

        for b in batch_results:
            batch_id = b.get("batch_id", "UNKNOWN")
            max_temp = b.get("max_temp_celsius", 37.0)
            excursion_duration = b.get("excursion_duration_min", 0.0)

            # Limit: Temperature must not deviate > 0.5°C from 37.0°C setpoint (>37.5°C)
            if max_temp > 37.5 and excursion_duration > 5.0:
                failed_batches.append({
                    "batch_id": batch_id,
                    "max_temp": max_temp,
                    "duration": excursion_duration,
                    "failure_reason": f"Temperature elevated to {max_temp}°C for {excursion_duration} min."
                })
            else:
                clean_batches.append(batch_id)

        # 1. Handle Recurrence Failure
        if failed_batches:
            recurrence_msg = (
                f"Recurrence detected during effectiveness window! {len(failed_batches)} batch(es) "
                f"exceeded temperature limits: {failed_batches}"
            )
            repo.audit_ledger.append(
                event_type="RECURRENCE_ESCALATION_TRIGGERED",
                entity_type="QualityCase",
                entity_id=case_id,
                actor_id=evaluator_id,
                actor_type=AuthorType.SYSTEM,
                data_snapshot={
                    "case_id": case_id,
                    "failed_batches": failed_batches,
                    "clean_batches": clean_batches,
                    "escalation_message": recurrence_msg
                },
                case_id=case_id
            )
            return {
                "case_id": case_id,
                "verified": False,
                "clean_batches_count": len(clean_batches),
                "required_clean_batches": 5,
                "failed_batches": failed_batches,
                "message": recurrence_msg,
                "escalation_triggered": True
            }

        # 2. Check if required threshold (5 consecutive clean batches) is met
        required_count = 5
        if len(clean_batches) >= required_count:
            # Advance state: CAPA_AUTHORIZED -> EFFECTIVENESS_VERIFIED (A3 Action)
            if case.state == CaseState.CAPA_AUTHORIZED:
                CaseStateMachine.transition(
                    case_id=case_id,
                    to_state=CaseState.EFFECTIVENESS_VERIFIED,
                    actor_id=evaluator_id,
                    actor_type=AuthorType.SYSTEM,
                    rationale=f"Successfully demonstrated {len(clean_batches)} consecutive clean batches without thermal excursion."
                )

            repo.audit_ledger.append(
                event_type="EFFECTIVENESS_CRITERIA_MET",
                entity_type="QualityCase",
                entity_id=case_id,
                actor_id=evaluator_id,
                actor_type=AuthorType.SYSTEM,
                data_snapshot={
                    "case_id": case_id,
                    "clean_batches_verified": clean_batches,
                    "criteria_status": "SATISFIED"
                },
                case_id=case_id
            )

            return {
                "case_id": case_id,
                "verified": True,
                "clean_batches_count": len(clean_batches),
                "required_clean_batches": required_count,
                "current_case_state": case.state.value,
                "message": "Effectiveness criteria fully satisfied. Case ready for QA Director final closure signature."
            }

        return {
            "case_id": case_id,
            "verified": False,
            "clean_batches_count": len(clean_batches),
            "required_clean_batches": required_count,
            "message": f"In-progress: {len(clean_batches)}/{required_count} clean batches verified."
        }
