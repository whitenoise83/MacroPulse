from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from itertools import product
from typing import Any, Iterable

import numpy as np
import pandas as pd

from macropulse.macro_state.rolling_tournament import RollingFold, RollingTournamentPlan
from macropulse.macro_state.tournament import (
    REGIMES,
    REGIME_FAMILY,
    classify_regime_with_thresholds,
)

DIMENSIONS = ("growth", "inflation", "labour")
FAMILIES = tuple(sorted(set(REGIME_FAMILY.values())))
BENCHMARK_IDS = (
    "source_direct",
    "persistence",
    "training_mode",
    "rolling_mode",
    "markov_first_order",
    "forecast_sign_rule",
)


@dataclass(frozen=True)
class TargetValidityPlan:
    perturbation_epsilons: tuple[float, ...]
    threshold_ids: tuple[str, ...]
    economic_horizons: tuple[int, ...]
    rolling_mode_months: int


def audit_plan(config: dict[str, Any]) -> TargetValidityPlan:
    section = config["target_validity_audit"]
    epsilons = tuple(float(value) for value in section["perturbation_epsilons"])
    threshold_ids = tuple(str(value) for value in section["threshold_ids"])
    horizons = tuple(int(value) for value in section["economic_horizons_months"])
    if not epsilons or any(value <= 0 for value in epsilons):
        raise ValueError("Perturbation epsilons must be positive.")
    if not horizons or any(value <= 0 for value in horizons):
        raise ValueError("Economic horizons must be positive.")
    unknown = set(threshold_ids) - set(config["tournament"]["threshold_candidates"])
    if unknown:
        raise ValueError(f"Unknown target-audit thresholds: {sorted(unknown)}")
    return TargetValidityPlan(
        perturbation_epsilons=epsilons,
        threshold_ids=threshold_ids,
        economic_horizons=horizons,
        rolling_mode_months=int(section["rolling_mode_months"]),
    )


def _month_ordinal(value: Any) -> int:
    return int(pd.Period(pd.Timestamp(value), freq="M").ordinal)


def _contiguous(previous: Any, current: Any) -> bool:
    return _month_ordinal(current) - _month_ordinal(previous) == 1


def _family(regime: str) -> str:
    return REGIME_FAMILY[str(regime)]


def _supported_classification_metrics(
    actual: pd.Series,
    predicted: pd.Series,
    labels: Iterable[str],
) -> dict[str, float]:
    frame = pd.DataFrame({"actual": actual.astype(str), "predicted": predicted.astype(str)}).dropna()
    if frame.empty:
        return {
            "accuracy": float("nan"),
            "balanced_accuracy": float("nan"),
            "macro_f1": float("nan"),
        }
    accuracy = float((frame["actual"] == frame["predicted"]).mean())
    recalls: list[float] = []
    f1_values: list[float] = []
    for label in labels:
        actual_mask = frame["actual"] == label
        predicted_mask = frame["predicted"] == label
        support = int(actual_mask.sum())
        forecast_count = int(predicted_mask.sum())
        true_positive = int((actual_mask & predicted_mask).sum())
        if support:
            recalls.append(true_positive / support)
        if support or forecast_count:
            precision = true_positive / forecast_count if forecast_count else 0.0
            recall = true_positive / support if support else 0.0
            f1_values.append(
                2.0 * precision * recall / (precision + recall)
                if precision + recall
                else 0.0
            )
    return {
        "accuracy": accuracy,
        "balanced_accuracy": float(np.mean(recalls)) if recalls else 0.0,
        "macro_f1": float(np.mean(f1_values)) if f1_values else 0.0,
    }


