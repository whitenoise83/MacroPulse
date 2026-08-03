from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import product
from typing import Any, Iterable

import numpy as np
import pandas as pd

from macropulse.config import get_series_definitions
from macropulse.inflation.config import target_definitions as inflation_target_definitions
from macropulse.labour.config import target_definitions as labour_target_definitions
from macropulse.macro_state.rolling_tournament import (
    RollingTournamentPlan,
    block_bootstrap_margin_ci,
)
from macropulse.macro_state.tournament import (
    ALL_TARGETS,
    GDP_TARGET,
    REGIMES,
    REGIME_FAMILY,
    build_core_candidates,
    candidate_monthly_states,
    classify_regime_with_thresholds,
)
from macropulse.processing.transforms import transform_series

FAMILIES = tuple(sorted(set(REGIME_FAMILY.values())))
TARGET_MODES = ("initial_release", "fixed_horizon_90d", "latest_revised")
BENCHMARKS = ("source", "persistence")


@dataclass(frozen=True)
class RealTimeSoftTargetPlan:
    target_modes: tuple[str, ...]
    fixed_horizon_days: int
    maximum_snapshot_gap_days: int
    perturbation_epsilon: float
    threshold_ids: tuple[str, ...]
    minimum_primary_probability: float
    minimum_probability_margin: float
    alternative_probability_floor: float
    prospective_shadow_start: date


def soft_target_plan(config: dict[str, Any]) -> RealTimeSoftTargetPlan:
    section = config["real_time_soft_targets"]
    modes = tuple(str(item) for item in section["target_modes"])
    unknown = set(modes) - set(TARGET_MODES)
    if unknown:
        raise ValueError(f"Unknown real-time target modes: {sorted(unknown)}")
    threshold_ids = tuple(str(item) for item in section["threshold_ids"])
    unknown_thresholds = set(threshold_ids) - set(
        config["tournament"]["threshold_candidates"]
    )
    if unknown_thresholds:
        raise ValueError(
            f"Unknown soft-target thresholds: {sorted(unknown_thresholds)}"
        )
    return RealTimeSoftTargetPlan(
        target_modes=modes,
        fixed_horizon_days=int(section["fixed_horizon_days"]),
        maximum_snapshot_gap_days=int(section["maximum_snapshot_gap_days"]),
        perturbation_epsilon=float(section["perturbation_epsilon"]),
        threshold_ids=threshold_ids,
        minimum_primary_probability=float(
            section["ambiguity"]["minimum_primary_probability"]
        ),
        minimum_probability_margin=float(
            section["ambiguity"]["minimum_probability_margin"]
        ),
        alternative_probability_floor=float(
            section["ambiguity"]["alternative_probability_floor"]
        ),
        prospective_shadow_start=pd.Timestamp(
            section["prospective_shadow_start"]
        ).date(),
    )


def _definition_map() -> dict[str, Any]:
    definitions = list(get_series_definitions())
    definitions.extend(inflation_target_definitions())
    definitions.extend(labour_target_definitions())
    return {str(item.series_id): item for item in definitions}


def _target_period(target: str, value: Any) -> pd.Period:
    return pd.Period(str(value), freq="Q" if target == GDP_TARGET else "M")


def _target_actual_from_frame(
    frame: pd.DataFrame,
    *,
    target: str,
    target_period: Any,
    definitions: dict[str, Any] | None = None,
) -> float:
    definitions = definitions or _definition_map()
    if target not in definitions:
        raise KeyError(f"No target definition is available for {target}.")
    subset = frame.loc[frame["series_id"].astype(str) == target].copy()
    if subset.empty:
        raise ValueError(f"No observations are available for {target}.")
    values = (
        subset.assign(observation_date=pd.to_datetime(subset["observation_date"]))
        .sort_values("observation_date")
        .drop_duplicates(subset=["observation_date"], keep="last")
        .set_index("observation_date")["value"]
    )
    transformed = transform_series(values.astype(float), definitions[target].transform)
    frequency = "Q" if target == GDP_TARGET else "M"
    transformed.index = transformed.index.to_period(frequency)
    grouped = transformed.groupby(level=0).last()
    period = _target_period(target, target_period)
    if period not in grouped.index or pd.isna(grouped.loc[period]):
        raise ValueError(f"No transformed actual is available for {target} {period}.")
    return float(grouped.loc[period])


def _latest_snapshot_date(
    repository: Any,
    *,
    target: str,
    release_date: date | None,
    evaluation_date: date,
) -> date | None:
    lower = release_date or date(1900, 1, 1)
    frame = repository.query_df(
        """
        SELECT MAX(as_of_date) AS as_of_date
        FROM historical_snapshots
        WHERE series_id = ?
          AND as_of_date >= ?
          AND as_of_date <= ?
        """,
        [target, lower, evaluation_date],
    )
    if frame.empty or pd.isna(frame.iloc[0]["as_of_date"]):
        return None
    return pd.Timestamp(frame.iloc[0]["as_of_date"]).date()


