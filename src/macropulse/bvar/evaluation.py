from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from math import log, pi, sqrt
from typing import Mapping

import numpy as np
import pandas as pd

from macropulse.bvar.benchmarks import (
    BENCHMARK_IDS,
    simulate_all_benchmarks,
)
from macropulse.bvar.model import (
    FORECAST_HORIZONS,
    VARIABLES,
    candidate_grid,
    fit_bvar,
    point_forecast,
)
from macropulse.bvar.probabilistic import simulate_posterior_predictive


PRIMARY_SELECTION_HORIZONS = (1, 2, 4)
MINIMUM_SELECTION_CELL_COUNT = 8
CENTRAL_COVERAGES = (0.50, 0.80, 0.95)


@dataclass(frozen=True)
class OutcomeObservation:
    horizon: int
    target_quarter: str
    values: np.ndarray
    outcome_as_of_date: date
    outcome_snapshot_hash: str


def derived_seed(
    base_seed: int,
    origin_id: str,
    model_id: str,
) -> int:
    payload = f"{int(base_seed)}|{origin_id}|{model_id}"
    digest = sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % (2**63)


def _central_interval(
    values: np.ndarray,
    coverage: float,
) -> tuple[float, float]:
    alpha = 1.0 - float(coverage)
    lower = float(np.quantile(values, alpha / 2.0))
    upper = float(np.quantile(values, 1.0 - alpha / 2.0))
    return lower, upper


def empirical_crps(draws: np.ndarray, outcome: float) -> float:
    values = np.asarray(draws, dtype=float)
    if values.ndim != 1 or len(values) < 2:
        raise ValueError("CRPS requires at least two one-dimensional draws.")
    if not np.isfinite(values).all() or not np.isfinite(outcome):
        raise ValueError("CRPS inputs must be finite.")

    ordered = np.sort(values)
    n = len(ordered)
    first = float(np.mean(np.abs(ordered - float(outcome))))
    ranks = np.arange(1, n + 1, dtype=float)
    coefficient = 2.0 * ranks - n - 1.0
    second = float(np.sum(coefficient * ordered) / (n**2))
    value = first - second
    if value < -1e-10 or not np.isfinite(value):
        raise ValueError("CRPS calculation produced an invalid value.")
    return max(0.0, value)


def kde_log_predictive_density(
    draws: np.ndarray,
    outcome: float,
) -> float:
    values = np.asarray(draws, dtype=float)
    if values.ndim != 1 or len(values) < 2:
        raise ValueError("Log density requires one-dimensional predictive draws.")
    if not np.isfinite(values).all() or not np.isfinite(outcome):
        raise ValueError("Log density inputs must be finite.")

    n = len(values)
    scale = float(np.std(values, ddof=1))
    if not np.isfinite(scale):
        raise ValueError("Predictive draw scale is non-finite.")
    if scale <= 1e-12:
        scale = max(abs(float(np.mean(values))) * 1e-8, 1e-8)

    bandwidth = 1.06 * scale * (n ** (-1.0 / 5.0))
    bandwidth = max(float(bandwidth), 1e-10)
    z = (float(outcome) - values) / bandwidth
    log_kernel = (
        -0.5 * z**2
        - 0.5 * log(2.0 * pi)
        - log(bandwidth)
    )
    maximum = float(np.max(log_kernel))
    log_density = maximum + log(
        float(np.mean(np.exp(log_kernel - maximum)))
    )
    if not np.isfinite(log_density):
        raise ValueError("Log predictive density became non-finite.")
    return log_density


def interval_score(
    lower: float,
    upper: float,
    outcome: float,
    coverage: float,
) -> float:
    if lower > upper:
        raise ValueError("Interval lower bound exceeds upper bound.")
    alpha = 1.0 - float(coverage)
    score = upper - lower
    if outcome < lower:
        score += (2.0 / alpha) * (lower - outcome)
    elif outcome > upper:
        score += (2.0 / alpha) * (outcome - upper)
    return float(score)


