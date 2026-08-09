from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
RELEASE = ROOT / "PHASE2_RELEASE.json"
CONTRACT = ROOT / "PHASE2_PLATFORM_CONTRACT.json"


def test_phase2_release_identity() -> None:
    payload = json.loads(RELEASE.read_text(encoding="utf-8"))
    assert payload["release_id"] == "MACROPULSE_PHASE2_PLATFORM_V1_0_0"
    assert payload["platform_version"] == "1.0.0"
    assert payload["lifecycle"] == "released"
    assert payload["release_tag"] == "phase2-platform-v1.0.0"


def test_release_gate_records_successful_guard_two() -> None:
    payload = json.loads(RELEASE.read_text(encoding="utf-8"))
    ci = payload["ci_release_gate"]
    assert ci["workflow"] == "Phase II Platform Guard"
    assert ci["run_number"] == 2
    assert ci["run_id"] == 31307316856
    assert ci["status"] == "success"
    assert ci["commit"].startswith("bd98dde")


def test_phase2_workstreams_are_closed() -> None:
    payload = json.loads(RELEASE.read_text(encoding="utf-8"))
    assert set(payload["phase2_workstreams"].values()) == {"complete"}


def test_model1d_remains_research_only() -> None:
    payload = json.loads(RELEASE.read_text(encoding="utf-8"))
    model1d = payload["model_suite"]["1D"]
    assert model1d["lifecycle"] == "development"
    assert model1d["version"] == "0.3.8"
    assert model1d["mode"] == "prospective_shadow"
    assert model1d["promotion_authority"] == "none"


def test_platform_contract_is_released() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["platform_version"] == "1.0.0"
    assert contract["lifecycle"] == "released"
    assert contract["release_tag"] == "phase2-platform-v1.0.0"