def reconstruct_actual_vintages(
    repository: Any,
    dataset: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    """Reconstruct initial-release, fixed-horizon, and latest actual values.

    Initial-release values are the actuals stored by the approved source vintage
    backtests. Fixed-horizon values use the latest cached historical snapshot on
    or before target-period end plus the configured horizon. Latest-revised
    values use the current `latest` observation vintage already stored locally.
    No network request is made.
    """
    plan = soft_target_plan(config)
    definitions = _definition_map()
    keys = [
        "state_date",
        "source_target",
        "target_period",
        "actual",
        "actual_release_date",
    ]
    missing = [column for column in keys if column not in dataset.columns]
    if missing:
        raise ValueError(f"Target reconstruction dataset is missing: {missing}")
    base = dataset[keys].drop_duplicates(
        subset=["state_date", "source_target", "target_period"], keep="last"
    )
    latest = repository.latest_observations(list(ALL_TARGETS))
    rows: list[dict[str, Any]] = []
    snapshot_cache: dict[tuple[str, date], pd.DataFrame] = {}

    for row in base.sort_values(["state_date", "source_target"]).itertuples(index=False):
        state_date = pd.Timestamp(row.state_date).date()
        target = str(row.source_target)
        target_period = _target_period(target, row.target_period)
        release_date = (
            pd.Timestamp(row.actual_release_date).date()
            if pd.notna(row.actual_release_date)
            else None
        )
        evaluation_date = (
            target_period.end_time.normalize().date()
            + timedelta(days=plan.fixed_horizon_days)
        )

        initial_value = float(row.actual) if pd.notna(row.actual) else float("nan")
        rows.append(
            {
                "state_date": state_date,
                "source_target": target,
                "target_period": str(target_period),
                "target_mode": "initial_release",
                "actual_value": initial_value,
                "actual_release_date": release_date,
                "requested_evaluation_date": release_date,
                "actual_as_of_date": release_date,
                "snapshot_gap_days": 0 if release_date else None,
                "availability_status": (
                    "available" if pd.notna(initial_value) and release_date else "missing"
                ),
                "revision_from_initial": 0.0 if pd.notna(initial_value) else None,
            }
        )

        snapshot_date = _latest_snapshot_date(
            repository,
            target=target,
            release_date=release_date,
            evaluation_date=evaluation_date,
        )
        fixed_value = float("nan")
        fixed_status = "missing_snapshot"
        gap_days: int | None = None
        if snapshot_date is not None:
            gap_days = int((evaluation_date - snapshot_date).days)
            if gap_days <= plan.maximum_snapshot_gap_days:
                cache_key = (target, snapshot_date)
                if cache_key not in snapshot_cache:
                    snapshot_cache[cache_key] = repository.historical_snapshot(
                        snapshot_date, [target]
                    )
                try:
                    fixed_value = _target_actual_from_frame(
                        snapshot_cache[cache_key],
                        target=target,
                        target_period=target_period,
                        definitions=definitions,
                    )
                    fixed_status = "available"
                except (KeyError, ValueError, TypeError):
                    fixed_status = "transformation_unavailable"
            else:
                fixed_status = "snapshot_too_stale"
        rows.append(
            {
                "state_date": state_date,
                "source_target": target,
                "target_period": str(target_period),
                "target_mode": "fixed_horizon_90d",
                "actual_value": fixed_value,
                "actual_release_date": release_date,
                "requested_evaluation_date": evaluation_date,
                "actual_as_of_date": snapshot_date,
                "snapshot_gap_days": gap_days,
                "availability_status": fixed_status,
                "revision_from_initial": (
                    fixed_value - initial_value
                    if pd.notna(fixed_value) and pd.notna(initial_value)
                    else None
                ),
            }
        )

        latest_value = float("nan")
        latest_status = "missing_latest_observation"
        latest_as_of: date | None = None
        try:
            latest_value = _target_actual_from_frame(
                latest,
                target=target,
                target_period=target_period,
                definitions=definitions,
            )
            latest_status = "available"
            target_latest = latest.loc[latest["series_id"].astype(str) == target]
            if not target_latest.empty and "retrieved_at" in target_latest:
                retrieved = pd.to_datetime(
                    target_latest["retrieved_at"], errors="coerce"
                ).max()
                latest_as_of = retrieved.date() if pd.notna(retrieved) else None
        except (KeyError, ValueError, TypeError):
            pass
        rows.append(
            {
                "state_date": state_date,
                "source_target": target,
                "target_period": str(target_period),
                "target_mode": "latest_revised",
                "actual_value": latest_value,
                "actual_release_date": release_date,
                "requested_evaluation_date": None,
                "actual_as_of_date": latest_as_of,
                "snapshot_gap_days": None,
                "availability_status": latest_status,
                "revision_from_initial": (
                    latest_value - initial_value
                    if pd.notna(latest_value) and pd.notna(initial_value)
                    else None
                ),
            }
        )

    result = pd.DataFrame(rows)
    result["state_date"] = pd.to_datetime(result["state_date"]).dt.date
    return result.sort_values(
        ["target_mode", "state_date", "source_target"]
    ).reset_index(drop=True)


def _candidate_from_source(core_candidate_id: str, config: dict[str, Any]) -> dict[str, Any]:
    candidates = {
        str(item["candidate_id"]): item for item in build_core_candidates(config)
    }
    if core_candidate_id not in candidates:
        raise RuntimeError(
            f"Source core candidate {core_candidate_id} is absent from governance."
        )
    return candidates[core_candidate_id]


def build_mode_monthlies(
    dataset: pd.DataFrame,
    actual_vintages: pd.DataFrame,
    source_monthly: pd.DataFrame,
    core_candidate: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    forecast_columns = [
        "state_date",
        "forecast_growth",
        "forecast_inflation",
        "forecast_labour",
        "forecast_regime",
        "forecast_family",
    ]
    if "probabilities_json" in source_monthly.columns:
        forecast_columns.append("probabilities_json")
    source_forecasts = source_monthly[forecast_columns].copy()
    source_forecasts["state_date"] = pd.to_datetime(
        source_forecasts["state_date"]
    ).dt.date
    output: dict[str, pd.DataFrame] = {}
    for mode in soft_target_plan(config).target_modes:
        values = actual_vintages.loc[
            (actual_vintages["target_mode"] == mode)
            & actual_vintages["actual_value"].notna(),
            ["state_date", "source_target", "target_period", "actual_value"],
        ]
        work = dataset.drop(columns=["actual"]).merge(
            values,
            on=["state_date", "source_target", "target_period"],
            how="inner",
        ).rename(columns={"actual_value": "actual"})
        counts = work.groupby("state_date")["source_target"].nunique()
        complete_dates = set(counts.loc[counts == len(ALL_TARGETS)].index)
        work = work.loc[work["state_date"].isin(complete_dates)].copy()
        if work.empty:
            output[mode] = pd.DataFrame()
            continue
        computed = candidate_monthly_states(work, core_candidate, config)
        computed = computed.drop(
            columns=[column for column in forecast_columns if column != "state_date"],
            errors="ignore",
        ).merge(source_forecasts, on="state_date", how="inner")
        computed.insert(0, "target_mode", mode)
        output[mode] = computed.sort_values("state_date").reset_index(drop=True)
    return output


def _perturbation_grid(epsilon: float) -> tuple[tuple[float, float, float], ...]:
    values = (-float(epsilon), 0.0, float(epsilon))
    return tuple(product(values, repeat=3))


def _normalise_probabilities(
    values: dict[str, float], labels: Iterable[str]
) -> dict[str, float]:
    output = {str(label): max(0.0, float(values.get(label, 0.0))) for label in labels}
    total = float(sum(output.values()))
    if total <= 0:
        return {label: 1.0 / len(output) for label in output}
    return {label: value / total for label, value in output.items()}


def family_probabilities_from_regimes(probabilities: dict[str, float]) -> dict[str, float]:
    regime = _normalise_probabilities(probabilities, REGIMES)
    families = {family: 0.0 for family in FAMILIES}
    for label, probability in regime.items():
        families[REGIME_FAMILY[label]] += probability
    return _normalise_probabilities(families, FAMILIES)


def _source_family_probabilities(row: Any) -> dict[str, float]:
    value = getattr(row, "probabilities_json", None)
    if value is not None and not (isinstance(value, float) and np.isnan(value)):
        parsed = json.loads(value) if isinstance(value, str) else dict(value)
        return family_probabilities_from_regimes(parsed)
    family = str(getattr(row, "forecast_family"))
    return {label: 1.0 if label == family else 0.0 for label in FAMILIES}


def soft_actual_distribution(
    growth: float,
    inflation: float,
    labour: float,
    config: dict[str, Any],
) -> dict[str, Any]:
    plan = soft_target_plan(config)
    threshold_map = config["tournament"]["threshold_candidates"]
    regime_counts = {label: 0 for label in REGIMES}
    family_counts = {label: 0 for label in FAMILIES}
    scenarios = 0
    for threshold_id in plan.threshold_ids:
        thresholds = threshold_map[threshold_id]
        for dg, di, dl in _perturbation_grid(plan.perturbation_epsilon):
            regime = classify_regime_with_thresholds(
                float(np.clip(growth + dg, -2.0, 2.0)),
                float(np.clip(inflation + di, -2.0, 2.0)),
                float(np.clip(labour + dl, -2.0, 2.0)),
                thresholds,
            )
            regime_counts[regime] += 1
            family_counts[REGIME_FAMILY[regime]] += 1
            scenarios += 1
    regime_probabilities = {
        label: count / scenarios for label, count in regime_counts.items()
    }
    family_probabilities = {
        label: count / scenarios for label, count in family_counts.items()
    }
    ordered_families = sorted(
        family_probabilities, key=family_probabilities.get, reverse=True
    )
    primary = ordered_families[0]
    second = ordered_families[1]
    top_probability = float(family_probabilities[primary])
    margin = top_probability - float(family_probabilities[second])
    ambiguous = bool(
        top_probability < plan.minimum_primary_probability
        or margin < plan.minimum_probability_margin
    )
    alternatives = [
        label
        for label in ordered_families[1:]
        if family_probabilities[label] >= plan.alternative_probability_floor
    ]
    threshold_hard = [
        REGIME_FAMILY[
            classify_regime_with_thresholds(
                growth, inflation, labour, threshold_map[threshold_id]
            )
        ]
        for threshold_id in plan.threshold_ids
    ]
    subtype = max(regime_probabilities, key=regime_probabilities.get)
    return {
        "primary_family": primary,
        "secondary_regime": subtype,
        "family_top_probability": top_probability,
        "family_probability_margin": margin,
        "ambiguity_indicator": ambiguous,
        "alternative_families_json": json.dumps(alternatives),
        "family_probabilities_json": json.dumps(
            family_probabilities, sort_keys=True
        ),
        "regime_probabilities_json": json.dumps(
            regime_probabilities, sort_keys=True
        ),
        "threshold_family_consensus": len(set(threshold_hard)) == 1,
        "scenario_count": scenarios,
    }


def build_soft_targets(
    mode_monthlies: dict[str, pd.DataFrame],
    config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for mode, monthly in mode_monthlies.items():
        if monthly.empty:
            continue
        for row in monthly.sort_values("state_date").itertuples(index=False):
            soft = soft_actual_distribution(
                float(row.actual_growth),
                float(row.actual_inflation),
                float(row.actual_labour),
                config,
            )
            forecast_probabilities = _source_family_probabilities(row)
            rows.append(
                {
                    **row._asdict(),
                    **soft,
                    "forecast_family_probabilities_json": json.dumps(
                        forecast_probabilities, sort_keys=True
                    ),
                    "forecast_top_family": max(
                        forecast_probabilities, key=forecast_probabilities.get
                    ),
                }
            )
    result = pd.DataFrame(rows)
    if not result.empty:
        result["state_date"] = pd.to_datetime(result["state_date"]).dt.date
    return result.sort_values(["target_mode", "state_date"]).reset_index(drop=True)


def _classification_metrics(actual: pd.Series, predicted: pd.Series) -> dict[str, float]:
    frame = pd.DataFrame({"actual": actual, "predicted": predicted}).dropna()
    if frame.empty:
        return {"accuracy": 0.0, "balanced_accuracy": 0.0, "macro_f1": 0.0}
    recalls: list[float] = []
    f1s: list[float] = []
    for label in FAMILIES:
        actual_mask = frame["actual"].astype(str) == label
        predicted_mask = frame["predicted"].astype(str) == label
        support = int(actual_mask.sum())
        forecast_count = int(predicted_mask.sum())
        tp = int((actual_mask & predicted_mask).sum())
        if support:
            recalls.append(tp / support)
        if support or forecast_count:
            precision = tp / forecast_count if forecast_count else 0.0
            recall = tp / support if support else 0.0
            f1s.append(
                2.0 * precision * recall / (precision + recall)
                if precision + recall
                else 0.0
            )
    return {
        "accuracy": float((frame["actual"] == frame["predicted"]).mean()),
        "balanced_accuracy": float(np.mean(recalls)) if recalls else 0.0,
        "macro_f1": float(np.mean(f1s)) if f1s else 0.0,
    }


def _probability_metrics(frame: pd.DataFrame) -> dict[str, float]:
    if frame.empty:
        return {
            "soft_brier": float("nan"),
            "soft_log_loss": float("nan"),
            "top2_coverage": float("nan"),
            "mean_actual_probability": float("nan"),
            "confidence_weighted_accuracy": float("nan"),
        }
    briers: list[float] = []
    losses: list[float] = []
    top2: list[float] = []
    actual_probabilities: list[float] = []
    weighted_correct: list[float] = []
    weights: list[float] = []
    for row in frame.itertuples(index=False):
        actual = _normalise_probabilities(
            json.loads(row.actual_probabilities_json), FAMILIES
        )
        predicted = _normalise_probabilities(
            json.loads(row.predicted_probabilities_json), FAMILIES
        )
        a = np.asarray([actual[label] for label in FAMILIES])
        p = np.asarray([predicted[label] for label in FAMILIES])
        briers.append(float(np.square(p - a).sum()))
        losses.append(
            float(-sum(actual[label] * math.log(max(predicted[label], 1e-12)) for label in FAMILIES))
        )
        top_labels = sorted(predicted, key=predicted.get, reverse=True)[:2]
        top2.append(float(str(row.actual_family) in top_labels))
        actual_probabilities.append(float(predicted[str(row.actual_family)]))
        weight = float(row.actual_confidence)
        weights.append(weight)
        weighted_correct.append(
            weight * float(str(row.actual_family) == str(row.predicted_family))
        )
    total_weight = float(sum(weights))
    return {
        "soft_brier": float(np.mean(briers)),
        "soft_log_loss": float(np.mean(losses)),
        "top2_coverage": float(np.mean(top2)),
        "mean_actual_probability": float(np.mean(actual_probabilities)),
        "confidence_weighted_accuracy": (
            float(sum(weighted_correct) / total_weight) if total_weight else 0.0
        ),
    }


def _contiguous(previous: Any, current: Any) -> bool:
    return int(pd.Period(pd.Timestamp(current), freq="M").ordinal) - int(
        pd.Period(pd.Timestamp(previous), freq="M").ordinal
    ) == 1


def evaluation_rows(soft_targets: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for mode, subset in soft_targets.groupby("target_mode", sort=False):
        previous_date: date | None = None
        previous_actual: dict[str, float] | None = None
        for row in subset.sort_values("state_date").itertuples(index=False):
            actual_probabilities = json.loads(row.family_probabilities_json)
            source_probabilities = json.loads(
                row.forecast_family_probabilities_json
            )
            rows.append(
                {
                    "target_mode": mode,
                    "state_date": row.state_date,
                    "benchmark_id": "source",
                    "actual_family": row.primary_family,
                    "predicted_family": max(
                        source_probabilities, key=source_probabilities.get
                    ),
                    "actual_probabilities_json": json.dumps(
                        actual_probabilities, sort_keys=True
                    ),
                    "predicted_probabilities_json": json.dumps(
                        source_probabilities, sort_keys=True
                    ),
                    "actual_confidence": float(row.family_top_probability),
                }
            )
            if (
                previous_actual is not None
                and previous_date is not None
                and _contiguous(previous_date, row.state_date)
            ):
                rows.append(
                    {
                        "target_mode": mode,
                        "state_date": row.state_date,
                        "benchmark_id": "persistence",
                        "actual_family": row.primary_family,
                        "predicted_family": max(
                            previous_actual, key=previous_actual.get
                        ),
                        "actual_probabilities_json": json.dumps(
                            actual_probabilities, sort_keys=True
                        ),
                        "predicted_probabilities_json": json.dumps(
                            previous_actual, sort_keys=True
                        ),
                        "actual_confidence": float(row.family_top_probability),
                    }
                )
            previous_date = row.state_date
            previous_actual = actual_probabilities
    return pd.DataFrame(rows)


def evaluate_benchmarks(
    soft_targets: pd.DataFrame,
    plan: RollingTournamentPlan,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = evaluation_rows(soft_targets)
    fold_records: list[dict[str, Any]] = []
    for mode in sorted(rows["target_mode"].unique()) if not rows.empty else []:
        mode_rows = rows.loc[rows["target_mode"] == mode]
        for fold in plan.folds:
            for benchmark in BENCHMARKS:
                frame = mode_rows.loc[
                    (mode_rows["benchmark_id"] == benchmark)
                    & mode_rows["state_date"].isin(set(fold.evaluation_dates))
                ].copy()
                if frame.empty:
                    continue
                classification = _classification_metrics(
                    frame["actual_family"], frame["predicted_family"]
                )
                probability = _probability_metrics(frame)
                fold_records.append(
                    {
                        "target_mode": mode,
                        "fold_id": fold.fold_id,
                        "evaluation_start": fold.evaluation_dates[0],
                        "evaluation_end": fold.evaluation_dates[-1],
                        "benchmark_id": benchmark,
                        "observations": len(frame),
                        "family_accuracy": classification["accuracy"],
                        "family_balanced_accuracy": classification[
                            "balanced_accuracy"
                        ],
                        "family_macro_f1": classification["macro_f1"],
                        **probability,
                    }
                )
    fold_metrics = pd.DataFrame(fold_records)
    if fold_metrics.empty:
        return fold_metrics, pd.DataFrame(), pd.DataFrame()

    comparison_rows: list[dict[str, Any]] = []
    for (mode, fold_id), frame in fold_metrics.groupby(
        ["target_mode", "fold_id"]
    ):
        indexed = frame.set_index("benchmark_id")
        if set(BENCHMARKS).issubset(indexed.index):
            source = indexed.loc["source"]
            persistence = indexed.loc["persistence"]
            comparison_rows.append(
                {
                    "target_mode": mode,
                    "fold_id": fold_id,
                    "source_family_accuracy": source["family_accuracy"],
                    "persistence_family_accuracy": persistence[
                        "family_accuracy"
                    ],
                    "source_macro_f1": source["family_macro_f1"],
                    "persistence_macro_f1": persistence["family_macro_f1"],
                    "source_weighted_accuracy": source[
                        "confidence_weighted_accuracy"
                    ],
                    "persistence_weighted_accuracy": persistence[
                        "confidence_weighted_accuracy"
                    ],
                    "baseline_margin": source[
                        "confidence_weighted_accuracy"
                    ]
                    - persistence["confidence_weighted_accuracy"],
                    "source_beats_persistence": bool(
                        source["confidence_weighted_accuracy"]
                        > persistence["confidence_weighted_accuracy"]
                    ),
                }
            )
    comparisons = pd.DataFrame(comparison_rows)

    summary_rows: list[dict[str, Any]] = []
    metric_columns = [
        "family_accuracy",
        "family_balanced_accuracy",
        "family_macro_f1",
        "soft_brier",
        "soft_log_loss",
        "top2_coverage",
        "mean_actual_probability",
        "confidence_weighted_accuracy",
    ]
    for (mode, benchmark), frame in fold_metrics.groupby(
        ["target_mode", "benchmark_id"]
    ):
        record: dict[str, Any] = {
            "target_mode": mode,
            "benchmark_id": benchmark,
            "folds": int(frame["fold_id"].nunique()),
        }
        for column in metric_columns:
            record[f"mean_{column}"] = float(frame[column].mean())
        mode_comparisons = comparisons.loc[comparisons["target_mode"] == mode]
        record["baseline_win_rate"] = (
            float(mode_comparisons["source_beats_persistence"].mean())
            if benchmark == "source" and not mode_comparisons.empty
            else None
        )
        record["mean_baseline_margin"] = (
            float(mode_comparisons["baseline_margin"].mean())
            if benchmark == "source" and not mode_comparisons.empty
            else None
        )
        summary_rows.append(record)
    summary = pd.DataFrame(summary_rows)
    return fold_metrics, comparisons, summary


def mode_completeness(
    dataset: pd.DataFrame,
    actual_vintages: pd.DataFrame,
    mode_monthlies: dict[str, pd.DataFrame],
    config: dict[str, Any],
) -> pd.DataFrame:
    expected_rows = len(
        dataset.drop_duplicates(
            subset=["state_date", "source_target", "target_period"]
        )
    )
    expected_states = int(dataset["state_date"].nunique())
    rows: list[dict[str, Any]] = []
    for mode in soft_target_plan(config).target_modes:
        subset = actual_vintages.loc[actual_vintages["target_mode"] == mode]
        available = int(subset["actual_value"].notna().sum())
        complete_states = len(mode_monthlies.get(mode, pd.DataFrame()))
        rows.append(
            {
                "target_mode": mode,
                "expected_target_rows": expected_rows,
                "available_target_rows": available,
                "target_row_completeness": (
                    available / expected_rows if expected_rows else 0.0
                ),
                "expected_states": expected_states,
                "complete_states": complete_states,
                "complete_state_share": (
                    complete_states / expected_states if expected_states else 0.0
                ),
            }
        )
    return pd.DataFrame(rows)


def vintage_agreement(
    mode_monthlies: dict[str, pd.DataFrame],
    soft_targets: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    pairs = (
        ("initial_release", "fixed_horizon_90d"),
        ("initial_release", "latest_revised"),
        ("fixed_horizon_90d", "latest_revised"),
    )
    for left_mode, right_mode in pairs:
        left = mode_monthlies.get(left_mode, pd.DataFrame())
        right = mode_monthlies.get(right_mode, pd.DataFrame())
        if left.empty or right.empty:
            rows.append(
                {
                    "left_mode": left_mode,
                    "right_mode": right_mode,
                    "common_months": 0,
                    "hard_family_agreement": float("nan"),
                    "hard_regime_agreement": float("nan"),
                    "soft_primary_family_agreement": float("nan"),
                    "growth_score_mae": float("nan"),
                    "inflation_score_mae": float("nan"),
                    "labour_score_mae": float("nan"),
                }
            )
            continue
        merged = left[
            [
                "state_date",
                "actual_family",
                "actual_regime",
                "actual_growth",
                "actual_inflation",
                "actual_labour",
            ]
        ].merge(
            right[
                [
                    "state_date",
                    "actual_family",
                    "actual_regime",
                    "actual_growth",
                    "actual_inflation",
                    "actual_labour",
                ]
            ],
            on="state_date",
            suffixes=("_left", "_right"),
        )
        left_soft = soft_targets.loc[
            soft_targets["target_mode"] == left_mode,
            ["state_date", "primary_family"],
        ]
        right_soft = soft_targets.loc[
            soft_targets["target_mode"] == right_mode,
            ["state_date", "primary_family"],
        ]
        soft = left_soft.merge(
            right_soft, on="state_date", suffixes=("_left", "_right")
        )
        rows.append(
            {
                "left_mode": left_mode,
                "right_mode": right_mode,
                "common_months": len(merged),
                "hard_family_agreement": float(
                    (merged["actual_family_left"] == merged["actual_family_right"]).mean()
                ),
                "hard_regime_agreement": float(
                    (merged["actual_regime_left"] == merged["actual_regime_right"]).mean()
                ),
                "soft_primary_family_agreement": (
                    float(
                        (
                            soft["primary_family_left"]
                            == soft["primary_family_right"]
                        ).mean()
                    )
                    if not soft.empty
                    else float("nan")
                ),
                "growth_score_mae": float(
                    np.mean(
                        np.abs(
                            merged["actual_growth_left"]
                            - merged["actual_growth_right"]
                        )
                    )
                ),
                "inflation_score_mae": float(
                    np.mean(
                        np.abs(
                            merged["actual_inflation_left"]
                            - merged["actual_inflation_right"]
                        )
                    )
                ),
                "labour_score_mae": float(
                    np.mean(
                        np.abs(
                            merged["actual_labour_left"]
                            - merged["actual_labour_right"]
                        )
                    )
                ),
            }
        )
    return pd.DataFrame(rows)


def prospective_shadow_status(
    source_monthly: pd.DataFrame,
    plan: RollingTournamentPlan,
    config: dict[str, Any],
) -> pd.DataFrame:
    start = soft_target_plan(config).prospective_shadow_start
    dates = pd.to_datetime(source_monthly["state_date"]).dt.date
    prospective = sorted(date_value for date_value in dates if date_value >= start)
    selection_leakage = any(date_value >= start for date_value in plan.selection_dates)
    audit_leakage = any(date_value >= start for date_value in plan.audit_dates)
    return pd.DataFrame(
        [
            {
                "prospective_shadow_start": start,
                "available_shadow_months": len(prospective),
                "first_shadow_month": prospective[0] if prospective else None,
                "last_shadow_month": prospective[-1] if prospective else None,
                "selection_contains_shadow_month": selection_leakage,
                "consumed_audit_contains_shadow_month": audit_leakage,
                "prospective_isolation_pass": not selection_leakage and not audit_leakage,
            }
        ]
    )


def _bootstrap_source_margin(
    soft_targets: pd.DataFrame,
    plan: RollingTournamentPlan,
    config: dict[str, Any],
) -> dict[str, float]:
    section = config["real_time_soft_targets"]
    rows = evaluation_rows(
        soft_targets.loc[soft_targets["target_mode"] == "initial_release"]
    )
    differences: list[np.ndarray] = []
    for fold in plan.folds:
        subset = rows.loc[rows["state_date"].isin(set(fold.evaluation_dates))]
        source = subset.loc[subset["benchmark_id"] == "source"].set_index("state_date")
        persistence = subset.loc[
            subset["benchmark_id"] == "persistence"
        ].set_index("state_date")
        common = source.index.intersection(persistence.index)
        values: list[float] = []
        for state_date in common:
            s = source.loc[state_date]
            p = persistence.loc[state_date]
            weight = float(s["actual_confidence"])
            source_correct = float(s["actual_family"] == s["predicted_family"])
            persistence_correct = float(
                p["actual_family"] == p["predicted_family"]
            )
            values.append(weight * (source_correct - persistence_correct))
        differences.append(np.asarray(values, dtype=float))
    return block_bootstrap_margin_ci(
        differences,
        repetitions=int(section["bootstrap_repetitions"]),
        block_months=int(section["bootstrap_block_months"]),
        confidence=float(section["bootstrap_confidence"]),
        seed=int(section["random_seed"]),
    )


def governance_flags(
    *,
    completeness: pd.DataFrame,
    agreement: pd.DataFrame,
    soft_targets: pd.DataFrame,
    benchmark_summary: pd.DataFrame,
    bootstrap: dict[str, float],
    prospective: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    thresholds = config["real_time_soft_targets"]["governance"]

    def completeness_value(mode: str) -> float:
        frame = completeness.loc[completeness["target_mode"] == mode]
        return float(frame.iloc[0]["complete_state_share"]) if not frame.empty else 0.0

    initial_latest = agreement.loc[
        (agreement["left_mode"] == "initial_release")
        & (agreement["right_mode"] == "latest_revised")
    ]
    vintage_agreement_value = (
        float(initial_latest.iloc[0]["soft_primary_family_agreement"])
        if not initial_latest.empty
        and pd.notna(initial_latest.iloc[0]["soft_primary_family_agreement"])
        else 0.0
    )
    initial_soft = soft_targets.loc[
        soft_targets["target_mode"] == "initial_release"
    ]
    mean_top = (
        float(initial_soft["family_top_probability"].mean())
        if not initial_soft.empty
        else 0.0
    )
    ambiguity_rate = (
        float(initial_soft["ambiguity_indicator"].mean())
        if not initial_soft.empty
        else 1.0
    )
    source_summary = benchmark_summary.loc[
        (benchmark_summary["target_mode"] == "initial_release")
        & (benchmark_summary["benchmark_id"] == "source")
    ]
    win_rate = (
        float(source_summary.iloc[0]["baseline_win_rate"])
        if not source_summary.empty
        and pd.notna(source_summary.iloc[0]["baseline_win_rate"])
        else 0.0
    )
    bootstrap_lower = float(bootstrap["bootstrap_margin_lower"])
    prospective_pass = bool(prospective.iloc[0]["prospective_isolation_pass"])

    checks = [
        (
            "initial_release_completeness",
            completeness_value("initial_release")
            >= float(thresholds["minimum_initial_release_completeness"]),
            completeness_value("initial_release"),
            float(thresholds["minimum_initial_release_completeness"]),
            "Initial-release target states must be complete and explicitly dated.",
        ),
        (
            "fixed_horizon_completeness",
            completeness_value("fixed_horizon_90d")
            >= float(thresholds["minimum_fixed_horizon_completeness"]),
            completeness_value("fixed_horizon_90d"),
            float(thresholds["minimum_fixed_horizon_completeness"]),
            "The fixed 90-day target requires sufficient cached-vintage coverage.",
        ),
        (
            "latest_revised_completeness",
            completeness_value("latest_revised")
            >= float(thresholds["minimum_latest_revised_completeness"]),
            completeness_value("latest_revised"),
            float(thresholds["minimum_latest_revised_completeness"]),
            "Latest-revised target states must be sufficiently complete.",
        ),
        (
            "initial_latest_family_agreement",
            vintage_agreement_value
            >= float(thresholds["minimum_initial_latest_family_agreement"]),
            vintage_agreement_value,
            float(thresholds["minimum_initial_latest_family_agreement"]),
            "Initial-release and latest-revised soft primary families should agree.",
        ),
        (
            "soft_target_confidence",
            mean_top >= float(thresholds["minimum_mean_family_top_probability"]),
            mean_top,
            float(thresholds["minimum_mean_family_top_probability"]),
            "Soft family targets should assign adequate probability to the primary family.",
        ),
        (
            "soft_target_ambiguity",
            ambiguity_rate <= float(thresholds["maximum_ambiguity_rate"]),
            ambiguity_rate,
            float(thresholds["maximum_ambiguity_rate"]),
            "The share of structurally ambiguous family labels should remain limited.",
        ),
        (
            "source_beats_persistence",
            win_rate >= float(thresholds["minimum_source_baseline_win_rate"]),
            win_rate,
            float(thresholds["minimum_source_baseline_win_rate"]),
            "The five-family source forecast should beat lagged-target persistence in most folds.",
        ),
        (
            "bootstrap_margin_positive",
            bootstrap_lower > float(thresholds["minimum_bootstrap_margin_lower"]),
            bootstrap_lower,
            float(thresholds["minimum_bootstrap_margin_lower"]),
            "The block-bootstrap lower confidence bound versus persistence must be positive.",
        ),
        (
            "prospective_shadow_isolation",
            prospective_pass,
            1.0 if prospective_pass else 0.0,
            1.0,
            "Months from the prospective shadow start must remain outside selection and consumed audit.",
        ),
    ]
    return pd.DataFrame(
        [
            {
                "check_id": check_id,
                "passed": bool(passed),
                "observed": float(observed),
                "threshold": float(threshold),
                "interpretation": interpretation,
            }
            for check_id, passed, observed, threshold, interpretation in checks
        ]
    )


def run_realtime_soft_target_audit(
    *,
    dataset: pd.DataFrame,
    actual_vintages: pd.DataFrame,
    source_monthly: pd.DataFrame,
    core_candidate: dict[str, Any],
    plan: RollingTournamentPlan,
    config: dict[str, Any],
) -> dict[str, Any]:
    mode_monthlies = build_mode_monthlies(
        dataset, actual_vintages, source_monthly, core_candidate, config
    )
    soft_targets = build_soft_targets(mode_monthlies, config)
    fold_metrics, fold_comparisons, benchmark_summary = evaluate_benchmarks(
        soft_targets, plan, config
    )
    completeness = mode_completeness(
        dataset, actual_vintages, mode_monthlies, config
    )
    agreement = vintage_agreement(mode_monthlies, soft_targets)
    prospective = prospective_shadow_status(source_monthly, plan, config)
    bootstrap = _bootstrap_source_margin(soft_targets, plan, config)
    flags = governance_flags(
        completeness=completeness,
        agreement=agreement,
        soft_targets=soft_targets,
        benchmark_summary=benchmark_summary,
        bootstrap=bootstrap,
        prospective=prospective,
        config=config,
    )
    monthly_frames = [frame for frame in mode_monthlies.values() if not frame.empty]
    mode_monthly = (
        pd.concat(monthly_frames, ignore_index=True)
        if monthly_frames
        else pd.DataFrame()
    )
    return {
        "mode_monthly": mode_monthly,
        "soft_targets": soft_targets,
        "mode_completeness": completeness,
        "vintage_agreement": agreement,
        "benchmark_fold_metrics": fold_metrics,
        "fold_comparisons": fold_comparisons,
        "benchmark_summary": benchmark_summary,
        "prospective_shadow": prospective,
        "bootstrap": bootstrap,
        "governance_flags": flags,
        "soft_target_governance_pass": bool(flags["passed"].all()),
    }
