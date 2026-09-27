import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def boundary():
    return json.loads((ROOT / "MODEL3B_DATA_VINTAGE_CONTRACT.json").read_text())


def test_identity():
    b = boundary()
    assert b["model"] == "3"
    assert b["workstream"] == "3B"
    assert b["branch"] == "model3-output-gap-development"


def test_bases_are_frozen():
    b = boundary()
    assert b["model3a_base_commit"] == "6f45208103a5ac1a900317a33c0038d56920ffbb"
    assert b["model2_base_commit"] == "cda24988e772cd2b96be612b7d455c54a06f44fa"
    assert b["model2_base_tag"] == "model2-bvar-v1.0.2"


def test_required_series_and_panel():
    b = boundary()
    assert b["required_series"] == ["GDPC1", "UNRATE", "PCEPILFE"]
    assert "real_gdp_level" in b["panel_columns"]
    assert "real_gdp_log" in b["panel_columns"]
    assert "core_pce_inflation" in b["panel_columns"]


def test_vintage_contract_fails_closed():
    v = boundary()["vintage_contract"]
    assert v["exact_vintage_or_governed_availability_evidence_required"] is True
    assert v["no_look_ahead_required"] is True
    assert v["publication_lags_must_be_respected"] is True
    assert v["current_revised_history_may_not_masquerade_as_real_time"] is False


def test_model2_forecasts_deferred():
    i = boundary()["integration"]
    assert i["model2_forward_gap_integration_deferred_to"] == "3G"
    assert i["model2_forecasts_allowed_in_3b"] is False


def test_no_estimation_or_predecessor_mutation():
    g = boundary()["governance"]
    assert g["estimation_allowed"] is False
    assert g["production_writes_allowed"] is False
    assert g["predecessor_modification_allowed"] is False


def test_next_authority_is_only_3c():
    assert boundary()["bootstrap"]["passing_3b_authorizes_only"] == "3C_univariate_trend_filter_benchmarks"
