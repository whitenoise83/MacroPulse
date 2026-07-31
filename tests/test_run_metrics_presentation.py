from macropulse.presentation.run_metrics import (
    dfm_rows,
    identity_rows,
    overview_rows,
    parse_metrics_json,
    selection_rows,
    weight_diagnostic_rows,
    weight_rows,
)


def sample_metrics():
    return {
        "training_observations": 137,
        "feature_count": 8,
        "imputed_features": [],
        "bridge_rmse": 1.9721203084585,
        "ar1_rmse": 4.400113480463206,
        "preferred_model": "Dynamic Factor Model",
        "preferred_sigma": 2.230642424211629,
        "interval": 0.8,
        "production_weights": {
            "Bridge Ridge": 0.4441408660563317,
            "Dynamic Factor Model": 0.5558591339436684,
        },
        "weight_diagnostics": {
            "weight_method": "inverse_rolling_rmse",
            "window": 12,
            "min_history": 8,
            "common_history": 12,
        },
        "production_selection": {
            "selected_model": "Dynamic Factor Model",
            "method": "trailing_rmse",
            "sample": "last_20",
            "observations": 20,
        },
        "dynamic_factor": {
            "status": "success",
            "converged": True,
            "iterations": 18,
            "log_likelihood": -123.456,
        },
        "model_identity": {
            "model_id": "US_GDP_NOWCAST_1A",
            "model_version": "0.5.0",
            "config_hash": "a" * 64,
        },
    }


def test_parse_metrics_json_is_safe():
    assert parse_metrics_json('{"interval": 0.8}') == {"interval": 0.8}
    assert parse_metrics_json("not-json") == {}
    assert parse_metrics_json(None) == {}


def test_overview_formats_long_values_for_people():
    rows = overview_rows(sample_metrics())
    values = {row["Metric"]: row["Value"] for row in rows}
    assert values["Bridge Ridge RMSE"] == "1.97 pp"
    assert values["AR(1) benchmark RMSE"] == "4.40 pp"
    assert values["Target forecast interval"] == "80%"
    assert values["Imputed indicators"] == "None"


def test_weights_are_percent_ready_and_sum_to_one():
    rows = weight_rows(sample_metrics())
    assert [row["Weight display"] for row in rows] == ["44.4%", "55.6%"]
    assert abs(sum(row["Weight"] for row in rows) - 1.0) < 1e-12


def test_nested_diagnostics_are_human_readable():
    metrics = sample_metrics()
    assert weight_diagnostic_rows(metrics)[0]["Value"] == "Inverse Rolling Rmse"
    assert selection_rows(metrics)[0]["Value"] == "Dynamic Factor Model"
    assert any(row["Metric"] == "EM converged" and row["Value"] == "Yes" for row in dfm_rows(metrics))
    assert identity_rows(metrics)[2]["Value"].endswith("…")
