from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import binomtest


DEFAULT_INTERVAL_COVERAGE = 0.80
METRIC_COLUMNS = [
    "model_name",
    "observations",
    "rmse",
    "trimmed_rmse_10",
    "mae",
    "median_ae",
    "max_abs_error",
    "p90_abs_error",
    "bias",
    "direction_accuracy",
    "positive_base_rate_accuracy",
    "direction_skill",
    "interval_coverage",
    "average_interval_width",
    "median_interval_width",
    "interval_score_80",
    "win_rate",
]


def interval_score(
    actual: pd.Series,
    lower: pd.Series,
    upper: pd.Series,
    coverage: float = DEFAULT_INTERVAL_COVERAGE,
) -> pd.Series:
    """Winkler interval score; lower values are better."""
    if not 0 < coverage < 1:
        raise ValueError("coverage must be between zero and one.")
    alpha = 1.0 - coverage
    width = upper - lower
    below = (2.0 / alpha) * (lower - actual).clip(lower=0.0)
    above = (2.0 / alpha) * (actual - upper).clip(lower=0.0)
    return width + below + above


def wilson_interval(successes: int, observations: int, confidence: float = 0.95) -> tuple[float, float]:
    if observations <= 0:
        return float("nan"), float("nan")
    # 1.959963984540054 is the two-sided 95% standard-normal critical value.
    z = 1.959963984540054 if confidence == 0.95 else 1.959963984540054
    phat = successes / observations
    denominator = 1.0 + z**2 / observations
    centre = (phat + z**2 / (2.0 * observations)) / denominator
    radius = (
        z
        * math.sqrt(
            phat * (1.0 - phat) / observations
            + z**2 / (4.0 * observations**2)
        )
        / denominator
    )
    return max(0.0, centre - radius), min(1.0, centre + radius)


def coverage_test(
    covered: pd.Series,
    target_coverage: float = DEFAULT_INTERVAL_COVERAGE,
) -> dict[str, float | int | bool]:
    clean = covered.dropna().astype(bool)
    observations = int(len(clean))
    successes = int(clean.sum())
    if observations == 0:
        return {
            "observations": 0,
            "covered": 0,
            "coverage": float("nan"),
            "p_value": float("nan"),
            "ci_lower": float("nan"),
            "ci_upper": float("nan"),
            "target_inside_95_ci": False,
        }
    test = binomtest(successes, observations, p=target_coverage, alternative="two-sided")
    lower, upper = wilson_interval(successes, observations)
    return {
        "observations": observations,
        "covered": successes,
        "coverage": successes / observations,
        "p_value": float(test.pvalue),
        "ci_lower": lower,
        "ci_upper": upper,
        "target_inside_95_ci": bool(lower <= target_coverage <= upper),
    }



def clustered_coverage_test(
    results: pd.DataFrame,
    model_name: str,
    target_coverage: float = DEFAULT_INTERVAL_COVERAGE,
    cluster_column: str = "target_period",
    bootstrap_samples: int = 5000,
    random_seed: int = 42,
) -> dict[str, float | int | bool]:
    """Cluster-aware coverage test for repeated stage forecasts per quarter.

    Forecast stages for the same GDP quarter share one realised outcome, so the
    pooled Bernoulli independence assumption is inappropriate. The bootstrap
    resamples target-quarter cluster means and recentres them under the null.
    """
    required = {"model_name", "actual", "lower_80", "upper_80", cluster_column}
    missing = required.difference(results.columns)
    if missing:
        raise ValueError(f"Clustered coverage test is missing columns: {sorted(missing)}")
    frame = results.loc[results["model_name"] == model_name].dropna(
        subset=["actual", "lower_80", "upper_80", cluster_column]
    ).copy()
    if frame.empty:
        return {
            "clusters": 0,
            "forecasts": 0,
            "coverage": float("nan"),
            "p_value": float("nan"),
            "ci_lower": float("nan"),
            "ci_upper": float("nan"),
            "target_inside_95_ci": False,
        }
    frame["covered"] = (
        (frame["actual"] >= frame["lower_80"])
        & (frame["actual"] <= frame["upper_80"])
    ).astype(float)
    cluster_means = frame.groupby(cluster_column)["covered"].mean().to_numpy(dtype=float)
    observed = float(cluster_means.mean())
    clusters = int(cluster_means.size)
    if clusters < 2:
        return {
            "clusters": clusters,
            "forecasts": int(len(frame)),
            "coverage": observed,
            "p_value": float("nan"),
            "ci_lower": observed,
            "ci_upper": observed,
            "target_inside_95_ci": bool(np.isclose(observed, target_coverage)),
        }
    rng = np.random.default_rng(random_seed)
    indices = rng.integers(0, clusters, size=(bootstrap_samples, clusters))
    bootstrap_means = cluster_means[indices].mean(axis=1)
    ci_lower, ci_upper = np.quantile(bootstrap_means, [0.025, 0.975])
    centred = cluster_means - observed
    null_samples = target_coverage + centred[indices].mean(axis=1)
    observed_distance = abs(observed - target_coverage)
    null_distances = np.abs(null_samples - target_coverage)
    p_value = float((np.sum(null_distances >= observed_distance) + 1) / (bootstrap_samples + 1))
    return {
        "clusters": clusters,
        "forecasts": int(len(frame)),
        "coverage": observed,
        "p_value": p_value,
        "ci_lower": float(ci_lower),
        "ci_upper": float(ci_upper),
        "target_inside_95_ci": bool(ci_lower <= target_coverage <= ci_upper),
    }

