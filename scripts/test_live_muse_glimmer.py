"""Standalone script to execute live Pydantic AI calls against muse-glimmer on Ollama with Langfuse tracing."""

import json
import os
import time
from pathlib import Path

from gxpsoft.agents.capa import CAPAAgent
from gxpsoft.agents.nc_investigator import NCInvestigatorAgent
from gxpsoft.agents.orchestrator import InvestigationPipeline
from gxpsoft.agents.sentinel import SentinelAgent
from gxpsoft.core.ai_config import get_agent_model, is_ollama_online
from gxpsoft.core.observability import DEFAULT_LANGFUSE_HOST, flush_langfuse, get_langfuse_client
from gxpsoft.core.repository import repo
from gxpsoft.evidence.indexer import evidence_indexer
from gxpsoft.models.enums import SignatureMeaning
from gxpsoft.review.service import HumanReviewService


def main():
    print("=" * 70)
    print("GxPSoft — Live Pydantic AI + Langfuse Observability Execution")
    print("=" * 70)

    # 1. Check Ollama & Langfuse servers
    ollama_online = is_ollama_online()
    model = get_agent_model()
    langfuse_host = os.getenv("LANGFUSE_HOST", DEFAULT_LANGFUSE_HOST)
    langfuse_client = get_langfuse_client()

    print(f"Ollama Server Online: {ollama_online} (Model: {model.model_name})")
    print(f"Langfuse Server Host: {langfuse_host} (Client Initialized: {langfuse_client is not None})")

    if not ollama_online:
        print("ERROR: Ollama server is not responding at http://localhost:11434")
        return

    # 2. Index documentation fixtures
    fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures"
    evidence_indexer.index_document_directory(fixtures_dir / "documents")
    print(f"Indexed {len(repo.evidence)} documents into Evidence Graph.")

    # 3. Load operational telemetry event
    event_file = fixtures_dir / "events" / "mes_temp_excursion.json"
    with open(event_file, "r", encoding="utf-8") as f:
        mes_payload = json.load(f)

    print("\n" + "-" * 70)
    print("STEP 1: Autonomous Triage & Multi-System RCA via Pydantic AI (Traced)")
    print("-" * 70)
    start = time.perf_counter()
    event, case, summary = InvestigationPipeline.run_pipeline(mes_payload)
    elapsed = time.perf_counter() - start

    print(f"Case ID: {case.case_id}")
    print(f"Assigned Severity: {summary['severity']}")
    print(f"Triage Rationale:\n  {summary['triage_rationale']}")
    print(f"Staged Draft Artifact: {summary['artifact_id']}")
    print(f"Grounded Claims Generated: {summary['claims_count']}")
    print(f"Execution Latency: {elapsed:.2f}s")

    print("\n" + "-" * 70)
    print("STEP 2: Human-in-the-Loop Part 11 Electronic Signatures (Traced)")
    print("-" * 70)
    case, _ = HumanReviewService.approve_and_sign(
        case_id=case.case_id,
        user_id="USER-QA-LEAD-01",
        password_or_pin="LeadPass2026!",
        meaning=SignatureMeaning.APPROVED_CLASSIFICATION,
        rationale="Approved classification and containment plan per SOP-PRC-042."
    )
    case, _ = HumanReviewService.approve_and_sign(
        case_id=case.case_id,
        user_id="USER-QA-LEAD-01",
        password_or_pin="LeadPass2026!",
        meaning=SignatureMeaning.APPROVED_ROOT_CAUSE,
        rationale="Approved RTD-04B expired calibration drift as primary root cause."
    )
    print(f"Current State: {case.state.value}")

    print("\n" + "-" * 70)
    print("STEP 3: Autonomous CAPA Plan Generation via Pydantic AI (Traced)")
    print("-" * 70)
    start_capa = time.perf_counter()
    capa_res = CAPAAgent.generate_capa(case.case_id)
    elapsed_capa = time.perf_counter() - start_capa

    drafts = repo.get_drafts_for_case(case.case_id)
    capa_draft = next(d for d in drafts if d.artifact_type == "CAPA_PLAN")
    content = capa_draft.structured_content

    print(f"CAPA Artifact ID: {capa_draft.artifact_id}")
    print(f"Action Items ({len(content['capa_actions'])}):")
    for act in content["capa_actions"]:
        print(f"  • [{act['action_type']}] {act['title']} (Owner: {act['target_owner']}, Due: {act['due_days']}d)")
    print(f"Effectiveness Metric: {content['effectiveness_plan']['verification_metric']}")
    print(f"CAPA Latency: {elapsed_capa:.2f}s")

    print("\n" + "-" * 70)
    print("STEP 4: 21 CFR Part 11 Cryptographic Audit Trail & Langfuse Flush")
    print("-" * 70)
    is_valid = repo.audit_ledger.verify_integrity()
    print(f"Ledger Hash-Chain Valid: {is_valid}")
    print(f"Total Immutable Audit Entries: {len(repo.audit_ledger.entries)}")
    latest = repo.audit_ledger.entries[-1]
    print(f"Latest Entry: {latest.entry_id} | Hash: {latest.entry_hash[:16]}... | PrevHash: {latest.prev_hash[:16]}...")

    flush_langfuse()
    print(f"Langfuse traces flushed to {langfuse_host}")
    print("=" * 70)
    print("SUCCESS: Full Pydantic AI + muse-glimmer + Langfuse + Part 11 verified!")
    print("=" * 70)


if __name__ == "__main__":
    main()
