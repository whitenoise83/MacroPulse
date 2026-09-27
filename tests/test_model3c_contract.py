import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def contract():
    return json.loads((ROOT / "MODEL3C_BENCHMARK_CONTRACT.json").read_text())


def test_identity_and_predecessor():
    c = contract()
    assert c["model"] == "3"
    assert c["workstream"] == "3C"
    assert c["model3b_base_commit"] == "5849b89367defdef68c0676fdcd1d2f7182bd873"


def test_exact_benchmark_families():
    f = contract()["benchmark_families"]
    assert set(f) == {
        "deterministic_linear_trend", "hp_filter",
        "one_sided_hp_filter", "hamilton_regression"
    }


def test_hp_roles_are_explicit():
    f = contract()["benchmark_families"]
    assert f["hp_filter"]["role"] == "diagnostic_benchmark"
    assert f["hp_filter"]["two_sided_full_sample"] is True
    assert f["one_sided_hp_filter"]["uses_only_information_through_origin"] is True


def test_hamilton_is_h8_p4():
    h = contract()["benchmark_families"]["hamilton_regression"]
    assert h["horizon_quarters"] == 8
    assert h["lags"] == 4


def test_no_production_selection_or_integration():
    g = contract()["governance"]
    assert g["production_winner_frozen"] is False
    assert g["automatic_selection_allowed"] is False
    assert g["automatic_promotion_allowed"] is False
    assert g["model1_integration_allowed"] is False
    assert g["model2_forecast_integration_allowed"] is False


def test_3c_only_authorizes_3d():
    assert contract()["bootstrap"]["passing_3c_authorizes_only"] == "3D_state_space_potential_output"