def _prepare_results(results: pd.DataFrame) -> pd.DataFrame:
    required = {
        "model_name",
        "point_forecast",
        "actual",
        "lower_80",
        "upper_80",
    }
    missing = required.difference(results.columns)
    if missing:
        raise ValueError(f"Backtest results are missing columns: {sorted(missing)}")

    clean = results.dropna(subset=["point_forecast", "actual"]).copy()
    if clean.empty:
        return clean

    if "forecast_date" not in clean.columns:
        clean["forecast_date"] = np.arange(len(clean))
    clean["error"] = clean["point_forecast"] - clean["actual"]
    clean["abs_error"] = clean["error"].abs()
    clean["squared_error"] = clean["error"].pow(2)
    clean["direction_correct"] = (
        np.sign(clean["point_forecast"]) == np.sign(clean["actual"])
    )
    clean["interval_width"] = clean["upper_80"] - clean["lower_80"]
    clean["interval_covered"] = (
        (clean["actual"] >= clean["lower_80"])
        & (clean["actual"] <= clean["upper_80"])
    )
    clean["interval_score_80"] = interval_score(
        clean["actual"], clean["lower_80"], clean["upper_80"]
    )
    clean["positive_base_correct"] = clean["actual"] >= 0

    period_keys = ["forecast_date"]
    if "target_period" in clean.columns:
        period_keys.append("target_period")
    min_error = clean.groupby(period_keys)["abs_error"].transform("min")
    clean["is_winner"] = np.isclose(clean["abs_error"], min_error, rtol=0, atol=1e-12)
    winner_count = clean.groupby(period_keys)["is_winner"].transform("sum")
    clean["win_credit"] = np.where(clean["is_winner"], 1.0 / winner_count, 0.0)
    return clean


def _upper_trimmed_rmse(squared_errors: pd.Series, trim_fraction: float = 0.10) -> float:
    values = np.sort(squared_errors.dropna().to_numpy(dtype=float))
    if values.size == 0:
        return float("nan")
    remove = int(math.floor(values.size * trim_fraction))
    if remove > 0 and values.size - remove >= 1:
        values = values[:-remove]
    return float(np.sqrt(values.mean()))


def calculate_backtest_metrics(results: pd.DataFrame) -> pd.DataFrame:
    """Calculate robust model-level forecast and interval metrics."""
    if results.empty:
        return pd.DataFrame(columns=METRIC_COLUMNS)

    clean = _prepare_results(results)
    if clean.empty:
        return pd.DataFrame(columns=METRIC_COLUMNS)

    rows: list[dict] = []
    for model_name, group in clean.groupby("model_name", sort=True):
        direction_accuracy = float(group["direction_correct"].mean())
        base_rate = float(group["positive_base_correct"].mean())
        rows.append(
            {
                "model_name": model_name,
                "observations": int(len(group)),
                "rmse": float(np.sqrt(group["squared_error"].mean())),
                "trimmed_rmse_10": _upper_trimmed_rmse(group["squared_error"]),
                "mae": float(group["abs_error"].mean()),
                "median_ae": float(group["abs_error"].median()),
                "max_abs_error": float(group["abs_error"].max()),
                "p90_abs_error": float(group["abs_error"].quantile(0.90)),
                "bias": float(group["error"].mean()),
                "direction_accuracy": direction_accuracy,
                "positive_base_rate_accuracy": base_rate,
                "direction_skill": direction_accuracy - base_rate,
                "interval_coverage": float(group["interval_covered"].mean()),
                "average_interval_width": float(group["interval_width"].mean()),
                "median_interval_width": float(group["interval_width"].median()),
                "interval_score_80": float(group["interval_score_80"].mean()),
                "win_rate": float(group["win_credit"].mean()),
            }
        )

    return pd.DataFrame(rows, columns=METRIC_COLUMNS).sort_values("rmse")


