from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date
from itertools import product
from typing import TYPE_CHECKING, Any, Iterable

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from macropulse.data.repository import MacroRepository


GDP_TARGET = "GDPC1"
INFLATION_TARGETS = ("PCEPILFE", "CPILFESL", "PCEPI", "CPIAUCSL")
LABOUR_TARGETS = ("PAYEMS", "UNRATE", "CES0500000003")
ALL_TARGETS = (GDP_TARGET, *INFLATION_TARGETS, *LABOUR_TARGETS)
REGIMES = (
    "hard_landing_risk",
    "stagflation_risk",
    "overheating",
    "disinflationary_expansion",
    "balanced_expansion",
    "reflation",
    "demand_slowdown",
    "mixed_transition",
)
REGIME_FAMILY = {
    "hard_landing_risk": "contraction",
    "demand_slowdown": "contraction",
    "stagflation_risk": "adverse_supply",
    "overheating": "inflationary_expansion",
    "reflation": "inflationary_expansion",
    "balanced_expansion": "benign_expansion",
    "disinflationary_expansion": "benign_expansion",
    "mixed_transition": "mixed",
}
Z80 = 1.2815515655446004


def _piecewise_score(value: float, anchors: Iterable[Iterable[float]]) -> float:
    points = sorted(
        [(float(x), float(score)) for x, score in anchors],
        key=lambda item: item[0],
    )
    if len(points) < 2:
        raise ValueError("At least two score anchors are required.")
    x = float(value)
    if x <= points[0][0]:
        return float(points[0][1])
    if x >= points[-1][0]:
        return float(points[-1][1])
    for (x0, y0), (x1, y1) in zip(points[:-1], points[1:]):
        if x0 <= x <= x1:
            weight = (x - x0) / (x1 - x0)
            return float(y0 + weight * (y1 - y0))
    raise RuntimeError("Unable to interpolate tournament score.")


@dataclass(frozen=True)
class TournamentSplit:
    training_dates: tuple[date, ...]
    validation_dates: tuple[date, ...]
    holdout_dates: tuple[date, ...]

    def as_dict(self) -> dict[str, Any]:
        def bounds(values: tuple[date, ...]) -> dict[str, Any]:
            return {
                "start": values[0] if values else None,
                "end": values[-1] if values else None,
                "months": len(values),
            }

        return {
            "training": bounds(self.training_dates),
            "validation": bounds(self.validation_dates),
            "holdout": bounds(self.holdout_dates),
        }


def _normalise_weights(weights: dict[str, float]) -> dict[str, float]:
    total = float(sum(float(value) for value in weights.values()))
    if total <= 0:
        raise ValueError("Tournament weights must sum to a positive value.")
    return {
        str(key): float(value) / total for key, value in weights.items()
    }


def build_core_candidates(config: dict[str, Any]) -> list[dict[str, Any]]:
    tournament = config["tournament"]
    candidates: list[dict[str, Any]] = []
    for normalisation_id, inflation_id, labour_id, threshold_id in product(
        tournament["normalization_candidates"],
        tournament["inflation_weight_candidates"],
        tournament["labour_weight_candidates"],
        tournament["threshold_candidates"],
    ):
        candidate_id = "__".join(
            [normalisation_id, inflation_id, labour_id, threshold_id]
        )
        candidates.append(
            {
                "candidate_id": candidate_id,
                "normalization_id": normalisation_id,
                "inflation_weights_id": inflation_id,
                "labour_weights_id": labour_id,
                "threshold_id": threshold_id,
                "normalization": tournament["normalization_candidates"][
                    normalisation_id
                ],
                "inflation_weights": _normalise_weights(
                    tournament["inflation_weight_candidates"][inflation_id]
                ),
                "labour_weights": _normalise_weights(
                    tournament["labour_weight_candidates"][labour_id]
                ),
                "thresholds": tournament["threshold_candidates"][
                    threshold_id
                ],
            }
        )
    return candidates


def chronological_split(
    state_dates: Iterable[date],
    *,
    training_months: int,
    validation_months: int,
    minimum_holdout_months: int,
) -> TournamentSplit:
    ordered = tuple(sorted({pd.Timestamp(item).date() for item in state_dates}))
    required = training_months + validation_months + minimum_holdout_months
    if len(ordered) < required:
        raise RuntimeError(
            "Model 1D tournament requires at least "
            f"{required} complete historical states; found {len(ordered)}."
        )
    training = ordered[:training_months]
    validation = ordered[
        training_months : training_months + validation_months
    ]
    holdout = ordered[training_months + validation_months :]
    return TournamentSplit(training, validation, holdout)


