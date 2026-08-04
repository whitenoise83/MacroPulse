from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from macropulse.macro_state.realtime_soft_targets import (
    FAMILIES,
    _classification_metrics,
    _normalise_probabilities,
    prospective_shadow_status,
)
from macropulse.macro_state.rolling_tournament import (
    RollingTournamentPlan,
    block_bootstrap_margin_ci,
)
from macropulse.macro_state.tournament import ALL_TARGETS

PRIMARY_TARGET_MODE = "fixed_horizon_90d"
BENCHMARKS = (
    "source",
    "hard_persistence",
    "soft_persistence",
    "dirichlet_persistence",
    "markov_first_order",
    "rolling_frequency",
)


@dataclass(frozen=True)
class FixedHorizonBenchmarkPlan:
    primary_target_mode: str
    governance_reference: str
    dirichlet_alpha: float
    markov_alpha: float
    rolling_window_months: int
    calibration_bins: int
    prospective_shadow_start: date


def fixed_horizon_plan(config: dict[str, Any]) -> FixedHorizonBenchmarkPlan:
    section = config["fixed_horizon_probabilistic_benchmarks"]
    primary = str(section["primary_target_mode"])
    if primary != PRIMARY_TARGET_MODE:
        raise ValueError(
            "Model 1D v0.3.6 locks the primary target to fixed_horizon_90d."
        )
    reference = str(section["governance_reference"])
    if reference not in BENCHMARKS or reference == "source":
        raise ValueError(f"Invalid governance benchmark: {reference}")
    bins = int(section["calibration_bins"])
    if bins < 2:
        raise ValueError("Calibration diagnostics require at least two bins.")
    return FixedHorizonBenchmarkPlan(
        primary_target_mode=primary,
        governance_reference=reference,
        dirichlet_alpha=float(section["dirichlet_alpha"]),
        markov_alpha=float(section["markov_alpha"]),
        rolling_window_months=int(section["rolling_window_months"]),
        calibration_bins=bins,
        prospective_shadow_start=pd.Timestamp(
            section["prospective_shadow_start"]
        ).date(),
    )


def _one_hot(label: str) -> dict[str, float]:
    return {family: 1.0 if family == label else 0.0 for family in FAMILIES}


def dirichlet_smooth(
    probabilities: dict[str, float], alpha: float
) -> dict[str, float]:
    if alpha < 0:
        raise ValueError("Dirichlet alpha cannot be negative.")
    base = _normalise_probabilities(probabilities, FAMILIES)
    denominator = 1.0 + alpha * len(FAMILIES)
    return {
        family: (base[family] + alpha) / denominator for family in FAMILIES
    }


def fixed_horizon_state_availability(
    actual_vintages: pd.DataFrame,
) -> pd.DataFrame:
    required = {
        "state_date",
        "source_target",
        "target_mode",
        "actual_value",
        "requested_evaluation_date",
        "actual_as_of_date",
        "availability_status",
    }
    missing = sorted(required - set(actual_vintages.columns))
    if missing:
        raise ValueError(f"Actual-vintage evidence is missing columns: {missing}")
    fixed = actual_vintages.loc[
        actual_vintages["target_mode"].astype(str) == PRIMARY_TARGET_MODE
    ].copy()
    if fixed.empty:
        return pd.DataFrame(
            columns=[
                "state_date",
                "expected_targets",
                "available_targets",
                "complete_state",
                "state_available_date",
                "latest_actual_as_of_date",
            ]
        )
    fixed["state_date"] = pd.to_datetime(fixed["state_date"]).dt.date
    fixed["requested_evaluation_date"] = pd.to_datetime(
        fixed["requested_evaluation_date"]
    ).dt.date
    fixed["actual_as_of_date"] = pd.to_datetime(
        fixed["actual_as_of_date"]
    ).dt.date
    rows: list[dict[str, Any]] = []
    for state_date, frame in fixed.groupby("state_date", sort=True):
        available = frame.loc[
            frame["actual_value"].notna()
            & (frame["availability_status"].astype(str) == "available")
        ]
        complete = int(available["source_target"].nunique()) == len(ALL_TARGETS)
        rows.append(
            {
                "state_date": state_date,
                "expected_targets": len(ALL_TARGETS),
                "available_targets": int(available["source_target"].nunique()),
                "complete_state": bool(complete),
                "state_available_date": (
                    max(available["requested_evaluation_date"])
                    if complete and not available.empty
                    else None
                ),
                "latest_actual_as_of_date": (
                    max(available["actual_as_of_date"])
                    if complete and not available.empty
                    else None
                ),
            }
        )
    return pd.DataFrame(rows)