def _transition_metrics(frame: pd.DataFrame) -> dict[str, float]:
    ordered = frame.sort_values("state_date").copy()
    actual_transition: list[bool] = [False]
    predicted_transition: list[bool] = [False]
    valid_transition: list[bool] = [False]
    for previous, current in zip(ordered.iloc[:-1].itertuples(), ordered.iloc[1:].itertuples()):
        contiguous = _contiguous(previous.state_date, current.state_date)
        valid = contiguous and pd.notna(previous.prediction) and pd.notna(current.prediction)
        valid_transition.append(valid)
        actual_transition.append(
            bool(contiguous and str(previous.actual_regime) != str(current.actual_regime))
        )
        predicted_transition.append(
            bool(valid and str(previous.prediction) != str(current.prediction))
        )
    ordered["actual_transition"] = actual_transition
    ordered["predicted_transition"] = predicted_transition
    ordered["valid_transition"] = valid_transition
    valid = ordered.loc[ordered["valid_transition"]]
    if valid.empty:
        return {
            "transition_precision": 0.0,
            "transition_recall": 0.0,
            "transition_f1": 0.0,
            "false_transition_rate": 0.0,
        }
    actual = valid["actual_transition"].astype(bool)
    predicted = valid["predicted_transition"].astype(bool)
    true_positive = int((actual & predicted).sum())
    predicted_count = int(predicted.sum())
    actual_count = int(actual.sum())
    false_positive = int((~actual & predicted).sum())
    stable_count = int((~actual).sum())
    precision = true_positive / predicted_count if predicted_count else 0.0
    recall = true_positive / actual_count if actual_count else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "transition_precision": precision,
        "transition_recall": recall,
        "transition_f1": f1,
        "false_transition_rate": false_positive / stable_count if stable_count else 0.0,
    }


def forecast_sign_rule(growth: float, inflation: float, labour: float, deadzone: float) -> str:
    g, i, l = float(growth), float(inflation), float(labour)
    gp = g > deadzone
    gn = g < -deadzone
    ip = i > deadzone
    inn = i < -deadzone
    lp = l > deadzone
    ln = l < -deadzone
    if gn and ip:
        return "stagflation_risk"
    if gn and ln:
        return "hard_landing_risk"
    if gp and ip and lp:
        return "overheating"
    if gp and inn and not ln:
        return "disinflationary_expansion"
    if not (gp or gn or ip or inn or lp or ln):
        return "balanced_expansion"
    if gp and ip:
        return "reflation"
    if gn or ln:
        return "demand_slowdown"
    return "mixed_transition"


def _perturbations(epsilon: float) -> tuple[tuple[float, float, float], ...]:
    values = (-float(epsilon), 0.0, float(epsilon))
    return tuple(product(values, repeat=3))


def _directions() -> tuple[tuple[int, int, int], ...]:
    return tuple(item for item in product((-1, 0, 1), repeat=3) if item != (0, 0, 0))


def _boundary_distance(
    scores: tuple[float, float, float],
    thresholds: dict[str, Any],
    *,
    step: float,
    maximum: float,
    family_only: bool,
) -> float:
    base = classify_regime_with_thresholds(*scores, thresholds)
    base_label = _family(base) if family_only else base
    radius = step
    while radius <= maximum + 1e-12:
        for direction in _directions():
            perturbed = tuple(
                float(np.clip(value + radius * sign, -2.0, 2.0))
                for value, sign in zip(scores, direction)
            )
            regime = classify_regime_with_thresholds(*perturbed, thresholds)
            label = _family(regime) if family_only else regime
            if label != base_label:
                return float(radius)
        radius += step
    return float(maximum + step)


