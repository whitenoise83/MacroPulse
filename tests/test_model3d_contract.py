import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads(
    (ROOT / "MODEL3D_STATE_SPACE_CONTRACT.json").read_text(encoding="utf-8")
)


def test_identity_and_exact_predecessor():
    assert CONTRACT["model"] == "3"
    assert CONTRACT["workstream"] == "3D"
    assert CONTRACT["model3c_base_commit"] == "dfcee48d0a0391f3187cf103c7c906d4ecf78892"


def test_input_is_univariate_gdp_not_joint_complete_panel():
    inp = CONTRACT["input_contract"]
    assert inp["required_series"] == "GDPC1"
    assert inp["required_transform"] == "natural_log_real_gdp"
    assert inp["joint_complete_model3b_panel_required"] is False


def test_state_space_equations_and_state_vector_are_frozen():
    spec = CONTRACT["state_space_specification"]
    assert spec["observation_equation"] == "y_t = ystar_t + gap_t"
    assert spec["state_vector"] == [
        "potential_log_output",
        "trend_growth",
        "output_gap",
        "output_gap_lag1",
    ]
    assert spec["measurement_error_variance"] == 0.0
    assert spec["fixed_parameters"]["sigma_potential"] == 0.0
    assert spec["estimated_parameters"] == ["sigma_trend_growth", "sigma_gap", "phi1", "phi2"]
    assert spec["stationary_gap_ar2_required"] is True


def test_filtered_and_smoothed_outputs_are_distinct():
    out = CONTRACT["output_contract"]
    assert out["filtered_full_sample_parameters_estimates_required"] is True
    assert out["filtered_full_sample_parameters_strict_real_time"] is False
    assert out["strict_real_time_endpoint_estimation_deferred_to"] == "3H"
    assert out["smoothed_revised_estimates_required"] is True
    assert out["filtered_and_smoothed_must_be_separately_labelled"] is True
    assert CONTRACT["governance"]["smoothed_estimate_may_masquerade_as_real_time"] is False
    assert CONTRACT["governance"]["filtered_full_sample_parameters_may_masquerade_as_real_time"] is False


def test_3d_excludes_multivariate_and_downstream_integration():
    integration = CONTRACT["integration"]
    assert integration["inflation_allowed"] is False
    assert integration["unemployment_allowed"] is False
    assert integration["model1_integration_allowed"] is False
    assert integration["model2_forecast_integration_allowed"] is False
    assert integration["multivariate_slack_deferred_to"] == "3E"
    assert integration["model1_current_state_integration_deferred_to"] == "3F"
    assert integration["model2_forward_gap_integration_deferred_to"] == "3G"


def test_no_production_selection_or_predecessor_mutation():
    gov = CONTRACT["governance"]
    assert gov["production_winner_frozen"] is False
    assert gov["automatic_selection_allowed"] is False
    assert gov["automatic_promotion_allowed"] is False
    assert gov["predecessor_modification_allowed"] is False
    assert gov["database_writes_allowed"] is False


def test_dependencies_recorded_but_manifest_change_deferred():
    est = CONTRACT["estimation"]
    assert est["engine"] == "statsmodels_state_space_mlemodel"
    assert est["optimizer"] == "powell"
    assert est["boundary_pile_up_guard_required"] is True
    assert est["numerical_dependencies"]["statsmodels"] == ">=0.14"
    assert est["dependency_manifest_normalization_deferred_to"] == "3I"


def test_only_3e_is_authorized_next():
    assert CONTRACT["bootstrap"]["new_paths_only"] is True
    assert CONTRACT["bootstrap"]["passing_3d_authorizes_only"] == \
        "3E_multivariate_macroeconomic_slack"