def fixed_horizon_missing_evidence(
    actual_vintages: pd.DataFrame,
) -> pd.DataFrame:
    fixed = actual_vintages.loc[
        actual_vintages["target_mode"].astype(str) == PRIMARY_TARGET_MODE
    ].copy()
    if fixed.empty:
        return pd.DataFrame()
    fixed["state_date"] = pd.to_datetime(fixed["state_date"]).dt.date
    unavailable = fixed.loc[
        fixed["actual_value"].isna()
        | (fixed["availability_status"].astype(str) != "available")
    ].copy()
    if unavailable.empty:
        return unavailable
    columns = [
        "state_date",
        "source_target",
        "target_period",
        "availability_status",
        "requested_evaluation_date",
        "actual_as_of_date",
        "snapshot_gap_days",
    ]
    return unavailable[columns].sort_values(
        ["state_date", "source_target"]
    ).reset_index(drop=True)


def locked_target_frame(
    soft_targets: pd.DataFrame,
    availability: pd.DataFrame,
) -> pd.DataFrame:
    fixed = soft_targets.loc[
        soft_targets["target_mode"].astype(str) == PRIMARY_TARGET_MODE
    ].copy()
    if fixed.empty:
        return fixed
    fixed["state_date"] = pd.to_datetime(fixed["state_date"]).dt.date
    available = availability.loc[availability["complete_state"]].copy()
    result = fixed.merge(available, on="state_date", how="inner")
    return result.sort_values("state_date").reset_index(drop=True)


def _latest_available_history(
    target: pd.DataFrame,
    evaluation_date: date,
) -> pd.DataFrame:
    history = target.loc[
        (target["state_date"] < evaluation_date)
        & target["state_available_date"].notna()
        & (target["state_available_date"] <= evaluation_date)
    ].copy()
    return history.sort_values("state_date").reset_index(drop=True)


def _rolling_frequency(
    history: pd.DataFrame, window: int
) -> dict[str, float]:
    recent = history.tail(max(1, int(window)))
    counts = recent["primary_family"].astype(str).value_counts()
    values = {family: float(counts.get(family, 0.0)) for family in FAMILIES}
    return _normalise_probabilities(values, FAMILIES)


def _markov_probabilities(
    history: pd.DataFrame,
    current_family: str,
    alpha: float,
) -> dict[str, float]:
    counts = {family: float(alpha) for family in FAMILIES}
    ordered = history.sort_values("state_date")
    previous: Any = None
    previous_date: Any = None
    for row in ordered.itertuples(index=False):
        if previous is not None and previous_date is not None:
            ordinal_gap = int(
                pd.Period(row.state_date, freq="M").ordinal
                - pd.Period(previous_date, freq="M").ordinal
            )
            if ordinal_gap == 1 and str(previous) == current_family:
                counts[str(row.primary_family)] += 1.0
        previous = row.primary_family
        previous_date = row.state_date
    if sum(counts.values()) <= 0:
        return _rolling_frequency(history, len(history))
    return _normalise_probabilities(counts, FAMILIES)