def label_stability_audit(
    monthly: pd.DataFrame,
    thresholds: dict[str, Any],
    config: dict[str, Any],
) -> pd.DataFrame:
    plan = audit_plan(config)
    section = config["target_validity_audit"]
    step = float(section["boundary_search_step"])
    maximum = float(section["boundary_search_maximum"])
    threshold_map = config["tournament"]["threshold_candidates"]
    rows: list[dict[str, Any]] = []
    for row in monthly.sort_values("state_date").itertuples(index=False):
        scores = (
            float(row.actual_growth),
            float(row.actual_inflation),
            float(row.actual_labour),
        )
        base_regime = classify_regime_with_thresholds(*scores, thresholds)
        record: dict[str, Any] = {
            "state_date": pd.Timestamp(row.state_date).date(),
            "actual_growth": scores[0],
            "actual_inflation": scores[1],
            "actual_labour": scores[2],
            "base_regime": base_regime,
            "base_family": _family(base_regime),
            "regime_boundary_distance_linf": _boundary_distance(
                scores, thresholds, step=step, maximum=maximum, family_only=False
            ),
            "family_boundary_distance_linf": _boundary_distance(
                scores, thresholds, step=step, maximum=maximum, family_only=True
            ),
        }
        for epsilon in plan.perturbation_epsilons:
            regimes = [
                classify_regime_with_thresholds(
                    float(np.clip(scores[0] + dg, -2.0, 2.0)),
                    float(np.clip(scores[1] + di, -2.0, 2.0)),
                    float(np.clip(scores[2] + dl, -2.0, 2.0)),
                    thresholds,
                )
                for dg, di, dl in _perturbations(epsilon)
            ]
            families = [_family(regime) for regime in regimes]
            suffix = str(epsilon).replace(".", "p")
            record[f"regime_agreement_e{suffix}"] = float(
                np.mean([regime == base_regime for regime in regimes])
            )
            record[f"regime_distinct_e{suffix}"] = int(len(set(regimes)))
            record[f"regime_robust_e{suffix}"] = bool(len(set(regimes)) == 1)
            record[f"family_agreement_e{suffix}"] = float(
                np.mean([family == _family(base_regime) for family in families])
            )
            record[f"family_distinct_e{suffix}"] = int(len(set(families)))
            record[f"family_robust_e{suffix}"] = bool(len(set(families)) == 1)
        threshold_labels = {
            threshold_id: classify_regime_with_thresholds(
                *scores, threshold_map[threshold_id]
            )
            for threshold_id in plan.threshold_ids
        }
        record["threshold_distinct_regimes"] = int(len(set(threshold_labels.values())))
        record["threshold_consensus"] = bool(len(set(threshold_labels.values())) == 1)
        record["threshold_base_agreement_share"] = float(
            np.mean([label == base_regime for label in threshold_labels.values()])
        )
        for threshold_id, label in threshold_labels.items():
            record[f"regime_{threshold_id}"] = label
            record[f"family_{threshold_id}"] = _family(label)
        rows.append(record)
    return pd.DataFrame(rows)


