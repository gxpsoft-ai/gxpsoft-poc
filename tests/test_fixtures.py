"""Unit tests verifying synthetic GxP fixtures consistency and integrity."""

import json
from pathlib import Path
import pytest

from gxpsoft.models.event import QualityEvent


def test_mes_and_lims_fixtures_consistency(fixtures_dir: Path) -> None:
    mes_path = fixtures_dir / "events" / "mes_temp_excursion.json"
    lims_path = fixtures_dir / "events" / "lims_oos_assay.json"

    with open(mes_path, "r", encoding="utf-8") as f:
        mes_data = json.load(f)
    with open(lims_path, "r", encoding="utf-8") as f:
        lims_data = json.load(f)

    mes_event = QualityEvent(**mes_data)
    lims_event = QualityEvent(**lims_data)

    # Cross-reference validation
    assert mes_event.batch_id == lims_event.batch_id == "BIO-2026-088"
    assert mes_event.product_id == lims_event.product_id == "PROD-MAB-701"
    assert mes_event.site_id == lims_event.site_id == "SITE-SF-01"


def test_calibration_log_fixture(fixtures_dir: Path) -> None:
    calib_path = fixtures_dir / "documents" / "equipment_BR-04_calib_log.json"
    with open(calib_path, "r", encoding="utf-8") as f:
        calib_data = json.load(f)

    assert calib_data["equipment_id"] == "BR-04"
    rtd = next(s for s in calib_data["sensors"] if s["sensor_id"] == "RTD-04B")
    assert rtd["calibration_status"] == "EXPIRED"
    assert rtd["days_overdue_as_of_event"] == 10


def test_batch_genealogy_fixture(fixtures_dir: Path) -> None:
    batch_path = fixtures_dir / "documents" / "batch_genealogy_BIO-2026-088.json"
    with open(batch_path, "r", encoding="utf-8") as f:
        batch_data = json.load(f)

    assert batch_data["batch_id"] == "BIO-2026-088"
    assert batch_data["assigned_bioreactor"] == "BR-04"
    assert len(batch_data["bill_of_materials"]) >= 2
