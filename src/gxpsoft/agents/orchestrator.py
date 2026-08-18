"""End-to-end investigation orchestration pipeline coordinating Sentinel and NC agents."""

from typing import Any, Dict, Tuple

from gxpsoft.agents.nc_investigator import NCInvestigatorAgent
from gxpsoft.agents.sentinel import SentinelAgent
from gxpsoft.core.observability import observe
from gxpsoft.ingestion.service import IngestionService
from gxpsoft.models.case import QualityCase
from gxpsoft.models.event import QualityEvent


class InvestigationPipeline:
    """Coordinates autonomous event intake, triage, multi-system investigation, and draft staging."""

    @staticmethod
    @observe(name="InvestigationPipeline.run_pipeline", as_type="chain")
    def run_pipeline(raw_event_dict: Dict[str, Any]) -> Tuple[QualityEvent, QualityCase, Dict[str, Any]]:
        """Executes the complete autonomous investigation loop up to the human review gate."""
        # Step 1: Ingest operational event
        event, case = IngestionService.ingest_event(raw_event_dict)
        if not case:
            raise RuntimeError("Case creation failed during event ingestion.")

        # Step 2: Sentinel Agent evaluates event & transitions to CASE_CREATED
        sentinel_result = SentinelAgent.evaluate_event(event=event, case=case)

        # Step 3: NC Investigator gathers multi-system evidence & stages DraftArtifact
        nc_result = NCInvestigatorAgent.investigate(case_id=case.case_id)

        pipeline_summary = {
            "event_id": event.event_id,
            "case_id": case.case_id,
            "severity": sentinel_result["severity"],
            "triage_rationale": sentinel_result["rationale"],
            "artifact_id": nc_result["artifact_id"],
            "claims_count": nc_result["claims_count"],
            "current_case_state": case.state.value,
        }

        return event, case, pipeline_summary