def calculate_regime_metrics(results: pd.DataFrame) -> pd.DataFrame:
    """Return full-sample, economic-regime, and trailing-20-quarter metrics."""
    if results.empty:
        return pd.DataFrame(columns=["sample", *METRIC_COLUMNS])

    frame = results.copy()
    if "target_period" not in frame.columns:
        raise ValueError("Regime metrics require target_period.")
    periods = pd.PeriodIndex(frame["target_period"].astype(str), freq="Q")
    frame["_period"] = periods

    samples: list[tuple[str, pd.DataFrame]] = [("Full sample", frame)]
    samples.extend(
        [
            ("Pre-pandemic (through 2019Q4)", frame.loc[frame["_period"] <= pd.Period("2019Q4")]),
            (
                "Pandemic (2020Q1–2021Q2)",
                frame.loc[
                    (frame["_period"] >= pd.Period("2020Q1"))
                    & (frame["_period"] <= pd.Period("2021Q2"))
                ],
            ),
            ("Post-pandemic (from 2021Q3)", frame.loc[frame["_period"] >= pd.Period("2021Q3")]),
        ]
    )

    unique_periods = sorted(frame["_period"].dropna().unique())
    if unique_periods:
        trailing_periods = set(unique_periods[-20:])
        samples.append(("Last 20 quarters", frame.loc[frame["_period"].isin(trailing_periods)]))

    outputs: list[pd.DataFrame] = []
    for sample_name, sample_frame in samples:
        metrics = calculate_backtest_metrics(sample_frame.drop(columns=["_period"], errors="ignore"))
        if not metrics.empty:
            metrics.insert(0, "sample", sample_name)
            outputs.append(metrics)
    if not outputs:
        return pd.DataFrame(columns=["sample", *METRIC_COLUMNS])
    return pd.concat(outputs, ignore_index=True)