def build_benchmark_predictions(
    locked_targets: pd.DataFrame,
    plan: RollingTournamentPlan,
    config: dict[str, Any],
) -> pd.DataFrame:
    benchmark_plan = fixed_horizon_plan(config)
    rows: list[dict[str, Any]] = []
    evaluation_dates = {
        date_value for fold in plan.folds for date_value in fold.evaluation_dates
    }
    for row in locked_targets.loc[
        locked_targets["state_date"].isin(evaluation_dates)
    ].sort_values("state_date").itertuples(index=False):
        actual_probabilities = _normalise_probabilities(
            json.loads(row.family_probabilities_json), FAMILIES
        )
        source_probabilities = _normalise_probabilities(
            json.loads(row.forecast_family_probabilities_json), FAMILIES
        )
        history = _latest_available_history(locked_targets, row.state_date)
        if history.empty:
            continue
        previous = history.iloc[-1]
        previous_soft = _normalise_probabilities(
            json.loads(previous["family_probabilities_json"]), FAMILIES
        )
        previous_family = str(previous["primary_family"])
        predictions = {
            "source": source_probabilities,
            "hard_persistence": _one_hot(previous_family),
            "soft_persistence": previous_soft,
            "dirichlet_persistence": dirichlet_smooth(
                previous_soft, benchmark_plan.dirichlet_alpha
            ),
            "markov_first_order": _markov_probabilities(
                history, previous_family, benchmark_plan.markov_alpha
            ),
            "rolling_frequency": _rolling_frequency(
                history, benchmark_plan.rolling_window_months
            ),
        }
        for benchmark_id, predicted in predictions.items():
            rows.append(
                {
                    "state_date": row.state_date,
                    "benchmark_id": benchmark_id,
                    "actual_family": str(row.primary_family),
                    "actual_confidence": float(row.family_top_probability),
                    "actual_probabilities_json": json.dumps(
                        actual_probabilities, sort_keys=True
                    ),
                    "predicted_family": max(predicted, key=predicted.get),
                    "predicted_probabilities_json": json.dumps(
                        predicted, sort_keys=True
                    ),
                    "predicted_top_probability": float(max(predicted.values())),
                    "history_rows": len(history),
                    "latest_target_state": previous["state_date"],
                    "latest_target_available_date": previous[
                        "state_available_date"
                    ],
                    "availability_no_lookahead": bool(
                        previous["state_available_date"] <= row.state_date
                    ),
                }
            )
    return pd.DataFrame(rows)