def score_predictive_draws(
    *,
    point_forecast_value: float,
    draws: np.ndarray,
    outcome: float,
) -> dict[str, float | bool]:
    values = np.asarray(draws, dtype=float)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError("Predictive draws must be a finite vector.")
    if not np.isfinite(point_forecast_value) or not np.isfinite(outcome):
        raise ValueError("Point forecast and outcome must be finite.")

    error = float(point_forecast_value - outcome)
    result: dict[str, float | bool] = {
        "error": error,
        "abs_error": abs(error),
        "squared_error": error**2,
        "log_predictive_density": kde_log_predictive_density(
            values,
            outcome,
        ),
        "crps": empirical_crps(values, outcome),
    }

    for coverage in CENTRAL_COVERAGES:
        suffix = int(round(coverage * 100))
        lower, upper = _central_interval(values, coverage)
        result[f"lower_{suffix}"] = lower
        result[f"upper_{suffix}"] = upper
        result[f"covered_{suffix}"] = bool(
            lower <= outcome <= upper
        )
        result[f"interval_score_{suffix}"] = interval_score(
            lower,
            upper,
            outcome,
            coverage,
        )
    return result


def _records_for_model(
    *,
    origin_id: str,
    origin_quarter: str,
    origin_as_of_date: date,
    model_id: str,
    model_family: str,
    candidate_id: str | None,
    lags: int | None,
    shrinkage: float | None,
    point: np.ndarray,
    draws: np.ndarray,
    horizons: tuple[int, ...],
    outcomes: Mapping[int, OutcomeObservation],
    seed: int,
    simulations: int,
    estimation_panel_hash: str,
) -> list[dict]:
    if point.shape != (len(horizons), len(VARIABLES)):
        raise ValueError("Point forecast matrix has unexpected shape.")
    if draws.shape != (
        simulations,
        len(horizons),
        len(VARIABLES),
    ):
        raise ValueError("Predictive draw tensor has unexpected shape.")

    rows: list[dict] = []
    for horizon_position, horizon in enumerate(horizons):
        outcome = outcomes[horizon]
        if outcome.horizon != horizon:
            raise ValueError("Outcome horizon lineage mismatch.")
        if outcome.outcome_as_of_date <= origin_as_of_date:
            raise ValueError(
                "Outcome exact-vintage date must be later than forecast origin."
            )
        values = np.asarray(outcome.values, dtype=float)
        if values.shape != (len(VARIABLES),):
            raise ValueError("Outcome vector has unexpected shape.")

        for variable_position, variable in enumerate(VARIABLES):
            metrics = score_predictive_draws(
                point_forecast_value=float(
                    point[horizon_position, variable_position]
                ),
                draws=draws[:, horizon_position, variable_position],
                outcome=float(values[variable_position]),
            )
            row = {
                "origin_id": origin_id,
                "origin_quarter": origin_quarter,
                "origin_as_of_date": origin_as_of_date,
                "target_quarter": outcome.target_quarter,
                "outcome_as_of_date": outcome.outcome_as_of_date,
                "outcome_snapshot_hash": outcome.outcome_snapshot_hash,
                "horizon": int(horizon),
                "model_id": model_id,
                "model_family": model_family,
                "candidate_id": candidate_id,
                "lags": lags,
                "shrinkage": shrinkage,
                "variable": variable,
                "point_forecast": float(
                    point[horizon_position, variable_position]
                ),
                "outcome": float(values[variable_position]),
                "seed": int(seed),
                "simulations": int(simulations),
                "estimation_panel_hash": estimation_panel_hash,
            }
            row.update(metrics)
            rows.append(row)
    return rows