def _latest_reconstruction_id(
    repository: MacroRepository,
    reconstruction_id: str | None,
) -> str:
    if reconstruction_id:
        frame = repository.query_df(
            """
            SELECT reconstruction_id
            FROM macro_state_history_runs
            WHERE reconstruction_id = ?
              AND source_mode = 'production_vintage_backtests'
            LIMIT 1
            """,
            [reconstruction_id],
        )
    else:
        frame = repository.query_df(
            """
            SELECT reconstruction_id
            FROM macro_state_history_runs
            WHERE source_mode = 'production_vintage_backtests'
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
    if frame.empty:
        raise RuntimeError(
            "No production-vintage Model 1D reconstruction is available."
        )
    return str(frame.iloc[0]["reconstruction_id"])


def _actual_rows(
    repository: MacroRepository,
    inputs: pd.DataFrame,
    source_model_id: str,
) -> pd.DataFrame:
    subset = inputs.loc[
        inputs["source_model_id"].astype(str) == source_model_id
    ].copy()
    if subset.empty:
        return subset
    source_ids = sorted(set(subset["source_run_id"].astype(str)))
    placeholders = ",".join("?" for _ in source_ids)
    if source_model_id == "US_GDP_NOWCAST_1A":
        actuals = repository.query_df(
            f"""
            SELECT
                stage_backtest_id AS source_run_id,
                'GDPC1' AS source_target,
                target_period,
                forecast_stage,
                model_name,
                actual
            FROM stage_backtest_results
            WHERE stage_backtest_id IN ({placeholders})
            """,
            source_ids,
        )
    elif source_model_id == "US_INFLATION_NOWCAST_1B":
        actuals = repository.query_df(
            f"""
            SELECT
                backtest_id AS source_run_id,
                target_series AS source_target,
                target_period,
                forecast_stage,
                model_name,
                actual
            FROM inflation_vintage_backtest_results
            WHERE backtest_id IN ({placeholders})
            """,
            source_ids,
        )
    elif source_model_id == "US_LABOUR_NOWCAST_1C":
        actuals = repository.query_df(
            f"""
            SELECT
                backtest_id AS source_run_id,
                target_series AS source_target,
                target_period,
                forecast_stage,
                model_name,
                actual
            FROM labour_vintage_backtest_results
            WHERE backtest_id IN ({placeholders})
            """,
            source_ids,
        )
    else:
        raise ValueError(f"Unsupported source model: {source_model_id}")

    join_columns = [
        "source_run_id",
        "source_target",
        "target_period",
        "forecast_stage",
        "model_name",
    ]
    actuals = actuals.drop_duplicates(subset=join_columns, keep="last")
    return subset.merge(actuals, on=join_columns, how="left")


def load_tournament_dataset(
    repository: MacroRepository,
    reconstruction_id: str | None = None,
) -> tuple[str, pd.DataFrame]:
    resolved_id = _latest_reconstruction_id(repository, reconstruction_id)
    inputs = repository.query_df(
        """
        SELECT *
        FROM macro_state_history_inputs
        WHERE reconstruction_id = ?
        ORDER BY state_date, source_model_id, source_target
        """,
        [resolved_id],
    )
    if inputs.empty:
        raise RuntimeError(
            f"Reconstruction {resolved_id} has no historical input rows."
        )

    frames = [
        _actual_rows(repository, inputs, "US_GDP_NOWCAST_1A"),
        _actual_rows(repository, inputs, "US_INFLATION_NOWCAST_1B"),
        _actual_rows(repository, inputs, "US_LABOUR_NOWCAST_1C"),
    ]
    dataset = pd.concat(frames, ignore_index=True)
    numeric_columns = ["point_forecast", "lower_80", "upper_80", "actual"]
    for column in numeric_columns:
        dataset[column] = pd.to_numeric(dataset[column], errors="coerce")
    dataset["state_date"] = pd.to_datetime(dataset["state_date"]).dt.date

    counts = dataset.groupby("state_date")["source_target"].nunique()
    complete_dates = set(counts.loc[counts == len(ALL_TARGETS)].index)
    dataset = dataset.loc[dataset["state_date"].isin(complete_dates)].copy()
    complete_actual_dates = set(
        dataset.groupby("state_date")["actual"]
        .apply(lambda values: bool(values.notna().all()))
        .loc[lambda values: values]
        .index
    )
    dataset = dataset.loc[
        dataset["state_date"].isin(complete_actual_dates)
    ].copy()
    if dataset.empty:
        raise RuntimeError(
            "No complete historical states have all eight realised outcomes."
        )

    def period_ordinal(row: pd.Series) -> int:
        frequency = "Q" if row["source_target"] == GDP_TARGET else "M"
        return int(pd.Period(str(row["target_period"]), freq=frequency).ordinal)

    dataset["target_period_ordinal"] = dataset.apply(
        period_ordinal, axis=1
    )
    dataset = dataset.sort_values(
        ["state_date", "source_target"]
    ).reset_index(drop=True)
    return resolved_id, dataset


def _piecewise_target_score(
    value: float,
    target: str,
    config: dict[str, Any],
) -> float:
    if target == GDP_TARGET:
        anchors = config["score_anchors"]["growth"]
    elif target in INFLATION_TARGETS:
        anchors = config["score_anchors"]["inflation"][target]
    elif target in LABOUR_TARGETS:
        anchors = config["score_anchors"]["labour"][target]
    else:
        raise KeyError(target)
    return float(_piecewise_score(float(value), anchors))


def _target_centered_score(
    value: float,
    target: str,
    target_centered: dict[str, Any],
) -> float:
    center = float(target_centered["centers"][target])
    scale = float(target_centered["scales"][target])
    orientation = float(target_centered["orientation"][target])
    if scale <= 0:
        raise ValueError(f"Target scale must be positive for {target}.")
    return float(np.clip(orientation * (float(value) - center) / scale, -2, 2))


def _prior_actual_values(
    actual_history: pd.DataFrame,
    target: str,
    target_period_ordinal: int,
) -> np.ndarray:
    frame = actual_history.loc[
        (actual_history["source_target"].astype(str) == target)
        & (actual_history["target_period_ordinal"] < target_period_ordinal)
    ].drop_duplicates(subset=["target_period_ordinal"], keep="last")
    return pd.to_numeric(frame["actual"], errors="coerce").dropna().to_numpy()


def target_score(
    value: float,
    *,
    target: str,
    target_period_ordinal: int,
    normalization_id: str,
    config: dict[str, Any],
    actual_history: pd.DataFrame,
) -> float:
    tournament = config["tournament"]
    normalizer = tournament["normalization_candidates"][normalization_id]
    method = str(normalizer["method"])
    if method == "policy_anchors":
        return _piecewise_target_score(value, target, config)
    target_centered = tournament["normalization_candidates"][
        "target_centered"
    ]
    if method == "target_centered":
        return _target_centered_score(value, target, target_centered)
    if method != "expanding_robust_z":
        raise ValueError(f"Unknown normalization method: {method}")

    history = _prior_actual_values(
        actual_history, target, target_period_ordinal
    )
    minimum = int(normalizer["minimum_history"])
    if len(history) < minimum:
        return _target_centered_score(value, target, target_centered)
    median = float(np.median(history))
    mad = float(np.median(np.abs(history - median)))
    robust_scale = 1.4826 * mad
    if robust_scale <= 1e-9:
        robust_scale = float(np.std(history, ddof=1)) if len(history) > 1 else 0.0
    if robust_scale <= 1e-9:
        return _target_centered_score(value, target, target_centered)
    orientation = float(target_centered["orientation"][target])
    clip = float(normalizer.get("clip", 2.0))
    score = orientation * (float(value) - median) / robust_scale
    return float(np.clip(score, -clip, clip))


def classify_regime_with_thresholds(
    growth: float,
    inflation: float,
    labour: float,
    thresholds: dict[str, Any],
) -> str:
    g = float(growth)
    i = float(inflation)
    l = float(labour)
    if (
        g <= float(thresholds["hard_growth_max"])
        and l <= float(thresholds["hard_labour_max"])
    ):
        return "hard_landing_risk"
    if (
        g <= float(thresholds["stag_growth_max"])
        and i >= float(thresholds["stag_inflation_min"])
    ):
        return "stagflation_risk"
    if (
        g >= float(thresholds["overheat_growth_min"])
        and i >= float(thresholds["overheat_inflation_min"])
        and l >= float(thresholds["overheat_labour_min"])
    ):
        return "overheating"
    if (
        g >= float(thresholds["disinflation_growth_min"])
        and i <= float(thresholds["disinflation_inflation_max"])
        and l >= float(thresholds["disinflation_labour_min"])
    ):
        return "disinflationary_expansion"
    if (
        float(thresholds["balanced_growth_min"])
        <= g
        <= float(thresholds["balanced_growth_max"])
        and float(thresholds["balanced_inflation_min"])
        <= i
        <= float(thresholds["balanced_inflation_max"])
        and float(thresholds["balanced_labour_min"])
        <= l
        <= float(thresholds["balanced_labour_max"])
    ):
        return "balanced_expansion"
    if (
        g >= float(thresholds["reflation_growth_min"])
        and i >= float(thresholds["reflation_inflation_min"])
    ):
        return "reflation"
    if (
        g <= float(thresholds["slowdown_growth_max"])
        and i <= float(thresholds["slowdown_inflation_max"])
    ):
        return "demand_slowdown"
    return "mixed_transition"


def _classify_samples(
    samples: np.ndarray,
    thresholds: dict[str, Any],
) -> np.ndarray:
    g, i, l = samples[:, 0], samples[:, 1], samples[:, 2]
    result = np.full(len(samples), "mixed_transition", dtype=object)
    unassigned = np.ones(len(samples), dtype=bool)

    def assign(mask: np.ndarray, label: str) -> None:
        nonlocal unassigned
        selected = unassigned & mask
        result[selected] = label
        unassigned[selected] = False

    assign(
        (g <= float(thresholds["hard_growth_max"]))
        & (l <= float(thresholds["hard_labour_max"])),
        "hard_landing_risk",
    )
    assign(
        (g <= float(thresholds["stag_growth_max"]))
        & (i >= float(thresholds["stag_inflation_min"])),
        "stagflation_risk",
    )
    assign(
        (g >= float(thresholds["overheat_growth_min"]))
        & (i >= float(thresholds["overheat_inflation_min"]))
        & (l >= float(thresholds["overheat_labour_min"])),
        "overheating",
    )
    assign(
        (g >= float(thresholds["disinflation_growth_min"]))
        & (i <= float(thresholds["disinflation_inflation_max"]))
        & (l >= float(thresholds["disinflation_labour_min"])),
        "disinflationary_expansion",
    )
    assign(
        (g >= float(thresholds["balanced_growth_min"]))
        & (g <= float(thresholds["balanced_growth_max"]))
        & (i >= float(thresholds["balanced_inflation_min"]))
        & (i <= float(thresholds["balanced_inflation_max"]))
        & (l >= float(thresholds["balanced_labour_min"]))
        & (l <= float(thresholds["balanced_labour_max"])),
        "balanced_expansion",
    )
    assign(
        (g >= float(thresholds["reflation_growth_min"]))
        & (i >= float(thresholds["reflation_inflation_min"])),
        "reflation",
    )
    assign(
        (g <= float(thresholds["slowdown_growth_max"]))
        & (i <= float(thresholds["slowdown_inflation_max"])),
        "demand_slowdown",
    )
    return result.astype(str)


def _weighted_average(values: dict[str, float], weights: dict[str, float]) -> float:
    return float(sum(values[key] * weights[key] for key in weights))


def candidate_monthly_states(
    dataset: pd.DataFrame,
    candidate: dict[str, Any],
    config: dict[str, Any],
) -> pd.DataFrame:
    actual_history = dataset[
        ["source_target", "target_period_ordinal", "actual"]
    ].copy()
    records: list[dict[str, Any]] = []
    for state_date, frame in dataset.groupby("state_date", sort=True):
        target_rows = {
            str(row.source_target): row
            for row in frame.itertuples(index=False)
        }
        if set(target_rows) != set(ALL_TARGETS):
            continue
        point_scores: dict[str, float] = {}
        actual_scores: dict[str, float] = {}
        lower_scores: dict[str, float] = {}
        upper_scores: dict[str, float] = {}
        for target, row in target_rows.items():
            kwargs = {
                "target": target,
                "target_period_ordinal": int(row.target_period_ordinal),
                "normalization_id": candidate["normalization_id"],
                "config": config,
                "actual_history": actual_history,
            }
            point_scores[target] = target_score(float(row.point_forecast), **kwargs)
            actual_scores[target] = target_score(float(row.actual), **kwargs)
            interval = sorted(
                [
                    target_score(float(row.lower_80), **kwargs),
                    target_score(float(row.upper_80), **kwargs),
                ]
            )
            lower_scores[target], upper_scores[target] = interval

        forecast_growth = point_scores[GDP_TARGET]
        actual_growth = actual_scores[GDP_TARGET]
        lower_growth = lower_scores[GDP_TARGET]
        upper_growth = upper_scores[GDP_TARGET]

        inflation_weights = candidate["inflation_weights"]
        labour_weights = candidate["labour_weights"]
        forecast_inflation = _weighted_average(point_scores, inflation_weights)
        actual_inflation = _weighted_average(actual_scores, inflation_weights)
        lower_inflation = _weighted_average(lower_scores, inflation_weights)
        upper_inflation = _weighted_average(upper_scores, inflation_weights)
        forecast_labour = _weighted_average(point_scores, labour_weights)
        actual_labour = _weighted_average(actual_scores, labour_weights)
        lower_labour = _weighted_average(lower_scores, labour_weights)
        upper_labour = _weighted_average(upper_scores, labour_weights)

        thresholds = candidate["thresholds"]
        forecast_regime = classify_regime_with_thresholds(
            forecast_growth, forecast_inflation, forecast_labour, thresholds
        )
        actual_regime = classify_regime_with_thresholds(
            actual_growth, actual_inflation, actual_labour, thresholds
        )
        records.append(
            {
                "candidate_id": candidate["candidate_id"],
                "state_date": pd.Timestamp(state_date).date(),
                "forecast_growth": forecast_growth,
                "forecast_inflation": forecast_inflation,
                "forecast_labour": forecast_labour,
                "actual_growth": actual_growth,
                "actual_inflation": actual_inflation,
                "actual_labour": actual_labour,
                "growth_lower": lower_growth,
                "growth_upper": upper_growth,
                "inflation_lower": min(lower_inflation, upper_inflation),
                "inflation_upper": max(lower_inflation, upper_inflation),
                "labour_lower": min(lower_labour, upper_labour),
                "labour_upper": max(lower_labour, upper_labour),
                "forecast_regime": forecast_regime,
                "actual_regime": actual_regime,
                "forecast_family": REGIME_FAMILY[forecast_regime],
                "actual_family": REGIME_FAMILY[actual_regime],
                "growth_error": forecast_growth - actual_growth,
                "inflation_error": forecast_inflation - actual_inflation,
                "labour_error": forecast_labour - actual_labour,
            }
        )
    return pd.DataFrame(records).sort_values("state_date").reset_index(drop=True)


def _sign_bucket(values: np.ndarray, deadzone: float) -> np.ndarray:
    return np.where(values > deadzone, 1, np.where(values < -deadzone, -1, 0))


def _contiguous_pairs(frame: pd.DataFrame) -> pd.DataFrame:
    ordered = frame.sort_values("state_date").copy()
    ordered["_ordinal"] = pd.PeriodIndex(ordered["state_date"], freq="M").asi8
    ordered["_previous_ordinal"] = ordered["_ordinal"].shift(1)
    return ordered.loc[
        ordered["_previous_ordinal"].notna()
        & ((ordered["_ordinal"] - ordered["_previous_ordinal"]) == 1)
    ].copy()


def _jensen_shannon_divergence(
    observed: pd.Series,
    expected: pd.Series,
) -> float:
    p = np.asarray([float(observed.get(item, 0.0)) for item in REGIMES])
    q = np.asarray([float(expected.get(item, 0.0)) for item in REGIMES])
    if p.sum() == 0 or q.sum() == 0:
        return 1.0
    p = p / p.sum()
    q = q / q.sum()
    m = 0.5 * (p + q)

    def kl(a: np.ndarray, b: np.ndarray) -> float:
        mask = a > 0
        return float(np.sum(a[mask] * np.log(a[mask] / b[mask])))

    return float(0.5 * kl(p, m) + 0.5 * kl(q, m))


def _normalized_regime_entropy(values: pd.Series) -> float:
    frequencies = values.value_counts(normalize=True)
    entropy = -sum(
        float(probability) * math.log(float(probability))
        for probability in frequencies
        if probability > 0
    )
    return float(entropy / math.log(len(REGIMES)))


def core_metrics(
    monthly: pd.DataFrame,
    dates: Iterable[date],
    *,
    deadzone: float,
) -> dict[str, Any]:
    date_set = {pd.Timestamp(item).date() for item in dates}
    frame = monthly.loc[monthly["state_date"].isin(date_set)].copy()
    if frame.empty:
        raise RuntimeError("Tournament split contains no candidate states.")
    forecast_dimensions = frame[
        ["forecast_growth", "forecast_inflation", "forecast_labour"]
    ].to_numpy(dtype=float)
    actual_dimensions = frame[
        ["actual_growth", "actual_inflation", "actual_labour"]
    ].to_numpy(dtype=float)
    errors = forecast_dimensions - actual_dimensions
    exact_accuracy = float(
        (frame["forecast_regime"] == frame["actual_regime"]).mean()
    )
    family_accuracy = float(
        (frame["forecast_family"] == frame["actual_family"]).mean()
    )
    sign_accuracy = float(
        (
            _sign_bucket(forecast_dimensions, deadzone)
            == _sign_bucket(actual_dimensions, deadzone)
        ).mean()
    )

    ordered = frame.sort_values("state_date").copy()
    ordered["previous_forecast_regime"] = ordered["forecast_regime"].shift(1)
    ordered["previous_actual_regime"] = ordered["actual_regime"].shift(1)
    pairs = _contiguous_pairs(ordered)
    if pairs.empty:
        forecast_churn = 0.0
        actual_churn = 0.0
    else:
        forecast_churn = float(
            (
                pairs["forecast_regime"]
                != pairs["previous_forecast_regime"]
            ).mean()
        )
        actual_churn = float(
            (pairs["actual_regime"] != pairs["previous_actual_regime"]).mean()
        )
    forecast_distribution = frame["forecast_regime"].value_counts(normalize=True)
    actual_distribution = frame["actual_regime"].value_counts(normalize=True)
    return {
        "months": int(len(frame)),
        "dimension_rmse": float(np.sqrt(np.mean(np.square(errors)))),
        "dimension_mae": float(np.mean(np.abs(errors))),
        "exact_regime_accuracy": exact_accuracy,
        "family_accuracy": family_accuracy,
        "sign_accuracy": sign_accuracy,
        "forecast_churn": forecast_churn,
        "actual_churn": actual_churn,
        "churn_gap": abs(forecast_churn - actual_churn),
        "distribution_jsd": _jensen_shannon_divergence(
            forecast_distribution, actual_distribution
        ),
        "forecast_regime_entropy": _normalized_regime_entropy(
            frame["forecast_regime"]
        ),
        "actual_regime_entropy": _normalized_regime_entropy(
            frame["actual_regime"]
        ),
        "regime_collapse_penalty": (
            max(
                0.0,
                0.50 - _normalized_regime_entropy(frame["forecast_regime"]),
            )
            + max(
                0.0,
                0.50 - _normalized_regime_entropy(frame["actual_regime"]),
            )
        ),
        "forecast_regime_count": int(frame["forecast_regime"].nunique()),
        "actual_regime_count": int(frame["actual_regime"].nunique()),
    }


def _rank_component(series: pd.Series, higher_is_better: bool) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    if values.isna().any():
        raise ValueError("Tournament ranking metrics cannot contain missing values.")
    ranked = values.rank(method="average", pct=True)
    return ranked if higher_is_better else (-values).rank(method="average", pct=True)


def rank_core_metrics(
    validation: pd.DataFrame,
    weights: dict[str, float],
) -> pd.DataFrame:
    frame = validation.copy()
    directions = {
        "dimension_rmse": False,
        "exact_regime_accuracy": True,
        "family_accuracy": True,
        "sign_accuracy": True,
        "churn_gap": False,
        "distribution_jsd": False,
        "regime_collapse_penalty": False,
    }
    score = pd.Series(0.0, index=frame.index)
    for metric, weight in weights.items():
        component = _rank_component(frame[metric], directions[metric])
        frame[f"rank_component_{metric}"] = component
        score = score + float(weight) * component
    frame["core_score"] = 100.0 * score
    frame["core_rank"] = frame["core_score"].rank(
        method="min", ascending=False
    ).astype(int)
    return frame.sort_values(
        ["core_rank", "candidate_id"]
    ).reset_index(drop=True)


def baseline_accuracies(
    monthly_reference: pd.DataFrame,
    split: TournamentSplit,
) -> dict[str, float]:
    ordered = monthly_reference.sort_values("state_date").copy()
    training = ordered.loc[
        ordered["state_date"].isin(set(split.training_dates))
    ]
    mode_regime = str(training["actual_regime"].mode().iloc[0])

    def metrics(dates: tuple[date, ...]) -> tuple[float, float]:
        frame = ordered.loc[ordered["state_date"].isin(set(dates))].copy()
        mode_accuracy = float((frame["actual_regime"] == mode_regime).mean())
        all_ordered = ordered.copy()
        all_ordered["previous_actual_regime"] = all_ordered[
            "actual_regime"
        ].shift(1)
        pairs = _contiguous_pairs(all_ordered)
        pairs = pairs.loc[pairs["state_date"].isin(set(dates))]
        persistence = (
            float(
                (
                    pairs["actual_regime"]
                    == pairs["previous_actual_regime"]
                ).mean()
            )
            if not pairs.empty
            else float("nan")
        )
        return mode_accuracy, persistence

    validation_mode, validation_persistence = metrics(split.validation_dates)
    holdout_mode, holdout_persistence = metrics(split.holdout_dates)
    return {
        "training_mode_regime": mode_regime,
        "validation_mode_accuracy": validation_mode,
        "validation_persistence_accuracy": validation_persistence,
        "holdout_mode_accuracy": holdout_mode,
        "holdout_persistence_accuracy": holdout_persistence,
    }


def run_core_tournament(
    dataset: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[
    TournamentSplit,
    list[dict[str, Any]],
    dict[str, pd.DataFrame],
    pd.DataFrame,
    pd.DataFrame,
    dict[str, float],
]:
    tournament = config["tournament"]
    split = chronological_split(
        dataset["state_date"].unique(),
        training_months=int(tournament["training_months"]),
        validation_months=int(tournament["validation_months"]),
        minimum_holdout_months=int(tournament["minimum_holdout_months"]),
    )
    candidates = build_core_candidates(config)
    monthly_by_candidate: dict[str, pd.DataFrame] = {}
    metric_rows: list[dict[str, Any]] = []
    for candidate in candidates:
        monthly = candidate_monthly_states(dataset, candidate, config)
        monthly_by_candidate[candidate["candidate_id"]] = monthly
        for split_name, dates in (
            ("validation", split.validation_dates),
            ("holdout", split.holdout_dates),
        ):
            metric_rows.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "split": split_name,
                    **core_metrics(
                        monthly,
                        dates,
                        deadzone=float(tournament["score_deadzone"]),
                    ),
                }
            )
    metrics = pd.DataFrame(metric_rows)
    validation = rank_core_metrics(
        metrics.loc[metrics["split"] == "validation"].copy(),
        tournament["core_metric_weights"],
    )
    holdout = rank_core_metrics(
        metrics.loc[metrics["split"] == "holdout"].copy(),
        tournament["core_metric_weights"],
    ).rename(
        columns={
            "core_score": "holdout_core_score",
            "core_rank": "holdout_core_rank",
        }
    )
    leaderboard = validation.merge(
        holdout[
            [
                "candidate_id",
                "holdout_core_score",
                "holdout_core_rank",
                "exact_regime_accuracy",
                "family_accuracy",
                "sign_accuracy",
                "dimension_rmse",
            ]
        ].rename(
            columns={
                "exact_regime_accuracy": "holdout_exact_regime_accuracy",
                "family_accuracy": "holdout_family_accuracy",
                "sign_accuracy": "holdout_sign_accuracy",
                "dimension_rmse": "holdout_dimension_rmse",
            }
        ),
        on="candidate_id",
        how="left",
    )
    reference_id = "policy_anchors__policy__policy__baseline"
    reference = monthly_by_candidate.get(reference_id)
    if reference is None:
        reference = monthly_by_candidate[candidates[0]["candidate_id"]]
    baselines = baseline_accuracies(reference, split)
    return (
        split,
        candidates,
        monthly_by_candidate,
        metrics,
        leaderboard,
        baselines,
    )


def _stable_seed(*parts: Any, base_seed: int) -> int:
    payload = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) + int(base_seed)


def _nearest_correlation(matrix: np.ndarray) -> np.ndarray:
    symmetric = 0.5 * (matrix + matrix.T)
    values, vectors = np.linalg.eigh(symmetric)
    values = np.clip(values, 1e-6, None)
    positive = vectors @ np.diag(values) @ vectors.T
    scales = np.sqrt(np.diag(positive))
    correlation = positive / np.outer(scales, scales)
    np.fill_diagonal(correlation, 1.0)
    return correlation


def uncertainty_correlation(
    monthly: pd.DataFrame,
    state_date: date,
    uncertainty_id: str,
    config: dict[str, Any],
) -> np.ndarray:
    candidate = config["tournament"]["uncertainty_candidates"][uncertainty_id]
    method = str(candidate["method"])
    if method == "independent_normal":
        return np.eye(3)
    fixed = np.asarray(
        config["tournament"]["uncertainty_candidates"]
        ["fixed_gaussian_copula"]["correlation"],
        dtype=float,
    )
    if method == "fixed_gaussian_copula":
        return _nearest_correlation(fixed)
    if method != "expanding_residual_copula":
        raise ValueError(f"Unknown uncertainty method: {method}")
    prior = monthly.loc[monthly["state_date"] < state_date]
    minimum = int(candidate["minimum_history"])
    if len(prior) < minimum:
        return _nearest_correlation(fixed)
    errors = prior[
        ["growth_error", "inflation_error", "labour_error"]
    ].to_numpy(dtype=float)
    empirical = np.corrcoef(errors, rowvar=False)
    if not np.isfinite(empirical).all():
        return _nearest_correlation(fixed)
    shrinkage = float(candidate["shrinkage"])
    shrunk = (1.0 - shrinkage) * empirical + shrinkage * np.eye(3)
    return _nearest_correlation(shrunk)


def regime_probability_distribution(
    row: pd.Series,
    *,
    monthly: pd.DataFrame,
    core_candidate: dict[str, Any],
    uncertainty_id: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    means = np.asarray(
        [
            row["forecast_growth"],
            row["forecast_inflation"],
            row["forecast_labour"],
        ],
        dtype=float,
    )
    widths = np.asarray(
        [
            max(0.0, row["growth_upper"] - row["growth_lower"]),
            max(0.0, row["inflation_upper"] - row["inflation_lower"]),
            max(0.0, row["labour_upper"] - row["labour_lower"]),
        ],
        dtype=float,
    )
    sigmas = np.maximum(widths / (2.0 * Z80), 1e-6)
    correlation = uncertainty_correlation(
        monthly,
        pd.Timestamp(row["state_date"]).date(),
        uncertainty_id,
        config,
    )
    covariance = np.diag(sigmas) @ correlation @ np.diag(sigmas)
    seed = _stable_seed(
        core_candidate["candidate_id"],
        uncertainty_id,
        row["state_date"],
        base_seed=int(config["tournament"]["random_seed"]),
    )
    rng = np.random.default_rng(seed)
    draws = int(config["tournament"]["uncertainty_draws"])
    samples = rng.multivariate_normal(means, covariance, size=draws)
    samples = np.clip(samples, -2.0, 2.0)
    classified = _classify_samples(samples, core_candidate["thresholds"])
    counts = pd.Series(classified).value_counts()
    probabilities = {
        regime: float(counts.get(regime, 0) / draws) for regime in REGIMES
    }
    ranked = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)
    top_regime, top_probability = ranked[0]
    actual_regime = str(row["actual_regime"])
    actual_probability = max(probabilities.get(actual_regime, 0.0), 1e-12)
    cumulative = 0.0
    coverage_set: set[str] = set()
    for regime, probability in ranked:
        coverage_set.add(regime)
        cumulative += probability
        if cumulative >= 0.80:
            break
    entropy = -sum(
        probability * math.log(probability)
        for probability in probabilities.values()
        if probability > 0
    )
    one_hot = np.asarray(
        [1.0 if regime == actual_regime else 0.0 for regime in REGIMES]
    )
    probability_vector = np.asarray([probabilities[regime] for regime in REGIMES])
    return {
        "top_regime": top_regime,
        "top_probability": float(top_probability),
        "actual_regime_probability": float(actual_probability),
        "brier_score": float(np.sum(np.square(probability_vector - one_hot))),
        "log_loss": float(-math.log(actual_probability)),
        "coverage_80": bool(actual_regime in coverage_set),
        "entropy": float(entropy),
        "effective_regimes": float(math.exp(entropy)),
        "probabilities_json": json.dumps(probabilities, sort_keys=True),
    }


def uncertainty_monthly(
    monthly: pd.DataFrame,
    core_candidate: dict[str, Any],
    uncertainty_id: str,
    config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    final_candidate_id = (
        f"{core_candidate['candidate_id']}__{uncertainty_id}"
    )
    for _, row in monthly.iterrows():
        distribution = regime_probability_distribution(
            row,
            monthly=monthly,
            core_candidate=core_candidate,
            uncertainty_id=uncertainty_id,
            config=config,
        )
        rows.append(
            {
                **row.to_dict(),
                "candidate_id": final_candidate_id,
                "core_candidate_id": core_candidate["candidate_id"],
                "uncertainty_id": uncertainty_id,
                **distribution,
            }
        )
    return pd.DataFrame(rows)


def uncertainty_metrics(
    monthly: pd.DataFrame,
    dates: Iterable[date],
) -> dict[str, Any]:
    date_set = {pd.Timestamp(item).date() for item in dates}
    frame = monthly.loc[monthly["state_date"].isin(date_set)].copy()
    if frame.empty:
        raise RuntimeError("Uncertainty split contains no monthly rows.")
    return {
        "months": int(len(frame)),
        "brier_score": float(frame["brier_score"].mean()),
        "log_loss": float(frame["log_loss"].mean()),
        "coverage_80": float(frame["coverage_80"].mean()),
        "coverage_gap": abs(float(frame["coverage_80"].mean()) - 0.80),
        "mean_top_probability": float(frame["top_probability"].mean()),
        "mean_effective_regimes": float(frame["effective_regimes"].mean()),
        "top1_accuracy": float(
            (frame["top_regime"] == frame["actual_regime"]).mean()
        ),
    }


def rank_uncertainty_metrics(
    metrics: pd.DataFrame,
    weights: dict[str, float],
) -> pd.DataFrame:
    frame = metrics.copy()
    directions = {
        "brier_score": False,
        "log_loss": False,
        "coverage_gap": False,
        "mean_effective_regimes": False,
        "top1_accuracy": True,
    }
    score = pd.Series(0.0, index=frame.index)
    for metric, weight in weights.items():
        component = _rank_component(frame[metric], directions[metric])
        frame[f"rank_component_{metric}"] = component
        score = score + float(weight) * component
    frame["uncertainty_score"] = 100.0 * score
    frame["uncertainty_rank"] = frame["uncertainty_score"].rank(
        method="min", ascending=False
    ).astype(int)
    return frame


def run_uncertainty_tournament(
    *,
    core_candidates: list[dict[str, Any]],
    monthly_by_candidate: dict[str, pd.DataFrame],
    core_leaderboard: pd.DataFrame,
    split: TournamentSplit,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    tournament = config["tournament"]
    top_n = int(tournament["top_core_candidates"])
    selected_core_ids = core_leaderboard.nsmallest(top_n, "core_rank")[
        "candidate_id"
    ].tolist()
    candidate_map = {item["candidate_id"]: item for item in core_candidates}
    monthly_final: dict[str, pd.DataFrame] = {}
    metric_rows: list[dict[str, Any]] = []
    for core_id in selected_core_ids:
        core = candidate_map[core_id]
        monthly = monthly_by_candidate[core_id]
        for uncertainty_id in tournament["uncertainty_candidates"]:
            final = uncertainty_monthly(
                monthly, core, uncertainty_id, config
            )
            final_id = str(final.iloc[0]["candidate_id"])
            monthly_final[final_id] = final
            for split_name, dates in (
                ("validation", split.validation_dates),
                ("holdout", split.holdout_dates),
            ):
                metric_rows.append(
                    {
                        "candidate_id": final_id,
                        "core_candidate_id": core_id,
                        "uncertainty_id": uncertainty_id,
                        "split": split_name,
                        **uncertainty_metrics(final, dates),
                    }
                )
    metrics = pd.DataFrame(metric_rows)
    validation = rank_uncertainty_metrics(
        metrics.loc[metrics["split"] == "validation"].copy(),
        tournament["uncertainty_metric_weights"],
    )
    holdout = rank_uncertainty_metrics(
        metrics.loc[metrics["split"] == "holdout"].copy(),
        tournament["uncertainty_metric_weights"],
    ).rename(
        columns={
            "uncertainty_score": "holdout_uncertainty_score",
            "uncertainty_rank": "holdout_uncertainty_rank",
        }
    )
    validation = validation.merge(
        core_leaderboard[
            ["candidate_id", "core_score", "core_rank", "holdout_core_score", "holdout_core_rank"]
        ].rename(columns={"candidate_id": "core_candidate_id"}),
        on="core_candidate_id",
        how="left",
    )
    final_weights = tournament["final_score_weights"]
    validation["final_score"] = (
        float(final_weights["core"]) * validation["core_score"]
        + float(final_weights["uncertainty"])
        * validation["uncertainty_score"]
    )
    validation["final_rank"] = validation["final_score"].rank(
        method="min", ascending=False
    ).astype(int)

    holdout = holdout.merge(
        core_leaderboard[
            ["candidate_id", "holdout_core_score", "holdout_core_rank"]
        ].rename(columns={"candidate_id": "core_candidate_id"}),
        on="core_candidate_id",
        how="left",
    )
    holdout["holdout_final_score"] = (
        float(final_weights["core"]) * holdout["holdout_core_score"]
        + float(final_weights["uncertainty"])
        * holdout["holdout_uncertainty_score"]
    )
    holdout["holdout_final_rank"] = holdout["holdout_final_score"].rank(
        method="min", ascending=False
    ).astype(int)
    leaderboard = validation.merge(
        holdout[
            [
                "candidate_id",
                "holdout_uncertainty_score",
                "holdout_uncertainty_rank",
                "holdout_final_score",
                "holdout_final_rank",
                "brier_score",
                "log_loss",
                "coverage_80",
                "top1_accuracy",
            ]
        ].rename(
            columns={
                "brier_score": "holdout_brier_score",
                "log_loss": "holdout_log_loss",
                "coverage_80": "holdout_coverage_80",
                "top1_accuracy": "holdout_top1_accuracy",
            }
        ),
        on="candidate_id",
        how="left",
    )
    return (
        leaderboard.sort_values(
            ["final_rank", "candidate_id"]
        ).reset_index(drop=True),
        metrics,
        monthly_final,
    )


def split_name_for_date(state_date: date, split: TournamentSplit) -> str:
    item = pd.Timestamp(state_date).date()
    if item in set(split.training_dates):
        return "training"
    if item in set(split.validation_dates):
        return "validation"
    if item in set(split.holdout_dates):
        return "holdout"
    return "outside"
