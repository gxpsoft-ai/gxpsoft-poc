"""Unit tests verifying Governed Tool Gateway execution, policy checks, and audit trails."""

from pathlib import Path
import pytest

from gxpsoft.core.policy import PolicyViolationError
from gxpsoft.core.repository import repo
from gxpsoft.evidence.indexer import evidence_indexer
from gxpsoft.models.case import QualityCase
from gxpsoft.models.enums import AuthorType, CaseSeverity, CaseState
from gxpsoft.tools.gateway import ToolGateway, ToolGatewayError


@pytest.fixture(autouse=True)
def setup_evidence_and_case(fixtures_dir: Path) -> str:
    evidence_indexer.index_document_directory(fixtures_dir / "documents")
    case = QualityCase(
        case_id="DEV-2026-TEST-TOOL",
        title="Test Tool Case",
        description="Testing Tool Gateway",
        initial_event_id="EVT-001",
        batch_id="BIO-2026-088",
        severity=CaseSeverity.MAJOR
    )
    repo.add_case(case)
    return case.case_id


def test_tool_gateway_search_sops() -> None:
    res = ToolGateway.invoke(
        tool_name="search_sops",
        arguments={"query": "Critical Process Parameters", "limit": 2},
        agent_run_id="RUN-TEST-001",
        actor_id="NCAgent-v1.0",
        actor_type=AuthorType.AGENT,
    )
    assert res["match_count"] > 0
    assert len(res["results"]) > 0
    assert "relevance_score" in res["results"][0]


def test_tool_gateway_get_equipment_calibration() -> None:
    res = ToolGateway.invoke(
        tool_name="get_equipment_calibration",
        arguments={"equipment_id": "BR-04"},
        agent_run_id="RUN-TEST-001",
        actor_id="NCAgent-v1.0",
        actor_type=AuthorType.AGENT,
    )
    assert res["found"] is True
    assert res["equipment_id"] == "BR-04"
    sensors = res["calibration_log"]["sensors"]
    rtd = next(s for s in sensors if s["sensor_id"] == "RTD-04B")
    assert rtd["calibration_status"] == "EXPIRED"


def test_tool_gateway_stage_investigation_draft(setup_evidence_and_case: str) -> None:
    case_id = setup_evidence_and_case
    ev_obj = next(iter(repo.evidence.values()))

    claims_data = [
        {
            "claim_text": "Temperature probe RTD-04B was overdue for 90-day calibration by 10 days.",
            "author_id": "NCAgent-v1.0",
            "confidence": 0.95,
            "uncertainty_notes": "None. Verification complete.",
            "citations": [
                {
                    "evidence_id": ev_obj.evidence_id,
                    "locator": "Equipment BR-04 -> Sensor RTD-04B",
                    "quote_text": "calibration_status: EXPIRED",
                    "relevance_score": 1.0,
                    "match_method": "EXACT_EXTRACTION"
                }
            ]
        }
    ]

    res = ToolGateway.invoke(
        tool_name="stage_investigation_draft",
        arguments={
            "case_id": case_id,
            "agent_run_id": "RUN-TEST-002",
            "title": "Proposed Investigation Report for Bioreactor Temp Excursion",
            "structured_content": {
                "summary": "Probe drift led to temperature excursion.",
                "severity_recommendation": "MAJOR"
            },
            "claims_data": claims_data
        },
        agent_run_id="RUN-TEST-002",
        actor_id="NCAgent-v1.0",
        actor_type=AuthorType.AGENT,
        case_id=case_id
    )

    assert res["status"] == "STAGED_FOR_REVIEW"
    assert res["claims_count"] == 1

    # Verify DraftArtifact was persisted
    drafts = repo.get_drafts_for_case(case_id)
    assert len(drafts) >= 1
    assert drafts[0].artifact_type == "INVESTIGATION_REPORT"

    # Verify claims stored
    claims = repo.get_claims_for_case(case_id)
    assert len(claims) >= 1
    assert claims[0].citations[0].locator == "Equipment BR-04 -> Sensor RTD-04B"


def test_tool_gateway_rejects_unregistered_tool() -> None:
    with pytest.raises(ToolGatewayError) as exc_info:
        ToolGateway.invoke(
            tool_name="arbitrary_db_write",
            arguments={"query": "DELETE FROM cases"},
            agent_run_id="RUN-TEST-003",
            actor_id="NCAgent-v1.0",
            actor_type=AuthorType.AGENT,
        )
    assert "not registered" in str(exc_info.value)
