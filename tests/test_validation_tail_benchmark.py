import pandas as pd

from macropulse.governance.validation import _accuracy_eligible_tail_benchmark


STATIC = [
    "Bridge Ridge",
    "Dynamic Factor Model",
    "Bridge–DFM Ensemble",
    "Rolling Bridge–DFM Ensemble",
]


def test_inaccurate_low_p90_model_is_excluded_from_tail_benchmark() -> None:
    frame = pd.DataFrame(
        {
            "rmse": [4.40, 2.86, 3.44, 3.72, 2.86],
            "mae": [2.19, 1.86, 1.98, 2.04, 1.86],
            "p90_abs_error": [3.37, 5.01, 4.20, 4.50, 5.01],
            "max_abs_error": [23.18, 8.79, 15.52, 18.58, 8.79],
        },
        index=[
            "Bridge Ridge",
            "Dynamic Factor Model",
            "Bridge–DFM Ensemble",
            "Rolling Bridge–DFM Ensemble",
            "Stable Stage Policy",
        ],
    )
    result = _accuracy_eligible_tail_benchmark(
        frame,
        "Stable Stage Policy",
        STATIC,
        rmse_limit=1.10,
        mae_limit=1.10,
        max_error_limit=1.25,
    )
    assert "Bridge Ridge" not in result["eligible_models"]
    assert result["best_p90_model"] == "Dynamic Factor Model"
    assert result["p90_ratio"] == 1.0


def test_accuracy_competitive_low_p90_model_remains_eligible() -> None:
    frame = pd.DataFrame(
        {
            "rmse": [2.75, 2.89, 2.69, 2.69, 2.69],
            "mae": [1.90, 1.88, 1.82, 1.81, 1.81],
            "p90_abs_error": [4.88, 5.10, 4.80, 4.74, 4.74],
            "max_abs_error": [8.21, 8.95, 8.20, 8.07, 8.07],
        },
        index=[
            "Bridge Ridge",
            "Dynamic Factor Model",
            "Bridge–DFM Ensemble",
            "Rolling Bridge–DFM Ensemble",
            "Stable Stage Policy",
        ],
    )
    result = _accuracy_eligible_tail_benchmark(
        frame,
        "Stable Stage Policy",
        STATIC,
        rmse_limit=1.10,
        mae_limit=1.10,
        max_error_limit=1.25,
    )
    assert "Bridge Ridge" in result["eligible_models"]
    assert result["best_p90_model"] == "Rolling Bridge–DFM Ensemble"
    assert abs(result["p90_ratio"] - 1.0) < 1e-12
