from __future__ import annotations

from pathlib import Path

from macropulse.macro_state.versioning import load_macro_state_governance


def test_phase3_preserves_frozen_outcome_governance() -> None:
    section = load_macro_state_governance()["prospective_transition_shadow"]
    assert section["model_version"] == "0.3.8"
    assert section["promotion_authority"] == "none"
    assert section["target"]["mode"] == "fixed_horizon_90d"
    assert section["target"]["horizon_days"] == 90
    assert section["target"]["latest_revised_substitution_prohibited"] is True
    assert section["target"]["target_must_be_available_before_resolution"] is True
    assert section["persistence"]["append_only"] is True
    assert section["persistence"]["updates_prohibited"] is True
    assert section["persistence"]["deletes_prohibited"] is True
    assert section["persistence"]["outcome_before_target_availability_prohibited"] is True
    assert section["probability_contract"]["log_loss_floor"] == 1.0e-12


def test_phase3_service_contains_no_mutating_shadow_sql() -> None:
    paths = [
        Path("src/macropulse/macro_state/shadow_outcomes.py"),
        Path("src/macropulse/macro_state/shadow_outcomes_service.py"),
    ]
    prohibited = ("UPDATE ", "DELETE ", "INSERT OR REPLACE", "UPSERT ")
    for path in paths:
        raw = path.read_text(encoding="utf-8")
        text = raw.upper()
        assert all(token not in text for token in prohibited)
        assert "latest_observations" not in raw
        assert "reconstruct_actual_vintages" not in raw


def test_phase3_planned_files_exist() -> None:
    for relative in [
        "src/macropulse/macro_state/shadow_outcomes.py",
        "src/macropulse/macro_state/shadow_outcomes_service.py",
        "scripts/resolve_macro_state_shadow_outcomes.py",
    ]:
        assert Path(relative).is_file()