def calculate_stage_regime_metrics(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return pd.DataFrame(columns=["forecast_stage", "sample", *METRIC_COLUMNS])
    if "forecast_stage" not in results.columns:
        raise ValueError("Stage-regime metrics require forecast_stage.")
    outputs: list[pd.DataFrame] = []
    for stage, group in results.groupby("forecast_stage", sort=False):
        metrics = calculate_regime_metrics(group)
        if not metrics.empty:
            metrics.insert(0, "forecast_stage", stage)
            outputs.append(metrics)
    if not outputs:
        return pd.DataFrame(columns=["forecast_stage", "sample", *METRIC_COLUMNS])
    return pd.concat(outputs, ignore_index=True)


def estimate_inverse_rmse_weights(
    results: pd.DataFrame,
    model_names: tuple[str, ...] = ("Bridge Ridge", "Dynamic Factor Model"),
    window: int = 12,
    min_history: int = 8,
    min_weight: float = 0.10,
    max_weight: float = 0.70,
) -> tuple[dict[str, float], dict]:
    """Estimate weights using only supplied historical forecast errors."""
    if len(model_names) < 2:
        raise ValueError("At least two model names are required.")
    equal = {name: 1.0 / len(model_names) for name in model_names}
    diagnostics = {
        "weight_method": "equal_fallback",
        "window": int(window),
        "min_history": int(min_history),
        "common_history": 0,
        "rolling_rmse": {},
    }
    if results.empty:
        return equal, diagnostics

    required = {"model_name", "forecast_date", "point_forecast", "actual"}
    if required.difference(results.columns):
        return equal, diagnostics

    clean = results.loc[results["model_name"].isin(model_names)].dropna(
        subset=["point_forecast", "actual"]
    ).copy()
    if clean.empty:
        return equal, diagnostics
    clean["squared_error"] = (clean["point_forecast"] - clean["actual"]) ** 2
    pivot = clean.pivot_table(
        index="forecast_date", columns="model_name", values="squared_error", aggfunc="first"
    ).sort_index()
    pivot = pivot.reindex(columns=list(model_names)).dropna()
    if window > 0:
        pivot = pivot.tail(window)
    diagnostics["common_history"] = int(len(pivot))
    if len(pivot) < min_history:
        return equal, diagnostics

    rmse = np.sqrt(pivot.mean())
    if not np.isfinite(rmse.to_numpy()).all() or (rmse <= 0).any():
        return equal, diagnostics

    if len(model_names) * min_weight > 1.0 + 1e-12:
        raise ValueError("Minimum ensemble weights are infeasible.")
    if len(model_names) * max_weight < 1.0 - 1e-12:
        raise ValueError("Maximum ensemble weights are infeasible.")

    inverse = 1.0 / rmse
    raw = (inverse / inverse.sum()).to_numpy(dtype=float)
    lower_lambda = float(np.min(raw - max_weight))
    upper_lambda = float(np.max(raw - min_weight))
    projected = raw.copy()
    for _ in range(100):
        midpoint = 0.5 * (lower_lambda + upper_lambda)
        projected = np.clip(raw - midpoint, min_weight, max_weight)
        if projected.sum() > 1.0:
            lower_lambda = midpoint
        else:
            upper_lambda = midpoint
    projected = np.clip(raw - upper_lambda, min_weight, max_weight)
    projected = projected / projected.sum()
    normalised = pd.Series(projected, index=list(model_names), dtype=float)

    weights = {name: float(normalised[name]) for name in model_names}
    diagnostics.update(
        {
            "weight_method": "inverse_rolling_rmse",
            "rolling_rmse": {name: float(rmse[name]) for name in model_names},
            "weights": weights,
        }
    )
    return weights, diagnostics


def calculate_stage_metrics(results: pd.DataFrame) -> pd.DataFrame:
    """Calculate model metrics separately for each within-quarter forecast stage."""
    extra_columns = [
        "average_days_to_release",
        "raw_interval_coverage",
        "raw_average_interval_width",
        "coverage_p_value",
        "coverage_ci_lower",
        "coverage_ci_upper",
        "target_inside_95_ci",
    ]
    if results.empty:
        return pd.DataFrame(columns=["forecast_stage", *METRIC_COLUMNS, *extra_columns])
    if "forecast_stage" not in results.columns:
        raise ValueError("Stage metrics require forecast_stage.")

    outputs: list[pd.DataFrame] = []
    for stage, group in results.groupby("forecast_stage", sort=False):
        metrics = calculate_backtest_metrics(group)
        if metrics.empty:
            continue
        days = (
            group.groupby("model_name")["days_to_release"].mean()
            if "days_to_release" in group.columns
            else pd.Series(dtype=float)
        )
        metrics.insert(0, "forecast_stage", stage)
        metrics["average_days_to_release"] = metrics["model_name"].map(days)

        raw_coverage: dict[str, float] = {}
        raw_width: dict[str, float] = {}
        if {"raw_lower_80", "raw_upper_80"}.issubset(group.columns):
            raw = group.copy()
            raw["raw_covered"] = (
                (raw["actual"] >= raw["raw_lower_80"])
                & (raw["actual"] <= raw["raw_upper_80"])
            )
            raw["raw_width"] = raw["raw_upper_80"] - raw["raw_lower_80"]
            raw_coverage = raw.groupby("model_name")["raw_covered"].mean().to_dict()
            raw_width = raw.groupby("model_name")["raw_width"].mean().to_dict()
        metrics["raw_interval_coverage"] = metrics["model_name"].map(raw_coverage)
        metrics["raw_average_interval_width"] = metrics["model_name"].map(raw_width)

        tests = {
            model_name: coverage_test(model_group["interval_covered"])
            for model_name, model_group in _prepare_results(group).groupby("model_name")
        }
        metrics["coverage_p_value"] = metrics["model_name"].map(
            {name: values["p_value"] for name, values in tests.items()}
        )
        metrics["coverage_ci_lower"] = metrics["model_name"].map(
            {name: values["ci_lower"] for name, values in tests.items()}
        )
        metrics["coverage_ci_upper"] = metrics["model_name"].map(
            {name: values["ci_upper"] for name, values in tests.items()}
        )
        metrics["target_inside_95_ci"] = metrics["model_name"].map(
            {name: values["target_inside_95_ci"] for name, values in tests.items()}
        )
        outputs.append(metrics)
    if not outputs:
        return pd.DataFrame(columns=["forecast_stage", *METRIC_COLUMNS, *extra_columns])
    return pd.concat(outputs, ignore_index=True)
