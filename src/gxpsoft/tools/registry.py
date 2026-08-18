"""Governed GxP Tool implementations for AI agents."""

import json
from typing import Any, Dict, List, Optional

from gxpsoft.core.repository import repo
from gxpsoft.evidence.indexer import evidence_indexer
from gxpsoft.models.agent_run import DraftArtifact
from gxpsoft.models.enums import AuthorType
from gxpsoft.models.evidence import Claim, ClaimEvidenceLink


def search_sops(query: str, limit: int = 3) -> Dict[str, Any]:
    """Searches controlled Standard Operating Procedures (SOPs) for relevant clauses."""
    results = evidence_indexer.search(query=query, doc_type="SOP", limit=limit)
    formatted = []
    for chunk, score in results:
        formatted.append({
            "evidence_id": chunk.evidence_id,
            "doc_title": chunk.doc_title,
            "locator": chunk.locator,
            "heading": chunk.heading,
            "excerpt": chunk.text,
            "relevance_score": score
        })
    return {"query": query, "match_count": len(formatted), "results": formatted}


def get_equipment_calibration(equipment_id: str) -> Dict[str, Any]:
    """Retrieves NIST calibration history and expiration status for equipment sensors."""
    for ev in repo.evidence.values():
        if ev.doc_type == "CALIBRATION_LOG" and ev.raw_content:
            data = json.loads(ev.raw_content)
            if data.get("equipment_id") == equipment_id:
                return {"found": True, "equipment_id": equipment_id, "calibration_log": data}
    return {"found": False, "equipment_id": equipment_id, "message": "No calibration record found."}


def get_batch_genealogy(batch_id: str) -> Dict[str, Any]:
    """Retrieves batch record details, bill of materials, and in-process samples."""
    for ev in repo.evidence.values():
        if ev.doc_type == "BATCH_GENEALOGY" and ev.raw_content:
            data = json.loads(ev.raw_content)
            if data.get("batch_id") == batch_id:
                return {"found": True, "batch_id": batch_id, "genealogy": data}
    return {"found": False, "batch_id": batch_id, "message": "No batch record found."}


def get_operator_training(operator_id: str) -> Dict[str, Any]:
    """Retrieves training qualifications and SOP sign-offs for an operator."""
    for ev in repo.evidence.values():
        if ev.doc_type == "TRAINING_RECORD" and ev.raw_content:
            data = json.loads(ev.raw_content)
            for op in data.get("operators", []):
                if op.get("user_id") == operator_id:
                    return {"found": True, "operator_id": operator_id, "record": op}
    return {"found": False, "operator_id": operator_id, "message": "Operator training record not found."}


def find_similar_deviations(keyword: str, limit: int = 3) -> Dict[str, Any]:
    """Searches historical deviation and CAPA records for similar failure modes."""
    results = evidence_indexer.search(query=keyword, doc_type="HISTORICAL_DEVIATIONS", limit=limit)
    formatted = []
    for chunk, score in results:
        formatted.append({
            "evidence_id": chunk.evidence_id,
            "locator": chunk.locator,
            "details": json.loads(chunk.text) if chunk.text.startswith("{") else chunk.text,
            "relevance_score": score
        })
    return {"keyword": keyword, "count": len(formatted), "similar_deviations": formatted}


def stage_investigation_draft(
    case_id: str,
    agent_run_id: str,
    title: str,
    structured_content: Dict[str, Any],
    claims_data: List[Dict[str, Any]],
    artifact_type: str = "INVESTIGATION_REPORT"
) -> Dict[str, Any]:
    """Stages a draft investigation report and atomic claims for human review (A2 Action)."""
    case = repo.get_case(case_id)
    if not case:
        raise ValueError(f"QualityCase '{case_id}' not found.")

    created_claim_ids = []
    for cd in claims_data:
        citations = []
        for cite in cd.get("citations", []):
            link = ClaimEvidenceLink(
                evidence_id=cite["evidence_id"],
                locator=cite["locator"],
                quote_text=cite["quote_text"],
                relevance_score=cite.get("relevance_score", 1.0),
                match_method=cite.get("match_method", "EXACT_EXTRACTION")
            )
            citations.append(link)

        claim = Claim(
            case_id=case_id,
            claim_text=cd["claim_text"],
            author_type=AuthorType.AGENT,
            author_id=cd.get("author_id", "Agent"),
            confidence=cd.get("confidence", 0.9),
            uncertainty_notes=cd.get("uncertainty_notes"),
            alternative_explanations=cd.get("alternative_explanations", []),
            citations=citations
        )
        repo.add_claim(claim)
        created_claim_ids.append(claim.claim_id)

    draft = DraftArtifact(
        case_id=case_id,
        agent_run_id=agent_run_id,
        artifact_type=artifact_type,
        title=title,
        structured_content=structured_content,
        claim_ids=created_claim_ids,
        status="STAGED_FOR_REVIEW"
    )
    repo.add_draft(draft)

    return {
        "artifact_id": draft.artifact_id,
        "case_id": case_id,
        "claims_count": len(created_claim_ids),
        "status": draft.status
    }