def threshold_sensitivity_summary(
    stability: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    plan = audit_plan(config)
    rows: list[dict[str, Any]] = []
    for left_index, left in enumerate(plan.threshold_ids):
        for right in plan.threshold_ids[left_index + 1 :]:
            rows.append(
                {
                    "comparison_type": "pairwise_agreement",
                    "left_threshold": left,
                    "right_threshold": right,
                    "months": int(len(stability)),
                    "regime_agreement": float(
                        (stability[f"regime_{left}"] == stability[f"regime_{right}"]).mean()
                    ),
                    "family_agreement": float(
                        (stability[f"family_{left}"] == stability[f"family_{right}"]).mean()
                    ),
                    "label": None,
                    "count": None,
                    "share": None,
                }
            )
    for threshold_id in plan.threshold_ids:
        counts = stability[f"regime_{threshold_id}"].value_counts()
        for regime in REGIMES:
            count = int(counts.get(regime, 0))
            rows.append(
                {
                    "comparison_type": "occupancy",
                    "left_threshold": threshold_id,
                    "right_threshold": None,
                    "months": int(len(stability)),
                    "regime_agreement": None,
                    "family_agreement": None,
                    "label": regime,
                    "count": count,
                    "share": count / len(stability) if len(stability) else 0.0,
                }
            )
    return pd.DataFrame(rows)


def _run_lengths(frame: pd.DataFrame, label_column: str) -> list[int]:
    ordered = frame.sort_values("state_date")
    lengths: list[int] = []
    current = 0
    previous_date: Any = None
    previous_label: str | None = None
    for row in ordered.itertuples(index=False):
        state_date = getattr(row, "state_date")
        label = str(getattr(row, label_column))
        if previous_date is None or not _contiguous(previous_date, state_date) or label != previous_label:
            if current:
                lengths.append(current)
            current = 1
        else:
            current += 1
        previous_date = state_date
        previous_label = label
    if current:
        lengths.append(current)
    return lengths


def occupancy_audit(monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for level, column, labels in (
        ("eight_state", "actual_regime", REGIMES),
        ("five_family", "actual_family", FAMILIES),
    ):
        counts = monthly[column].astype(str).value_counts()
        for label in labels:
            subset = monthly.loc[monthly[column].astype(str) == label]
            lengths = _run_lengths(subset, column) if not subset.empty else []
            rows.append(
                {
                    "target_level": level,
                    "label": label,
                    "count": int(counts.get(label, 0)),
                    "share": float(counts.get(label, 0) / len(monthly)) if len(monthly) else 0.0,
                    "median_run_months": float(np.median(lengths)) if lengths else 0.0,
                    "maximum_run_months": int(max(lengths)) if lengths else 0,
                }
            )
    return pd.DataFrame(rows)


def _target_period_end(target: str, target_period: Any) -> date | None:
    try:
        frequency = "Q" if str(target) == "GDPC1" else "M"
        return pd.Period(str(target_period), freq=frequency).end_time.date()
    except Exception:
        return None


def lineage_audit(inputs: pd.DataFrame) -> pd.DataFrame:
    frame = inputs.copy()
    for column in (
        "state_date",
        "information_cutoff",
        "data_as_of",
        "max_observation_date",
        "actual_release_date",
    ):
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.date
    if "target_leakage" not in frame.columns:
        frame["target_leakage"] = False
    frame["target_period_end"] = [
        _target_period_end(target, period)
        for target, period in zip(frame["source_target"], frame["target_period"])
    ]
    rows: list[dict[str, Any]] = []
    for target, subset in frame.groupby("source_target", sort=True):
        rows.append(
            {
                "source_target": str(target),
                "rows": int(len(subset)),
                "states": int(subset["state_date"].nunique()),
                "information_cutoff_after_state": int(
                    sum(
                        pd.notna(cutoff) and pd.notna(state) and cutoff > state
                        for cutoff, state in zip(subset["information_cutoff"], subset["state_date"])
                    )
                ),
                "data_as_of_after_state": int(
                    sum(
                        pd.notna(value) and pd.notna(state) and value > state
                        for value, state in zip(subset.get("data_as_of", pd.Series([None] * len(subset))), subset["state_date"])
                    )
                ),
                "max_observation_after_cutoff": int(
                    sum(
                        pd.notna(value) and pd.notna(cutoff) and value > cutoff
                        for value, cutoff in zip(
                            subset.get("max_observation_date", pd.Series([None] * len(subset))),
                            subset["information_cutoff"],
                        )
                    )
                ),
                "target_leakage_rows": int(subset["target_leakage"].fillna(False).astype(bool).sum()),
                "future_target_period_rows": int(
                    sum(
                        pd.notna(end) and pd.notna(state) and end > state
                        for end, state in zip(subset["target_period_end"], subset["state_date"])
                    )
                ),
                "missing_actual_release_date_rows": int(
                    subset.get("actual_release_date", pd.Series([None] * len(subset))).isna().sum()
                ),
                "actual_revision_vintage_recorded": False,
                "evaluation_target_mode": "ex_post_backtest_actual",
            }
        )
    return pd.DataFrame(rows)


def _mode(values: pd.Series, fallback: str) -> str:
    modes = values.dropna().astype(str).mode().sort_values()
    return str(modes.iloc[0]) if not modes.empty else fallback


def _markov_prediction(training: pd.DataFrame, previous_actual: str, fallback: str) -> str:
    ordered = training.sort_values("state_date")
    counts: dict[tuple[str, str], int] = {}
    for previous, current in zip(ordered.iloc[:-1].itertuples(), ordered.iloc[1:].itertuples()):
        if not _contiguous(previous.state_date, current.state_date):
            continue
        key = (str(previous.actual_regime), str(current.actual_regime))
        counts[key] = counts.get(key, 0) + 1
    outgoing = {to: count for (source, to), count in counts.items() if source == previous_actual}
    if not outgoing:
        return fallback
    return sorted(outgoing.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _benchmark_predictions(
    monthly: pd.DataFrame,
    fold: RollingFold,
    config: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    section = config["target_validity_audit"]
    rolling_window = int(section["rolling_mode_months"])
    deadzone = float(section["forecast_sign_deadzone"])
    ordered = monthly.sort_values("state_date").copy()
    training = ordered.loc[ordered["state_date"].isin(set(fold.training_dates))]
    evaluation = ordered.loc[ordered["state_date"].isin(set(fold.evaluation_dates))].copy()
    fallback = _mode(training["actual_regime"], "mixed_transition")
    outputs: dict[str, pd.DataFrame] = {}
    for benchmark_id in BENCHMARK_IDS:
        predictions: list[str | None] = []
        for row in evaluation.itertuples(index=False):
            prior = ordered.loc[ordered["state_date"] < row.state_date].copy()
            previous = prior.iloc[-1] if not prior.empty and _contiguous(prior.iloc[-1]["state_date"], row.state_date) else None
            if benchmark_id == "source_direct":
                prediction = str(row.forecast_regime)
            elif benchmark_id == "persistence":
                prediction = str(previous["actual_regime"]) if previous is not None else None
            elif benchmark_id == "training_mode":
                prediction = fallback
            elif benchmark_id == "rolling_mode":
                prediction = _mode(prior.tail(rolling_window)["actual_regime"], fallback)
            elif benchmark_id == "markov_first_order":
                prediction = (
                    _markov_prediction(training, str(previous["actual_regime"]), fallback)
                    if previous is not None
                    else fallback
                )
            else:
                prediction = forecast_sign_rule(
                    row.forecast_growth,
                    row.forecast_inflation,
                    row.forecast_labour,
                    deadzone,
                )
            predictions.append(prediction)
        frame = evaluation[["state_date", "actual_regime", "actual_family"]].copy()
        frame["prediction"] = predictions
        frame["prediction_family"] = frame["prediction"].map(
            lambda value: _family(str(value)) if pd.notna(value) else None
        )
        outputs[benchmark_id] = frame
    return outputs


def benchmark_metrics(
    monthly: pd.DataFrame,
    plan: RollingTournamentPlan,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    fold_rows: list[dict[str, Any]] = []
    for fold in plan.folds:
        predictions = _benchmark_predictions(monthly, fold, config)
        preliminary: dict[str, dict[str, Any]] = {}
        for benchmark_id, frame in predictions.items():
            valid = frame.dropna(subset=["prediction"])
            regime_metrics = _supported_classification_metrics(
                valid["actual_regime"], valid["prediction"], REGIMES
            )
            family_metrics = _supported_classification_metrics(
                valid["actual_family"], valid["prediction_family"], FAMILIES
            )
            transition = _transition_metrics(valid)
            preliminary[benchmark_id] = {
                "fold_id": fold.fold_id,
                "evaluation_start": fold.evaluation_dates[0],
                "evaluation_end": fold.evaluation_dates[-1],
                "benchmark_id": benchmark_id,
                "months": int(len(valid)),
                "exact_regime_accuracy": regime_metrics["accuracy"],
                "balanced_accuracy": regime_metrics["balanced_accuracy"],
                "macro_f1": regime_metrics["macro_f1"],
                "family_accuracy": family_metrics["accuracy"],
                "family_balanced_accuracy": family_metrics["balanced_accuracy"],
                "family_macro_f1": family_metrics["macro_f1"],
                **transition,
            }
        naive_accuracy = max(
            preliminary["persistence"]["exact_regime_accuracy"],
            preliminary["training_mode"]["exact_regime_accuracy"],
        )
        strongest = (
            "persistence"
            if preliminary["persistence"]["exact_regime_accuracy"]
            >= preliminary["training_mode"]["exact_regime_accuracy"]
            else "training_mode"
        )
        for values in preliminary.values():
            values["strongest_naive_benchmark"] = strongest
            values["strongest_naive_accuracy"] = naive_accuracy
            values["baseline_margin"] = values["exact_regime_accuracy"] - naive_accuracy
            fold_rows.append(values)
    fold_metrics = pd.DataFrame(fold_rows)
    summary_rows: list[dict[str, Any]] = []
    for benchmark_id, subset in fold_metrics.groupby("benchmark_id", sort=True):
        summary_rows.append(
            {
                "benchmark_id": benchmark_id,
                "folds": int(len(subset)),
                "mean_exact_regime_accuracy": float(subset["exact_regime_accuracy"].mean()),
                "mean_balanced_accuracy": float(subset["balanced_accuracy"].mean()),
                "mean_macro_f1": float(subset["macro_f1"].mean()),
                "mean_family_accuracy": float(subset["family_accuracy"].mean()),
                "mean_family_macro_f1": float(subset["family_macro_f1"].mean()),
                "mean_transition_recall": float(subset["transition_recall"].mean()),
                "mean_false_transition_rate": float(subset["false_transition_rate"].mean()),
                "mean_baseline_margin": float(subset["baseline_margin"].mean()),
                "baseline_win_rate": float((subset["baseline_margin"] > 0).mean()),
                "baseline_nonloss_rate": float((subset["baseline_margin"] >= 0).mean()),
            }
        )
    summary = pd.DataFrame(summary_rows).sort_values(
        ["mean_macro_f1", "mean_exact_regime_accuracy"], ascending=False
    ).reset_index(drop=True)

    audit_fold = RollingFold(
        fold_id="consumed_audit",
        training_dates=plan.selection_dates,
        evaluation_dates=plan.audit_dates,
    )
    audit_predictions = _benchmark_predictions(monthly, audit_fold, config)
    audit_rows: list[dict[str, Any]] = []
    naive_values: dict[str, float] = {}
    raw_rows: dict[str, dict[str, Any]] = {}
    for benchmark_id, frame in audit_predictions.items():
        valid = frame.dropna(subset=["prediction"])
        regime_metrics = _supported_classification_metrics(
            valid["actual_regime"], valid["prediction"], REGIMES
        )
        family_metrics = _supported_classification_metrics(
            valid["actual_family"], valid["prediction_family"], FAMILIES
        )
        raw_rows[benchmark_id] = {
            "benchmark_id": benchmark_id,
            "months": int(len(valid)),
            "exact_regime_accuracy": regime_metrics["accuracy"],
            "balanced_accuracy": regime_metrics["balanced_accuracy"],
            "macro_f1": regime_metrics["macro_f1"],
            "family_accuracy": family_metrics["accuracy"],
            "family_macro_f1": family_metrics["macro_f1"],
            **_transition_metrics(valid),
        }
        if benchmark_id in {"persistence", "training_mode"}:
            naive_values[benchmark_id] = regime_metrics["accuracy"]
    strongest_name = max(naive_values, key=naive_values.get)
    strongest_accuracy = naive_values[strongest_name]
    for values in raw_rows.values():
        values["strongest_naive_benchmark"] = strongest_name
        values["strongest_naive_accuracy"] = strongest_accuracy
        values["baseline_margin"] = values["exact_regime_accuracy"] - strongest_accuracy
        audit_rows.append(values)
    audit = pd.DataFrame(audit_rows).sort_values(
        ["macro_f1", "exact_regime_accuracy"], ascending=False
    ).reset_index(drop=True)
    audit["audit_rank"] = np.arange(1, len(audit) + 1)
    return fold_metrics, summary, audit


def _eta_squared(values: pd.Series, groups: pd.Series) -> float:
    frame = pd.DataFrame({"value": pd.to_numeric(values, errors="coerce"), "group": groups.astype(str)}).dropna()
    if len(frame) < 3 or frame["group"].nunique() < 2:
        return 0.0
    grand_mean = float(frame["value"].mean())
    total = float(((frame["value"] - grand_mean) ** 2).sum())
    if total <= 1e-12:
        return 0.0
    between = 0.0
    for _, subset in frame.groupby("group"):
        between += len(subset) * (float(subset["value"].mean()) - grand_mean) ** 2
    return float(between / total)


def economic_separation_audit(
    monthly: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    plan = audit_plan(config)
    ordered = monthly.sort_values("state_date").copy()
    rows: list[dict[str, Any]] = []
    ordinals = pd.PeriodIndex(ordered["state_date"], freq="M").asi8
    for horizon in plan.economic_horizons:
        future_ordinals = pd.Series(ordinals, index=ordered.index).shift(-horizon)
        horizon_valid = (future_ordinals - pd.Series(ordinals, index=ordered.index)) == horizon
        for dimension in DIMENSIONS:
            current = pd.to_numeric(ordered[f"actual_{dimension}"], errors="coerce")
            future = current.shift(-horizon).where(horizon_valid)
            change = (future - current).where(horizon_valid)
            for target_level, group_column in (
                ("eight_state", "actual_regime"),
                ("five_family", "actual_family"),
            ):
                for outcome_type, values in (
                    ("future_level", future),
                    ("forward_change", change),
                ):
                    valid = pd.DataFrame(
                        {"value": values, "group": ordered[group_column]}
                    ).dropna()
                    support = valid["group"].astype(str).value_counts()
                    rows.append(
                        {
                            "horizon_months": horizon,
                            "dimension": dimension,
                            "target_level": target_level,
                            "outcome_type": outcome_type,
                            "observations": int(len(valid)),
                            "groups_observed": int(valid["group"].nunique()),
                            "minimum_group_support": int(support.min()) if not support.empty else 0,
                            "maximum_group_share": float(support.max() / len(valid)) if len(valid) else 0.0,
                            "eta_squared": _eta_squared(valid["value"], valid["group"]),
                        }
                    )
    return pd.DataFrame(rows)


def validity_flags(
    *,
    lineage: pd.DataFrame,
    stability: pd.DataFrame,
    occupancy: pd.DataFrame,
    benchmark_summary: pd.DataFrame,
    economic: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    section = config["target_validity_audit"]["validity_thresholds"]
    epsilon = float(section["reference_perturbation_epsilon"])
    suffix = str(epsilon).replace(".", "p")
    regime_robust_share = float(stability[f"regime_robust_e{suffix}"].mean())
    family_robust_share = float(stability[f"family_robust_e{suffix}"].mean())
    threshold_consensus = float(stability["threshold_consensus"].mean())
    regime_occupancy = occupancy.loc[occupancy["target_level"] == "eight_state"]
    minimum_support = int(regime_occupancy["count"].min())
    maximum_share = float(regime_occupancy["share"].max())
    source = benchmark_summary.loc[
        benchmark_summary["benchmark_id"] == "source_direct"
    ].iloc[0]
    economic_subset = economic.loc[
        (economic["horizon_months"] == int(section["reference_economic_horizon_months"]))
        & (economic["outcome_type"] == "future_level")
    ]
    eight_eta = float(
        economic_subset.loc[economic_subset["target_level"] == "eight_state", "eta_squared"].mean()
    )
    family_eta = float(
        economic_subset.loc[economic_subset["target_level"] == "five_family", "eta_squared"].mean()
    )
    no_lookahead = bool(
        lineage[[
            "information_cutoff_after_state",
            "data_as_of_after_state",
            "max_observation_after_cutoff",
            "target_leakage_rows",
        ]].fillna(0).to_numpy().sum()
        == 0
    )
    actual_vintage = bool(lineage["actual_revision_vintage_recorded"].all())
    checks = [
        (
            "forecast_lineage_no_lookahead",
            no_lookahead,
            1.0 if no_lookahead else 0.0,
            1.0,
            "Forecast inputs must respect historical information cutoffs.",
        ),
        (
            "actual_revision_vintage_recorded",
            actual_vintage,
            1.0 if actual_vintage else 0.0,
            1.0,
            "Evaluation actuals require an explicit real-time revision vintage for a real-time target claim.",
        ),
        (
            "regime_perturbation_robustness",
            regime_robust_share >= float(section["minimum_regime_robust_share"]),
            regime_robust_share,
            float(section["minimum_regime_robust_share"]),
            f"Eight-state labels should remain unchanged under ±{epsilon:.2f} score perturbations.",
        ),
        (
            "family_perturbation_robustness",
            family_robust_share >= float(section["minimum_family_robust_share"]),
            family_robust_share,
            float(section["minimum_family_robust_share"]),
            f"Family labels should remain unchanged under ±{epsilon:.2f} score perturbations.",
        ),
        (
            "threshold_consensus",
            threshold_consensus >= float(section["minimum_threshold_consensus_share"]),
            threshold_consensus,
            float(section["minimum_threshold_consensus_share"]),
            "Realised labels should be stable across the pre-specified threshold sets.",
        ),
        (
            "minimum_regime_support",
            minimum_support >= int(section["minimum_regime_support"]),
            float(minimum_support),
            float(section["minimum_regime_support"]),
            "Every eight-state label should have enough observations for meaningful validation.",
        ),
        (
            "maximum_regime_share",
            maximum_share <= float(section["maximum_regime_share"]),
            maximum_share,
            float(section["maximum_regime_share"]),
            "No single regime should dominate the realised target.",
        ),
        (
            "source_beats_naive_baseline",
            float(source["baseline_win_rate"]) >= float(section["minimum_source_baseline_win_rate"]),
            float(source["baseline_win_rate"]),
            float(section["minimum_source_baseline_win_rate"]),
            "The source classifier should beat the strongest naive benchmark in most rolling folds.",
        ),
        (
            "family_forward_separation",
            family_eta >= float(section["minimum_family_eta_squared"]),
            family_eta,
            float(section["minimum_family_eta_squared"]),
            "Regime families should separate subsequent macro outcomes.",
        ),
        (
            "eight_state_incremental_separation",
            (eight_eta - family_eta) >= float(section["minimum_incremental_eight_state_eta_squared"]),
            eight_eta - family_eta,
            float(section["minimum_incremental_eight_state_eta_squared"]),
            "Eight-state subtyping should add economic separation beyond the five-family target.",
        ),
    ]
    return pd.DataFrame(
        [
            {
                "check_id": check_id,
                "passed": passed,
                "observed": observed,
                "threshold": threshold,
                "interpretation": interpretation,
            }
            for check_id, passed, observed, threshold, interpretation in checks
        ]
    )


def run_target_validity_audit(
    monthly: pd.DataFrame,
    plan: RollingTournamentPlan,
    core_candidate: dict[str, Any],
    lineage_inputs: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, Any]:
    thresholds = core_candidate["thresholds"]
    stability = label_stability_audit(monthly, thresholds, config)
    threshold_summary = threshold_sensitivity_summary(stability, config)
    occupancy = occupancy_audit(monthly)
    lineage = lineage_audit(lineage_inputs)
    fold_metrics, benchmark_summary, audit_benchmarks = benchmark_metrics(
        monthly, plan, config
    )
    economic = economic_separation_audit(monthly, config)
    flags = validity_flags(
        lineage=lineage,
        stability=stability,
        occupancy=occupancy,
        benchmark_summary=benchmark_summary,
        economic=economic,
        config=config,
    )
    return {
        "lineage": lineage,
        "label_stability": stability,
        "threshold_sensitivity": threshold_summary,
        "occupancy": occupancy,
        "benchmark_fold_metrics": fold_metrics,
        "benchmark_summary": benchmark_summary,
        "audit_benchmarks": audit_benchmarks,
        "economic_separation": economic,
        "validity_flags": flags,
        "target_validity_pass": bool(flags["passed"].all()),
    }
