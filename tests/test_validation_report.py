"""Unit and API tests for ValidationReportGenerator and GAMP 5 CSA summary report."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from gxpsoft.api.main import app
from gxpsoft.evals.validation_report import ValidationReportGenerator

client = TestClient(app)


def test_generate_csa_validation_summary_report(fixtures_dir: Path) -> None:
    vsr = ValidationReportGenerator.generate_report(fixtures_dir)

    assert "FIT FOR INTENDED USE" in vsr.validation_verdict
    assert len(vsr.sha256_report_hash) == 64
    assert len(vsr.regulatory_traceability_matrix) >= 7

    # Verify key regulations covered in RTM
    reg_texts = [r.regulation for r in vsr.regulatory_traceability_matrix]
    assert any("21 CFR §11.10(a)" in reg for reg in reg_texts)
    assert any("21 CFR §11.10(e)" in reg for reg in reg_texts)
    assert any("21 CFR §11.50" in reg for reg in reg_texts)
    assert any("FDA QMSR" in reg for reg in reg_texts)
    assert any("Annex 11" in reg for reg in reg_texts)

    assert vsr.eval_suite_results.pass_rate_percent == 100.0


def test_api_evals_and_validation_report_endpoints() -> None:
    # 1. Test /api/v1/evals/run
    res_evals = client.post("/api/v1/evals/run")
    assert res_evals.status_code == 200
    eval_data = res_evals.json()
    assert eval_data["pass_rate_percent"] == 100.0
    assert eval_data["total_tests"] == 5

    # 2. Test /api/v1/evals/validation-summary-report
    res_vsr = client.get("/api/v1/evals/validation-summary-report")
    assert res_vsr.status_code == 200
    vsr_data = res_vsr.json()
    assert "FIT FOR INTENDED USE" in vsr_data["validation_verdict"]
    assert len(vsr_data["regulatory_traceability_matrix"]) >= 7
    assert len(vsr_data["sha256_report_hash"]) == 64