def _probability_arrays(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    actual_rows: list[list[float]] = []
    predicted_rows: list[list[float]] = []
    for row in frame.itertuples(index=False):
        actual = _normalise_probabilities(
            json.loads(row.actual_probabilities_json), FAMILIES
        )
        predicted = _normalise_probabilities(
            json.loads(row.predicted_probabilities_json), FAMILIES
        )
        actual_rows.append([actual[family] for family in FAMILIES])
        predicted_rows.append([predicted[family] for family in FAMILIES])
    return np.asarray(actual_rows, dtype=float), np.asarray(
        predicted_rows, dtype=float
    )


def calibration_error(frame: pd.DataFrame, bins: int) -> float:
    if frame.empty:
        return float("nan")
    confidence = pd.to_numeric(
        frame["predicted_top_probability"], errors="coerce"
    ).to_numpy(dtype=float)
    correctness = (
        frame["actual_family"].astype(str)
        == frame["predicted_family"].astype(str)
    ).to_numpy(dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for index in range(bins):
        lower, upper = edges[index], edges[index + 1]
        mask = (
            (confidence >= lower)
            & ((confidence < upper) if index < bins - 1 else (confidence <= upper))
        )
        if not mask.any():
            continue
        ece += float(mask.mean()) * abs(
            float(confidence[mask].mean()) - float(correctness[mask].mean())
        )
    return float(ece)


def reliability_rows(
    frame: pd.DataFrame,
    *,
    fold_id: str,
    benchmark_id: str,
    bins: int,
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    confidence = pd.to_numeric(
        frame["predicted_top_probability"], errors="coerce"
    ).to_numpy(dtype=float)
    correctness = (
        frame["actual_family"].astype(str)
        == frame["predicted_family"].astype(str)
    ).to_numpy(dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    rows: list[dict[str, Any]] = []
    for index in range(bins):
        lower, upper = edges[index], edges[index + 1]
        mask = (
            (confidence >= lower)
            & ((confidence < upper) if index < bins - 1 else (confidence <= upper))
        )
        rows.append(
            {
                "fold_id": fold_id,
                "benchmark_id": benchmark_id,
                "bin_id": index + 1,
                "bin_lower": lower,
                "bin_upper": upper,
                "observations": int(mask.sum()),
                "mean_confidence": (
                    float(confidence[mask].mean()) if mask.any() else float("nan")
                ),
                "empirical_accuracy": (
                    float(correctness[mask].mean()) if mask.any() else float("nan")
                ),
            }
        )
    return pd.DataFrame(rows)


def brier_decomposition(frame: pd.DataFrame, bins: int) -> dict[str, float]:
    if frame.empty:
        return {
            "hard_brier": float("nan"),
            "brier_reliability": float("nan"),
            "brier_resolution": float("nan"),
            "brier_uncertainty": float("nan"),
            "brier_decomposition_residual": float("nan"),
        }
    predicted = []
    actual_hard = []
    for row in frame.itertuples(index=False):
        probabilities = _normalise_probabilities(
            json.loads(row.predicted_probabilities_json), FAMILIES
        )
        predicted.append([probabilities[family] for family in FAMILIES])
        actual_hard.append(
            [1.0 if str(row.actual_family) == family else 0.0 for family in FAMILIES]
        )
    p = np.asarray(predicted, dtype=float)
    y = np.asarray(actual_hard, dtype=float)
    hard_brier = float(np.mean(np.square(p - y).sum(axis=1)))
    edges = np.linspace(0.0, 1.0, bins + 1)
    reliability = 0.0
    resolution = 0.0
    uncertainty = 0.0
    n = len(frame)
    for class_index in range(len(FAMILIES)):
        y_bar = float(y[:, class_index].mean())
        uncertainty += y_bar * (1.0 - y_bar)
        for bin_index in range(bins):
            lower, upper = edges[bin_index], edges[bin_index + 1]
            values = p[:, class_index]
            mask = (
                (values >= lower)
                & ((values < upper) if bin_index < bins - 1 else (values <= upper))
            )
            if not mask.any():
                continue
            weight = float(mask.sum()) / n
            p_bar = float(values[mask].mean())
            o_bar = float(y[mask, class_index].mean())
            reliability += weight * (p_bar - o_bar) ** 2
            resolution += weight * (o_bar - y_bar) ** 2
    residual = hard_brier - (reliability - resolution + uncertainty)
    return {
        "hard_brier": hard_brier,
        "brier_reliability": float(reliability),
        "brier_resolution": float(resolution),
        "brier_uncertainty": float(uncertainty),
        "brier_decomposition_residual": float(residual),
    }


def probability_metrics(frame: pd.DataFrame, bins: int) -> dict[str, float]:
    if frame.empty:
        return {
            "soft_brier": float("nan"),
            "soft_log_loss": float("nan"),
            "top2_coverage": float("nan"),
            "mean_actual_probability": float("nan"),
            "confidence_weighted_accuracy": float("nan"),
            "expected_calibration_error": float("nan"),
            **brier_decomposition(frame, bins),
        }
    actual, predicted = _probability_arrays(frame)
    soft_brier = float(np.mean(np.square(predicted - actual).sum(axis=1)))
    soft_log_loss = float(
        np.mean(
            -np.sum(actual * np.log(np.maximum(predicted, 1e-12)), axis=1)
        )
    )
    top2: list[float] = []
    actual_probability: list[float] = []
    weighted_correct: list[float] = []
    weights: list[float] = []
    for row in frame.itertuples(index=False):
        probabilities = _normalise_probabilities(
            json.loads(row.predicted_probabilities_json), FAMILIES
        )
        ordered = sorted(probabilities, key=probabilities.get, reverse=True)
        top2.append(float(str(row.actual_family) in ordered[:2]))
        actual_probability.append(probabilities[str(row.actual_family)])
        weight = float(row.actual_confidence)
        weights.append(weight)
        weighted_correct.append(
            weight
            * float(str(row.actual_family) == str(row.predicted_family))
        )
    total_weight = float(sum(weights))
    return {
        "soft_brier": soft_brier,
        "soft_log_loss": soft_log_loss,
        "top2_coverage": float(np.mean(top2)),
        "mean_actual_probability": float(np.mean(actual_probability)),
        "confidence_weighted_accuracy": (
            float(sum(weighted_correct) / total_weight) if total_weight else 0.0
        ),
        "expected_calibration_error": calibration_error(frame, bins),
        **brier_decomposition(frame, bins),
    }


def evaluate_probabilistic_benchmarks(
    predictions: pd.DataFrame,
    plan: RollingTournamentPlan,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    benchmark_plan = fixed_horizon_plan(config)
    fold_records: list[dict[str, Any]] = []
    reliability_frames: list[pd.DataFrame] = []
    for fold in plan.folds:
        for benchmark_id in BENCHMARKS:
            frame = predictions.loc[
                (predictions["benchmark_id"] == benchmark_id)
                & predictions["state_date"].isin(set(fold.evaluation_dates))
            ].copy()
            if frame.empty:
                continue
            classification = _classification_metrics(
                frame["actual_family"], frame["predicted_family"]
            )
            probability = probability_metrics(
                frame, benchmark_plan.calibration_bins
            )
            fold_records.append(
                {
                    "fold_id": fold.fold_id,
                    "evaluation_start": fold.evaluation_dates[0],
                    "evaluation_end": fold.evaluation_dates[-1],
                    "benchmark_id": benchmark_id,
                    "observations": len(frame),
                    "family_accuracy": classification["accuracy"],
                    "family_balanced_accuracy": classification[
                        "balanced_accuracy"
                    ],
                    "family_macro_f1": classification["macro_f1"],
                    **probability,
                    "availability_no_lookahead": bool(
                        frame["availability_no_lookahead"].all()
                    ),
                }
            )
            reliability_frames.append(
                reliability_rows(
                    frame,
                    fold_id=fold.fold_id,
                    benchmark_id=benchmark_id,
                    bins=benchmark_plan.calibration_bins,
                )
            )
    fold_metrics = pd.DataFrame(fold_records)
    reliability = (
        pd.concat(reliability_frames, ignore_index=True)
        if reliability_frames
        else pd.DataFrame()
    )
    if fold_metrics.empty:
        return fold_metrics, pd.DataFrame(), pd.DataFrame(), reliability

    comparison_rows: list[dict[str, Any]] = []
    reference = benchmark_plan.governance_reference
    for fold_id, frame in fold_metrics.groupby("fold_id"):
        indexed = frame.set_index("benchmark_id")
        if "source" not in indexed.index or reference not in indexed.index:
            continue
        source = indexed.loc["source"]
        baseline = indexed.loc[reference]
        non_source = frame.loc[frame["benchmark_id"] != "source"]
        strongest_brier = str(
            non_source.sort_values(["soft_brier", "benchmark_id"]).iloc[0][
                "benchmark_id"
            ]
        )
        comparison_rows.append(
            {
                "fold_id": fold_id,
                "reference_benchmark": reference,
                "source_weighted_accuracy": source[
                    "confidence_weighted_accuracy"
                ],
                "reference_weighted_accuracy": baseline[
                    "confidence_weighted_accuracy"
                ],
                "weighted_accuracy_margin": source[
                    "confidence_weighted_accuracy"
                ]
                - baseline["confidence_weighted_accuracy"],
                "source_beats_reference": bool(
                    source["confidence_weighted_accuracy"]
                    > baseline["confidence_weighted_accuracy"]
                ),
                "source_macro_f1": source["family_macro_f1"],
                "reference_macro_f1": baseline["family_macro_f1"],
                "macro_f1_margin": source["family_macro_f1"]
                - baseline["family_macro_f1"],
                "source_soft_brier": source["soft_brier"],
                "reference_soft_brier": baseline["soft_brier"],
                "soft_brier_improvement": baseline["soft_brier"]
                - source["soft_brier"],
                "source_ece": source["expected_calibration_error"],
                "reference_ece": baseline["expected_calibration_error"],
                "ece_improvement": baseline["expected_calibration_error"]
                - source["expected_calibration_error"],
                "strongest_non_source_brier_benchmark": strongest_brier,
                "source_brier_rank": int(
                    frame["soft_brier"].rank(method="min").loc[
                        frame["benchmark_id"] == "source"
                    ].iloc[0]
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
        "expected_calibration_error",
        "hard_brier",
        "brier_reliability",
        "brier_resolution",
        "brier_uncertainty",
    ]
    for benchmark_id, frame in fold_metrics.groupby("benchmark_id"):
        record: dict[str, Any] = {
            "benchmark_id": benchmark_id,
            "folds": int(frame["fold_id"].nunique()),
        }
        for column in metric_columns:
            record[f"mean_{column}"] = float(frame[column].mean())
        if benchmark_id == "source" and not comparisons.empty:
            record["reference_win_rate"] = float(
                comparisons["source_beats_reference"].mean()
            )
            record["mean_weighted_accuracy_margin"] = float(
                comparisons["weighted_accuracy_margin"].mean()
            )
            record["mean_macro_f1_margin"] = float(
                comparisons["macro_f1_margin"].mean()
            )
            record["mean_soft_brier_improvement"] = float(
                comparisons["soft_brier_improvement"].mean()
            )
            record["mean_source_brier_rank"] = float(
                comparisons["source_brier_rank"].mean()
            )
        else:
            record["reference_win_rate"] = None
            record["mean_weighted_accuracy_margin"] = None
            record["mean_macro_f1_margin"] = None
            record["mean_soft_brier_improvement"] = None
            record["mean_source_brier_rank"] = None
        summary_rows.append(record)
    summary = pd.DataFrame(summary_rows).sort_values(
        ["mean_soft_brier", "benchmark_id"]
    ).reset_index(drop=True)
    summary.insert(0, "soft_brier_rank", np.arange(1, len(summary) + 1))
    return fold_metrics, comparisons, summary, reliability


def bootstrap_reference_margin(
    predictions: pd.DataFrame,
    plan: RollingTournamentPlan,
    config: dict[str, Any],
) -> dict[str, float]:
    section = config["fixed_horizon_probabilistic_benchmarks"]
    reference = fixed_horizon_plan(config).governance_reference
    differences: list[np.ndarray] = []
    for fold in plan.folds:
        subset = predictions.loc[
            predictions["state_date"].isin(set(fold.evaluation_dates))
        ]
        source = subset.loc[subset["benchmark_id"] == "source"].set_index(
            "state_date"
        )
        baseline = subset.loc[
            subset["benchmark_id"] == reference
        ].set_index("state_date")
        common = source.index.intersection(baseline.index)
        values: list[float] = []
        for state_date in common:
            source_row = source.loc[state_date]
            baseline_row = baseline.loc[state_date]
            weight = float(source_row["actual_confidence"])
            values.append(
                weight
                * (
                    float(
                        source_row["actual_family"]
                        == source_row["predicted_family"]
                    )
                    - float(
                        baseline_row["actual_family"]
                        == baseline_row["predicted_family"]
                    )
                )
            )
        differences.append(np.asarray(values, dtype=float))
    return block_bootstrap_margin_ci(
        differences,
        repetitions=int(section["bootstrap_repetitions"]),
        block_months=int(section["bootstrap_block_months"]),
        confidence=float(section["bootstrap_confidence"]),
        seed=int(section["random_seed"]),
    )


def fixed_horizon_governance_flags(
    *,
    availability: pd.DataFrame,
    missing_evidence: pd.DataFrame,
    predictions: pd.DataFrame,
    comparisons: pd.DataFrame,
    summary: pd.DataFrame,
    bootstrap: dict[str, float],
    prospective: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    section = config["fixed_horizon_probabilistic_benchmarks"]
    thresholds = section["governance"]
    complete_share = (
        float(availability["complete_state"].mean())
        if not availability.empty
        else 0.0
    )
    documented = bool(
        int((~availability["complete_state"]).sum())
        == int(missing_evidence["state_date"].nunique())
    ) if not availability.empty else False
    no_lookahead = bool(predictions["availability_no_lookahead"].all()) if not predictions.empty else False
    source_summary = summary.loc[summary["benchmark_id"] == "source"]
    if source_summary.empty:
        win_rate = 0.0
        macro_margin = -math.inf
        brier_improvement = -math.inf
        ece = math.inf
        top2 = 0.0
    else:
        row = source_summary.iloc[0]
        win_rate = float(row["reference_win_rate"])
        macro_margin = float(row["mean_macro_f1_margin"])
        brier_improvement = float(row["mean_soft_brier_improvement"])
        ece = float(row["mean_expected_calibration_error"])
        top2 = float(row["mean_top2_coverage"])
    bootstrap_lower = float(bootstrap["bootstrap_margin_lower"])
    prospective_pass = bool(prospective.iloc[0]["prospective_isolation_pass"])
    checks = [
        (
            "fixed_horizon_target_locked",
            fixed_horizon_plan(config).primary_target_mode == PRIMARY_TARGET_MODE,
            1.0,
            1.0,
            "The five-family fixed-90-day target is the locked primary research target.",
        ),
        (
            "fixed_horizon_state_completeness",
            complete_share >= float(thresholds["minimum_complete_state_share"]),
            complete_share,
            float(thresholds["minimum_complete_state_share"]),
            "The locked target requires sufficient complete states without revised-value substitution.",
        ),
        (
            "missing_evidence_documented",
            documented,
            1.0 if documented else 0.0,
            1.0,
            "Every incomplete fixed-horizon state must have explicit missing-target evidence.",
        ),
        (
            "latest_revised_substitution_prohibited",
            not bool(section["allow_latest_revised_substitution"]),
            1.0 if not bool(section["allow_latest_revised_substitution"]) else 0.0,
            1.0,
            "Missing fixed-horizon observations cannot be replaced with latest-revised values.",
        ),
        (
            "benchmark_availability_no_lookahead",
            no_lookahead,
            1.0 if no_lookahead else 0.0,
            1.0,
            "Probabilistic benchmarks may only use target states available by the forecast month.",
        ),
        (
            "source_reference_fold_win_rate",
            win_rate >= float(thresholds["minimum_reference_win_rate"]),
            win_rate,
            float(thresholds["minimum_reference_win_rate"]),
            "The source must beat the pre-specified soft-persistence reference in most folds.",
        ),
        (
            "bootstrap_margin_positive",
            bootstrap_lower > float(thresholds["minimum_bootstrap_margin_lower"]),
            bootstrap_lower,
            float(thresholds["minimum_bootstrap_margin_lower"]),
            "The block-bootstrap lower confidence bound versus the reference must be positive.",
        ),
        (
            "macro_f1_not_reduced",
            macro_margin >= float(thresholds["minimum_macro_f1_margin"]),
            macro_margin,
            float(thresholds["minimum_macro_f1_margin"]),
            "The source cannot improve common-family accuracy by reducing macro-F1.",
        ),
        (
            "soft_brier_improves_reference",
            brier_improvement > float(thresholds["minimum_soft_brier_improvement"]),
            brier_improvement,
            float(thresholds["minimum_soft_brier_improvement"]),
            "The source must improve soft Brier score over probabilistic persistence.",
        ),
        (
            "source_calibration_error",
            ece <= float(thresholds["maximum_expected_calibration_error"]),
            ece,
            float(thresholds["maximum_expected_calibration_error"]),
            "Expected calibration error must remain below the research ceiling.",
        ),
        (
            "source_top2_coverage",
            top2 >= float(thresholds["minimum_top2_coverage"]),
            top2,
            float(thresholds["minimum_top2_coverage"]),
            "The realised primary family should be contained in the top two source probabilities often enough.",
        ),
        (
            "prospective_shadow_isolation",
            prospective_pass,
            1.0 if prospective_pass else 0.0,
            1.0,
            "Months beginning April 2026 remain outside selection and consumed audit.",
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


def run_fixed_horizon_probabilistic_audit(
    *,
    actual_vintages: pd.DataFrame,
    soft_targets: pd.DataFrame,
    source_monthly: pd.DataFrame,
    plan: RollingTournamentPlan,
    config: dict[str, Any],
) -> dict[str, Any]:
    availability = fixed_horizon_state_availability(actual_vintages)
    missing_evidence = fixed_horizon_missing_evidence(actual_vintages)
    locked = locked_target_frame(soft_targets, availability)
    predictions = build_benchmark_predictions(locked, plan, config)
    fold_metrics, comparisons, summary, reliability = (
        evaluate_probabilistic_benchmarks(predictions, plan, config)
    )
    bootstrap = bootstrap_reference_margin(predictions, plan, config)
    prospective = prospective_shadow_status(source_monthly, plan, config)
    flags = fixed_horizon_governance_flags(
        availability=availability,
        missing_evidence=missing_evidence,
        predictions=predictions,
        comparisons=comparisons,
        summary=summary,
        bootstrap=bootstrap,
        prospective=prospective,
        config=config,
    )
    target_lock = pd.DataFrame(
        [
            {
                "primary_target_mode": PRIMARY_TARGET_MODE,
                "primary_target_level": "five_family",
                "secondary_target_level": "eight_state_report_only",
                "governance_reference": fixed_horizon_plan(
                    config
                ).governance_reference,
                "latest_revised_substitution_allowed": bool(
                    config["fixed_horizon_probabilistic_benchmarks"][
                        "allow_latest_revised_substitution"
                    ]
                ),
                "complete_states": int(availability["complete_state"].sum()),
                "expected_states": len(availability),
                "missing_states": int((~availability["complete_state"]).sum()),
            }
        ]
    )
    return {
        "target_lock": target_lock,
        "state_availability": availability,
        "missing_evidence": missing_evidence,
        "locked_targets": locked,
        "benchmark_predictions": predictions,
        "benchmark_fold_metrics": fold_metrics,
        "fold_comparisons": comparisons,
        "benchmark_summary": summary,
        "reliability": reliability,
        "bootstrap": bootstrap,
        "prospective_shadow": prospective,
        "governance_flags": flags,
        "fixed_horizon_governance_pass": bool(flags["passed"].all()),
    }
