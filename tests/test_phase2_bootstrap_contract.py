from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
BOUNDARY = ROOT / "PHASE2_BOUNDARY.json"
PLAN = ROOT / "MACROPULSE_PHASE2_PLAN.md"
ARCHITECTURE = ROOT / "docs" / "PHASE2_ARCHITECTURE.md"


def test_phase2_bootstrap_files_exist() -> None:
    assert BOUNDARY.is_file()
    assert PLAN.is_file()
    assert ARCHITECTURE.is_file()


def test_phase2_boundary_is_platform_only() -> None:
    payload = json.loads(BOUNDARY.read_text(encoding="utf-8"))

    assert payload["phase"] == "II"
    assert payload["branch"] == "phase2-platform-development"
    assert payload["base_commit"] == "048c1a6"
    assert payload["phase2_may_change_model_specifications"] is False
    assert payload["phase2_may_tune_model1d_on_prospective_outcomes"] is False
    assert payload["phase2_may_move_model1d_release_tags"] is False
    assert payload["phase2_initial_model_logic_changes"] is False


def test_model_suite_identity_is_preserved() -> None:
    payload = json.loads(BOUNDARY.read_text(encoding="utf-8"))
    suite = payload["model_suite"]

    assert suite["1A"] == {"status": "production", "version": "1.0.0"}
    assert suite["1B"] == {"status": "production", "version": "1.0.0"}
    assert suite["1C"] == {"status": "production", "version": "1.0.0"}

    model1d = suite["1D"]
    assert model1d["status"] == "development"
    assert model1d["version"] == "0.3.8"
    assert model1d["mode"] == "prospective_shadow"
    assert model1d["promotion_authority"] == "none"


def test_plan_preserves_model1d_research_boundary() -> None:
    text = PLAN.read_text(encoding="utf-8")
    required = (
        "change the frozen Model 1D v0.3.8 source candidate",
        "tune any model against Model 1D prospective outcomes",
        "move either published Model 1D v0.3.8 release tag",
        "No automatic production promotion",
    )
    for phrase in required:
        assert phrase in text


def test_architecture_keeps_model_logic_out_of_platform_layer() -> None:
    text = ARCHITECTURE.read_text(encoding="utf-8")
    assert "Phase II separates model science from platform operations." in text
    assert "Model 1D not eligible -> skip safely" in text
    assert "Unknown lifecycle/version -> fail closed." in text
