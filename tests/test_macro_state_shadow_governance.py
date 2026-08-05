from __future__ import annotations

from pathlib import Path

import yaml


def test_v038_prospective_shadow_governance_is_frozen() -> None:
    path = Path("config") / "macro_state_governance.yml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert config["model"]["version"] == "0.3.8"
    assert config["model"]["lifecycle_status"] == "development"

    shadow = config["prospective_transition_shadow"]
    assert shadow["model_version"] == "0.3.8"
    assert shadow["promotion_authority"] == "none"
    assert shadow["frozen_source"]["model_version"] == "0.3.6"
    assert (
        shadow["frozen_source"]["candidate_id"]
        == "expanding_robust_z__policy__equal__sensitive__independent_normal"
    )
    assert shadow["comparator"]["benchmark_id"] == "rolling_frequency"
    assert shadow["comparator"]["adaptive_switching_prohibited"] is True
    assert shadow["comparator"]["blending_prohibited"] is True
    assert shadow["target"]["mode"] == "fixed_horizon_90d"
    assert shadow["target"]["horizon_days"] == 90
    assert (
        shadow["target"]["latest_revised_substitution_prohibited"] is True
    )

    assert shadow["probability_contract"]["family_order"] == [
        "adverse_supply",
        "benign_expansion",
        "contraction",
        "inflationary_expansion",
        "mixed",
    ]
    assert shadow["persistence"]["append_only"] is True
    assert shadow["persistence"]["updates_prohibited"] is True
    assert shadow["persistence"]["deletes_prohibited"] is True
    assert (
        shadow["persistence"]["outcome_before_target_availability_prohibited"]
        is True
    )
    assert shadow["required_dimensions"] == [
        "growth",
        "inflation",
        "labour",
    ]
    assert shadow["minimum_evidence"]["complete_target_months"] == 12