def evaluate_origin(
    panel: pd.DataFrame,
    *,
    origin_id: str,
    origin_quarter: str,
    origin_as_of_date: date,
    outcomes: Mapping[int, OutcomeObservation],
    simulations: int,
    base_seed: int,
) -> pd.DataFrame:
    horizons = tuple(sorted(int(value) for value in outcomes))
    if not horizons:
        raise ValueError("Evaluation origin has no resolved target horizons.")
    if any(value not in FORECAST_HORIZONS for value in horizons):
        raise ValueError("Evaluation requested a non-governed horizon.")

    records: list[dict] = []

    for candidate in candidate_grid():
        posterior = fit_bvar(panel, candidate)
        model_id = "bvar::" + candidate.candidate_id
        seed = derived_seed(base_seed, origin_id, model_id)
        point_frame = point_forecast(
            panel,
            posterior,
            horizons=horizons,
        )
        point = point_frame.loc[
            :, list(VARIABLES)
        ].to_numpy(dtype=float)
        predictive = simulate_posterior_predictive(
            panel,
            posterior,
            simulations=simulations,
            seed=seed,
            horizons=horizons,
        )
        records.extend(
            _records_for_model(
                origin_id=origin_id,
                origin_quarter=origin_quarter,
                origin_as_of_date=origin_as_of_date,
                model_id=model_id,
                model_family="bvar",
                candidate_id=candidate.candidate_id,
                lags=candidate.lags,
                shrinkage=candidate.shrinkage,
                point=point,
                draws=predictive.draws,
                horizons=horizons,
                outcomes=outcomes,
                seed=seed,
                simulations=simulations,
                estimation_panel_hash=posterior.estimation_panel_hash,
            )
        )

    benchmark_seeds = {
        model_id: derived_seed(base_seed, origin_id, model_id)
        for model_id in BENCHMARK_IDS
    }
    benchmarks = simulate_all_benchmarks(
        panel,
        horizons=horizons,
        simulations=simulations,
        seeds=benchmark_seeds,
    )
    panel_hash = fit_bvar(panel, candidate_grid()[0]).estimation_panel_hash

    for benchmark in benchmarks:
        records.extend(
            _records_for_model(
                origin_id=origin_id,
                origin_quarter=origin_quarter,
                origin_as_of_date=origin_as_of_date,
                model_id=benchmark.model_id,
                model_family="benchmark",
                candidate_id=None,
                lags=4 if "ar4" in benchmark.model_id or "var4" in benchmark.model_id else None,
                shrinkage=None,
                point=benchmark.point,
                draws=benchmark.draws,
                horizons=horizons,
                outcomes=outcomes,
                seed=benchmark_seeds[benchmark.model_id],
                simulations=simulations,
                estimation_panel_hash=panel_hash,
            )
        )

    frame = pd.DataFrame.from_records(records)
    if frame.empty:
        raise ValueError("Pseudo-real-time origin evaluation produced no rows.")

    case_counts = frame.groupby(
        ["origin_id", "horizon", "variable"]
    )["model_id"].nunique()
    expected_models = len(candidate_grid()) + len(BENCHMARK_IDS)
    if not bool((case_counts == expected_models).all()):
        raise ValueError(
            "Pseudo-real-time comparison is not common-case across all models."
        )
    return frame


def aggregate_metrics(records: pd.DataFrame) -> pd.DataFrame:
    required = {
        "model_id", "model_family", "candidate_id", "lags", "shrinkage",
        "variable", "horizon", "error", "abs_error", "squared_error",
        "log_predictive_density", "crps",
        "covered_50", "covered_80", "covered_95",
        "interval_score_50", "interval_score_80", "interval_score_95",
    }
    missing = sorted(required - set(records.columns))
    if missing:
        raise ValueError(
            "Evaluation records missing columns: " + ", ".join(missing)
        )

    rows: list[dict] = []
    keys = [
        "model_id",
        "model_family",
        "candidate_id",
        "lags",
        "shrinkage",
        "variable",
        "horizon",
    ]
    for key, group in records.groupby(keys, dropna=False, sort=True):
        (
            model_id,
            family,
            candidate_id,
            lags,
            shrinkage,
            variable,
            horizon,
        ) = key
        row = {
            "model_id": model_id,
            "model_family": family,
            "candidate_id": None if pd.isna(candidate_id) else candidate_id,
            "lags": None if pd.isna(lags) else int(lags),
            "shrinkage": None if pd.isna(shrinkage) else float(shrinkage),
            "variable": variable,
            "horizon": int(horizon),
            "n": int(len(group)),
            "bias": float(group["error"].mean()),
            "mae": float(group["abs_error"].mean()),
            "rmse": float(sqrt(group["squared_error"].mean())),
            "mean_log_predictive_density": float(
                group["log_predictive_density"].mean()
            ),
            "mean_crps": float(group["crps"].mean()),
            "coverage_50": float(group["covered_50"].astype(float).mean()),
            "coverage_80": float(group["covered_80"].astype(float).mean()),
            "coverage_95": float(group["covered_95"].astype(float).mean()),
            "mean_interval_score_50": float(
                group["interval_score_50"].mean()
            ),
            "mean_interval_score_80": float(
                group["interval_score_80"].mean()
            ),
            "mean_interval_score_95": float(
                group["interval_score_95"].mean()
            ),
        }
        rows.append(row)

    result = pd.DataFrame.from_records(rows)
    if result.empty:
        raise ValueError("Metric aggregation produced no rows.")
    return result


