"""Unit tests specifically validating Pydantic AI integration, schemas, and agent behaviors."""

from pathlib import Path
import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from gxpsoft.agents.capa import CAPAAgent, create_capa_pydantic_agent
from gxpsoft.agents.nc_investigator import NCInvestigatorAgent, create_nc_pydantic_agent
from gxpsoft.agents.sentinel import SentinelAgent, create_sentinel_pydantic_agent
from gxpsoft.core.ai_config import get_agent_model, is_ollama_online
from gxpsoft.evidence.indexer import evidence_indexer
from gxpsoft.ingestion.service import IngestionService
from gxpsoft.models.agent_schemas import (
    CAPAPlanOutput,
    NCInvestigationOutput,
    SentinelTriageOutput,
)
from gxpsoft.models.enums import CaseSeverity, CaseState, SignatureMeaning
from gxpsoft.review.service import HumanReviewService


@pytest.fixture(autouse=True)
def index_fixtures(fixtures_dir: Path) -> None:
    evidence_indexer.index_document_directory(fixtures_dir / "documents")


def test_ai_config_model_initialization():
    """Verify that get_agent_model returns a properly configured model pointing to muse-glimmer."""
    model = get_agent_model()
    assert model.model_name == "muse-glimmer"


def test_sentinel_pydantic_agent_structure():
    """Validates Sentinel Pydantic AI agent creation, output schema, and prompt."""
    agent = create_sentinel_pydantic_agent()
    assert isinstance(agent, Agent)
    assert agent.name == "sentinel_agent"
    assert agent._output_type == SentinelTriageOutput


def test_nc_investigator_pydantic_agent_structure():
    """Validates NC Investigator Pydantic AI agent creation and structured schema."""
    agent = create_nc_pydantic_agent()
    assert isinstance(agent, Agent)
    assert agent.name == "nc_investigator_agent"
    assert agent._output_type == NCInvestigationOutput


def test_capa_pydantic_agent_structure():
    """Validates CAPA Pydantic AI agent creation and structured schema."""
    agent = create_capa_pydantic_agent()
    assert isinstance(agent, Agent)
    assert agent.name == "capa_agent"
    assert agent._output_type == CAPAPlanOutput


def test_end_to_end_pydantic_ai_pipeline_execution(mes_event_payload: dict):
    """Verifies that the entire pipeline runs with Pydantic AI agents maintaining audit integrity."""
    payload = dict(mes_event_payload)
    payload["idempotency_key"] = "test:pydantic_ai:e2e:001"
    payload["event_id"] = "EVT-PAI-001"

    # Step 1: Ingest
    event, case = IngestionService.ingest_event(payload)
    assert case.state == CaseState.SIGNAL_RECEIVED

    # Step 2: Sentinel Agent
    sentinel_res = SentinelAgent.evaluate_event(event=event, case=case)
    assert sentinel_res["severity"] == CaseSeverity.MAJOR.value
    assert case.state == CaseState.CASE_CREATED

    # Step 3: NC Investigator Agent
    nc_res = NCInvestigatorAgent.investigate(case_id=case.case_id)
    assert nc_res["status"] == "STAGED_FOR_REVIEW"
    assert nc_res["claims_count"] == 5
    assert case.state == CaseState.CONTAINMENT_PROPOSED

    # Step 4: Human Review Signatures
    case, _ = HumanReviewService.approve_and_sign(
        case_id=case.case_id,
        user_id="USER-QA-LEAD-01",
        password_or_pin="LeadPass2026!",
        meaning=SignatureMeaning.APPROVED_CLASSIFICATION,
        rationale="Classification and containment approved."
    )
    case, _ = HumanReviewService.approve_and_sign(
        case_id=case.case_id,
        user_id="USER-QA-LEAD-01",
        password_or_pin="LeadPass2026!",
        meaning=SignatureMeaning.APPROVED_ROOT_CAUSE,
        rationale="Root cause confirmed."
    )
    assert case.state == CaseState.ROOT_CAUSE_CONFIRMED

    # Step 5: CAPA Generator Agent
    capa_res = CAPAAgent.generate_capa(case_id=case.case_id)
    assert capa_res["actions_count"] == 4
    assert case.state == CaseState.CAPA_DRAFTED
