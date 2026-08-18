"""Unit and regression tests for GoldenEvalRunner and regulated test cases."""

from pathlib import Path
import pytest

from gxpsoft.evals.runner import GoldenEvalRunner


def test_golden_eval_suite_full_execution(fixtures_dir: Path) -> None:
    report = GoldenEvalRunner.run_all(fixtures_dir)

    assert report.total_tests == 5
    assert report.passed_tests == 5
    assert report.failed_tests == 0
    assert report.pass_rate_percent == 100.0

    tc_ids = [r.test_case_id for r in report.results]
    assert "EVAL-TC-01" in tc_ids  # Nominal
    assert "EVAL-TC-02" in tc_ids  # Abstention
    assert "EVAL-TC-03" in tc_ids  # Citation grounding
    assert "EVAL-TC-04" in tc_ids  # Security bypass attack
    assert "EVAL-TC-05" in tc_ids  # Tamper detection