def select_bvar_candidate(
    aggregate: pd.DataFrame,
    *,
    minimum_cell_count: int = MINIMUM_SELECTION_CELL_COUNT,
) -> pd.DataFrame:
    bvar = aggregate[
        (aggregate["model_family"] == "bvar")
        & (aggregate["horizon"].isin(PRIMARY_SELECTION_HORIZONS))
    ].copy()

    expected_candidates = {
        candidate.candidate_id
        for candidate in candidate_grid()
    }
    observed_candidates = set(
        bvar["candidate_id"].dropna().astype(str)
    )
    if observed_candidates != expected_candidates:
        raise ValueError(
            "Selection evidence must contain all six BVAR candidates."
        )

    expected_cells = {
        (variable, horizon)
        for variable in VARIABLES
        for horizon in PRIMARY_SELECTION_HORIZONS
    }

    for candidate_id in sorted(expected_candidates):
        part = bvar[bvar["candidate_id"] == candidate_id]
        cells = set(
            zip(
                part["variable"].astype(str),
                part["horizon"].astype(int),
            )
        )
        if cells != expected_cells:
            raise ValueError(
                "Candidate selection lacks a complete variable-horizon grid."
            )
        if bool((part["n"].astype(int) < minimum_cell_count).any()):
            raise ValueError(
                "Candidate selection cell has insufficient resolved cases."
            )

    counts = bvar.pivot_table(
        index=["variable", "horizon"],
        columns="candidate_id",
        values="n",
        aggfunc="first",
    )
    if bool((counts.nunique(axis=1) != 1).any()):
        raise ValueError(
            "Candidate selection must use identical common-case counts."
        )

    rows: list[dict] = []
    for candidate in candidate_grid():
        part = bvar[bvar["candidate_id"] == candidate.candidate_id]
        rows.append(
            {
                "candidate_id": candidate.candidate_id,
                "lags": candidate.lags,
                "shrinkage": candidate.shrinkage,
                "cells": int(len(part)),
                "minimum_cell_n": int(part["n"].min()),
                "mean_log_predictive_density": float(
                    part["mean_log_predictive_density"].mean()
                ),
                "mean_crps": float(part["mean_crps"].mean()),
                "mean_rmse": float(part["rmse"].mean()),
            }
        )

    table = pd.DataFrame.from_records(rows)
    table = table.sort_values(
        by=[
            "mean_log_predictive_density",
            "mean_crps",
            "mean_rmse",
            "candidate_id",
        ],
        ascending=[False, True, True, True],
        kind="mergesort",
    ).reset_index(drop=True)
    table.insert(0, "rank", np.arange(1, len(table) + 1))
    table["selected"] = table["rank"].eq(1)
    return table


def canonical_frame_hash(
    frame: pd.DataFrame,
    *,
    sort_columns: list[str],
) -> str:
    missing = sorted(set(sort_columns) - set(frame.columns))
    if missing:
        raise ValueError(
            "Hash sort columns missing: " + ", ".join(missing)
        )
    ordered = frame.sort_values(
        sort_columns,
        kind="mergesort",
        na_position="first",
    ).reset_index(drop=True)

    parts = ["|".join(str(column) for column in ordered.columns)]
    for row in ordered.itertuples(index=False, name=None):
        values = []
        for value in row:
            if value is None or pd.isna(value):
                values.append("<NA>")
            elif isinstance(value, (float, np.floating)):
                values.append(f"{float(value):.17g}")
            elif isinstance(value, (int, np.integer)):
                values.append(str(int(value)))
            elif isinstance(value, (bool, np.bool_)):
                values.append("true" if bool(value) else "false")
            elif isinstance(value, (pd.Timestamp, date)):
                values.append(pd.Timestamp(value).date().isoformat())
            else:
                values.append(str(value))
        parts.append("|".join(values))
    return sha256("\n".join(parts).encode("utf-8")).hexdigest()
