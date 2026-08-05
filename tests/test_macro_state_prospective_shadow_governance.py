from __future__ import annotations

from macropulse.macro_state.prospective_shadow import prospective_shadow_plan
from macropulse.macro_state.versioning import load_macro_state_governance


def test_v038_prediction_engine_is_operationally_pinned() -> None:
    config = load_macro_state_governance()
    plan = prospective_shadow_plan(config)

    assert plan.model_version == "0.3.8"
    assert plan.source_version == "0.3.6"
    assert (
        plan.source_candidate_id
        == "expanding_robust_z__policy__equal__sensitive__independent_normal"
    )
    assert (
        plan.source_evidence_stem
        == "model1d_fixed_horizon_c99ac096-a9cb-4e39-b976-b0d4cfe018a1"
    )
    assert (
        plan.source_stability_id
        == "4d97b730-7dcb-4ee6-9f89-bf5fff542a9d"
    )
    assert (
        plan.source_core_candidate_id
        == "expanding_robust_z__policy__equal__sensitive"
    )
    assert plan.primary_comparator == "rolling_frequency"
    assert plan.target_mode == "fixed_horizon_90d"
    assert plan.target_horizon_days == 90
    assert plan.rolling_window_months == 12
    assert plan.uncertainty_draws == 1024
    assert plan.random_seed == 13030
    assert plan.robust_minimum_history == 18
    assert plan.robust_clip == 2.0
