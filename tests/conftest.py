"""Pytest configuration and shared test fixtures."""

import json
from pathlib import Path
import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def mes_event_payload(fixtures_dir: Path) -> dict:
    path = fixtures_dir / "events" / "mes_temp_excursion.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def lims_event_payload(fixtures_dir: Path) -> dict:
    path = fixtures_dir / "events" / "lims_oos_assay.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def bioreactor_sop_text(fixtures_dir: Path) -> str:
    path = fixtures_dir / "documents" / "SOP-PRC-042_bioreactor.md"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def equipment_calib_log(fixtures_dir: Path) -> dict:
    path = fixtures_dir / "documents" / "equipment_BR-04_calib_log.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
