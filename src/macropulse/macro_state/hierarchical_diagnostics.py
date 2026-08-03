from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from itertools import product
from typing import Any, Iterable

import numpy as np
import pandas as pd

from macropulse.macro_state.rolling_tournament import (
    RollingFold,
    RollingTournamentPlan,
    block_bootstrap_margin_ci,
    candidate_fold_baseline,
)
from macropulse.macro_state.temporal_diagnostics import (
    source_candidate_monthly,
    temporal_plan,
    transition_events,
)
from macropulse.macro_state.tournament import (
    REGIMES,
    REGIME_FAMILY,
    classify_regime_with_thresholds,
)

DIMENSIONS = ("growth", "inflation", "labour")
FAMILIES = (
    "contraction",
    "adverse_supply",
    "inflationary_expansion",
    "benign_expansion",
    "mixed",
)
CALIBRATION_METHODS = (
    "none",
    "expanding_bias",
    "expanding_affine_shrinkage",
)
ARCHITECTURES = (
    "direct_eight_state",
    "family_first",
    "family_first_interval_abstain",
)


@dataclass(frozen=True)
class DimensionCalibration:
    dimension: str
    method: str
    alpha: float
    beta: float
    training_months: int
    pre_bias: float
    post_bias: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "method": self.method,
            "alpha": self.alpha,
            "beta": self.beta,
            "training_months": self.training_months,
            "pre_bias": self.pre_bias,
            "post_bias": self.post_bias,
        }


def build_hierarchical_candidates(config: dict[str, Any]) -> list[dict[str, str]]:
    section = config["hierarchical_diagnostics"]
    calibrations = tuple(section["calibration_methods"])
    architectures = tuple(section["architectures"])
    unknown_calibrations = set(calibrations) - set(CALIBRATION_METHODS)
    unknown_architectures = set(architectures) - set(ARCHITECTURES)
    if unknown_calibrations:
        raise ValueError(
            f"Unknown dimension calibration methods: {sorted(unknown_calibrations)}"
        )
    if unknown_architectures:
        raise ValueError(
            f"Unknown hierarchical architectures: {sorted(unknown_architectures)}"
        )
    return [
        {
            "candidate_id": f"{calibration}__{architecture}",
            "calibration_method": calibration,
            "architecture_id": architecture,
        }
        for calibration, architecture in product(calibrations, architectures)
    ]


def _fit_affine(
    forecast: np.ndarray,
    actual: np.ndarray,
    *,
    ridge_strength: float,
    beta_bounds: tuple[float, float],
    alpha_bound: float,
) -> tuple[float, float]:
    x = np.asarray(forecast, dtype=float)
    y = np.asarray(actual, dtype=float)
    x_mean = float(x.mean())
    y_mean = float(y.mean())
    centered_x = x - x_mean
    variance = float(np.dot(centered_x, centered_x))
    covariance = float(np.dot(centered_x, y - y_mean))
    ols_beta = covariance / variance if variance > 1e-12 else 1.0
    shrinkage_weight = len(x) / (len(x) + float(ridge_strength))
    beta = 1.0 + shrinkage_weight * (ols_beta - 1.0)
    beta = float(np.clip(beta, beta_bounds[0], beta_bounds[1]))
    alpha = float(np.clip(y_mean - beta * x_mean, -alpha_bound, alpha_bound))
    return alpha, beta


def fit_dimension_calibration(
    training: pd.DataFrame,
    method: str,
    config: dict[str, Any],
) -> dict[str, DimensionCalibration]:
    if method not in CALIBRATION_METHODS:
        raise ValueError(f"Unsupported calibration method: {method}")
    section = config["hierarchical_diagnostics"]["calibration"]
    minimum_history = int(section["minimum_history"])
    ridge_strength = float(section["affine_ridge_strength"])
    beta_bounds = tuple(float(item) for item in section["affine_beta_bounds"])
    alpha_bound = float(section["affine_alpha_bound"])
    calibrations: dict[str, DimensionCalibration] = {}

    for dimension in DIMENSIONS:
        frame = training[[f"forecast_{dimension}", f"actual_{dimension}"]].dropna()
        forecast = frame[f"forecast_{dimension}"].to_numpy(dtype=float)
        actual = frame[f"actual_{dimension}"].to_numpy(dtype=float)
        if not len(frame):
            raise RuntimeError(f"No calibration observations for {dimension}.")
        pre_bias = float(np.mean(forecast - actual))
        resolved_method = method if len(frame) >= minimum_history else "none"
        if resolved_method == "none":
            alpha, beta = 0.0, 1.0
        elif resolved_method == "expanding_bias":
            alpha, beta = -pre_bias, 1.0
        else:
            alpha, beta = _fit_affine(
                forecast,
                actual,
                ridge_strength=ridge_strength,
                beta_bounds=(beta_bounds[0], beta_bounds[1]),
                alpha_bound=alpha_bound,
            )
        calibrated = alpha + beta * forecast
        post_bias = float(np.mean(calibrated - actual))
        calibrations[dimension] = DimensionCalibration(
            dimension=dimension,
            method=resolved_method,
            alpha=alpha,
            beta=beta,
            training_months=int(len(frame)),
            pre_bias=pre_bias,
            post_bias=post_bias,
        )
    return calibrations


def apply_dimension_calibration(
    frame: pd.DataFrame,
    calibrations: dict[str, DimensionCalibration],
) -> pd.DataFrame:
    output = frame.copy()
    for dimension in DIMENSIONS:
        calibration = calibrations[dimension]
        for column in (
            f"forecast_{dimension}",
            f"{dimension}_lower",
            f"{dimension}_upper",
        ):
            output[column] = (
                calibration.alpha
                + calibration.beta * pd.to_numeric(output[column], errors="coerce")
            ).clip(-2.0, 2.0)
        lower = output[[f"{dimension}_lower", f"{dimension}_upper"]].min(axis=1)
        upper = output[[f"{dimension}_lower", f"{dimension}_upper"]].max(axis=1)
        output[f"{dimension}_lower"] = lower
        output[f"{dimension}_upper"] = upper
        output[f"{dimension}_calibration_alpha"] = calibration.alpha
        output[f"{dimension}_calibration_beta"] = calibration.beta
    return output


def classify_family(
    growth: float,
    inflation: float,
    labour: float,
    config: dict[str, Any],
) -> str:
    family = config["hierarchical_diagnostics"]["family_thresholds"]
    g, i, l = float(growth), float(inflation), float(labour)
    if g <= float(family["contraction_growth_max"]):
        if i >= float(family["adverse_supply_inflation_min"]):
            return "adverse_supply"
        return "contraction"
    if g >= float(family["expansion_growth_min"]):
        if i >= float(family["inflationary_expansion_inflation_min"]):
            return "inflationary_expansion"
        if (
            i <= float(family["benign_expansion_inflation_max"])
            and l >= float(family["benign_expansion_labour_min"])
        ):
            return "benign_expansion"
        return "mixed"
    if (
        i >= float(family["ambiguous_adverse_inflation_min"])
        and l <= float(family["ambiguous_adverse_labour_max"])
    ):
        return "adverse_supply"
    if l <= float(family["ambiguous_contraction_labour_max"]):
        return "contraction"
    if (
        i >= float(family["ambiguous_inflationary_inflation_min"])
        and l >= float(family["ambiguous_inflationary_labour_min"])
    ):
        return "inflationary_expansion"
    if (
        i <= float(family["ambiguous_benign_inflation_max"])
        and l >= float(family["ambiguous_benign_labour_min"])
    ):
        return "benign_expansion"
    return "mixed"


def family_subtype(
    family: str,
    growth: float,
    inflation: float,
    labour: float,
    thresholds: dict[str, Any],
) -> str:
    g, i, l = float(growth), float(inflation), float(labour)
    if family == "contraction":
        if (
            g <= float(thresholds["hard_growth_max"])
            and l <= float(thresholds["hard_labour_max"])
        ):
            return "hard_landing_risk"
        return "demand_slowdown"
    if family == "adverse_supply":
        return "stagflation_risk"
    if family == "inflationary_expansion":
        if (
            g >= float(thresholds["overheat_growth_min"])
            and i >= float(thresholds["overheat_inflation_min"])
            and l >= float(thresholds["overheat_labour_min"])
        ):
            return "overheating"
        return "reflation"
    if family == "benign_expansion":
        if (
            g >= float(thresholds["disinflation_growth_min"])
            and i <= float(thresholds["disinflation_inflation_max"])
            and l >= float(thresholds["disinflation_labour_min"])
        ):
            return "disinflationary_expansion"
        return "balanced_expansion"
    return "mixed_transition"


def classify_hierarchical_regime(
    *,
    growth: float,
    inflation: float,
    labour: float,
    growth_lower: float,
    growth_upper: float,
    inflation_lower: float,
    inflation_upper: float,
    labour_lower: float,
    labour_upper: float,
    architecture_id: str,
    thresholds: dict[str, Any],
    config: dict[str, Any],
) -> tuple[str, str, bool, int]:
    if architecture_id == "direct_eight_state":
        regime = classify_regime_with_thresholds(
            growth, inflation, labour, thresholds
        )
        return regime, REGIME_FAMILY[regime], False, 1

    point_family = classify_family(growth, inflation, labour, config)
    possible_families = {point_family}
    if architecture_id == "family_first_interval_abstain":
        possible_families = {
            classify_family(g, i, l, config)
            for g, i, l in product(
                (growth_lower, growth_upper),
                (inflation_lower, inflation_upper),
                (labour_lower, labour_upper),
            )
        }
        if len(possible_families) != 1 or point_family == "mixed":
            return "mixed_transition", "mixed", True, len(possible_families)
    elif architecture_id != "family_first":
        raise ValueError(f"Unsupported hierarchy architecture: {architecture_id}")

    regime = family_subtype(
        point_family, growth, inflation, labour, thresholds
    )
    return regime, REGIME_FAMILY[regime], False, len(possible_families)


def build_candidate_frame(
    monthly: pd.DataFrame,
    *,
    training_dates: Iterable[date],
    evaluation_dates: Iterable[date],
    candidate: dict[str, str],
    thresholds: dict[str, Any],
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_set = {pd.Timestamp(item).date() for item in training_dates}
    eval_set = {pd.Timestamp(item).date() for item in evaluation_dates}
    training = monthly.loc[monthly["state_date"].isin(train_set)].copy()
    evaluation = monthly.loc[monthly["state_date"].isin(eval_set)].copy()
    calibrations = fit_dimension_calibration(
        training,
        candidate["calibration_method"],
        config,
    )
    calibrated = apply_dimension_calibration(evaluation, calibrations)
    rows: list[dict[str, Any]] = []
    for row in calibrated.itertuples(index=False):
        regime, family, abstained, possible_family_count = (
            classify_hierarchical_regime(
                growth=float(row.forecast_growth),
                inflation=float(row.forecast_inflation),
                labour=float(row.forecast_labour),
                growth_lower=float(row.growth_lower),
                growth_upper=float(row.growth_upper),
                inflation_lower=float(row.inflation_lower),
                inflation_upper=float(row.inflation_upper),
                labour_lower=float(row.labour_lower),
                labour_upper=float(row.labour_upper),
                architecture_id=candidate["architecture_id"],
                thresholds=thresholds,
                config=config,
            )
        )
        rows.append(
            {
                **row._asdict(),
                "candidate_id": candidate["candidate_id"],
                "calibration_method": candidate["calibration_method"],
                "architecture_id": candidate["architecture_id"],
                "decision_regime": regime,
                "decision_family": family,
                "abstained": abstained,
                "possible_family_count": possible_family_count,
            }
        )
    calibration_frame = pd.DataFrame(
        [item.as_dict() for item in calibrations.values()]
    )
    return pd.DataFrame(rows), calibration_frame


def _classification_metrics(
    actual: pd.Series,
    predicted: pd.Series,
    labels: Iterable[str],
) -> dict[str, float]:
    actual_values = actual.astype(str)
    predicted_values = predicted.astype(str)
    recalls: list[float] = []
    precisions: list[float] = []
    f1_values: list[float] = []
    for label in labels:
        actual_mask = actual_values == label
        support = int(actual_mask.sum())
        if not support:
            continue
        predicted_mask = predicted_values == label
        true_positive = int((actual_mask & predicted_mask).sum())
        recall = true_positive / support
        precision = (
            true_positive / int(predicted_mask.sum())
            if int(predicted_mask.sum())
            else 0.0
        )
        f1 = (
            2.0 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        recalls.append(recall)
        precisions.append(precision)
        f1_values.append(f1)
    return {
        "accuracy": float((actual_values == predicted_values).mean()),
        "balanced_accuracy": float(np.mean(recalls)) if recalls else 0.0,
        "macro_precision": float(np.mean(precisions)) if precisions else 0.0,
        "macro_recall": float(np.mean(recalls)) if recalls else 0.0,
        "macro_f1": float(np.mean(f1_values)) if f1_values else 0.0,
    }


def _transition_metrics(
    frame: pd.DataFrame,
    dates: Iterable[date],
    matching_window_months: int,
) -> dict[str, float]:
    temporal = frame.copy()
    temporal["decision_regime"] = temporal["decision_regime"].astype(str)
    events = transition_events(temporal, dates, matching_window_months)
    if events.empty:
        return {
            "transition_precision": 0.0,
            "transition_recall": 0.0,
            "transition_f1": 0.0,
            "false_transition_rate": 0.0,
            "actual_transition_count": 0,
            "predicted_transition_count": 0,
        }
    actual_events = events.loc[events["event_type"] == "actual_transition"]
    matched = int(actual_events["matched"].sum()) if not actual_events.empty else 0
    false_count = int(
        (events["event_type"] == "false_predicted_transition").sum()
    )
    actual_count = int(len(actual_events))
    predicted_count = matched + false_count
    precision = matched / predicted_count if predicted_count else 0.0
    recall = matched / actual_count if actual_count else 0.0
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "transition_precision": float(precision),
        "transition_recall": float(recall),
        "transition_f1": float(f1),
        "false_transition_rate": (
            float(false_count / predicted_count) if predicted_count else 0.0
        ),
        "actual_transition_count": actual_count,
        "predicted_transition_count": predicted_count,
    }


def candidate_metrics(
    frame: pd.DataFrame,
    *,
    dates: Iterable[date],
    strongest_baseline_accuracy: float,
    config: dict[str, Any],
) -> dict[str, Any]:
    date_set = {pd.Timestamp(item).date() for item in dates}
    subset = frame.loc[frame["state_date"].isin(date_set)].copy()
    if subset.empty:
        raise RuntimeError("Hierarchical diagnostics split contains no rows.")
    exact = _classification_metrics(
        subset["actual_regime"], subset["decision_regime"], REGIMES
    )
    family = _classification_metrics(
        subset["actual_family"], subset["decision_family"], FAMILIES
    )
    errors = np.column_stack(
        [
            pd.to_numeric(subset[f"forecast_{dimension}"], errors="coerce")
            - pd.to_numeric(subset[f"actual_{dimension}"], errors="coerce")
            for dimension in DIMENSIONS
        ]
    )
    transition = _transition_metrics(
        frame,
        dates,
        int(
            config["hierarchical_diagnostics"][
                "transition_matching_window_months"
            ]
        ),
    )
    occupancy = subset["decision_regime"].value_counts(normalize=True)
    unique_regimes = int(subset["decision_regime"].nunique())
    maximum_share = float(occupancy.max())
    section = config["hierarchical_diagnostics"]
    collapse = bool(
        unique_regimes < int(section["minimum_regimes_per_fold"])
        or maximum_share > float(section["maximum_regime_share"])
    )
    return {
        "months": int(len(subset)),
        "dimension_rmse": float(np.sqrt(np.mean(np.square(errors)))),
        "growth_bias": float(subset["forecast_growth"].sub(subset["actual_growth"]).mean()),
        "inflation_bias": float(subset["forecast_inflation"].sub(subset["actual_inflation"]).mean()),
        "labour_bias": float(subset["forecast_labour"].sub(subset["actual_labour"]).mean()),
        "exact_regime_accuracy": exact["accuracy"],
        "balanced_accuracy": exact["balanced_accuracy"],
        "macro_precision": exact["macro_precision"],
        "macro_recall": exact["macro_recall"],
        "macro_f1": exact["macro_f1"],
        "family_accuracy": family["accuracy"],
        "family_balanced_accuracy": family["balanced_accuracy"],
        "family_macro_f1": family["macro_f1"],
        **transition,
        "strongest_baseline_accuracy": float(strongest_baseline_accuracy),
        "baseline_margin": exact["accuracy"] - float(strongest_baseline_accuracy),
        "beats_strongest_baseline": bool(
            exact["accuracy"] > float(strongest_baseline_accuracy)
        ),
        "abstention_rate": float(subset["abstained"].mean()),
        "unique_regimes": unique_regimes,
        "maximum_regime_share": maximum_share,
        "regime_collapse": collapse,
    }


def _percentile_rank(series: pd.Series, higher_is_better: bool) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    if values.isna().any():
        raise ValueError("Hierarchical ranking metrics cannot be missing.")
    return values.rank(method="average", pct=True, ascending=higher_is_better)


def rank_fold_candidates(
    metrics: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    weights = config["hierarchical_diagnostics"]["fold_score_weights"]
    directions = {
        "macro_f1": True,
        "balanced_accuracy": True,
        "family_macro_f1": True,
        "family_balanced_accuracy": True,
        "baseline_margin": True,
        "transition_recall": True,
        "false_transition_rate": False,
        "dimension_rmse": False,
    }
    frame = metrics.copy()
    score = pd.Series(0.0, index=frame.index)
    for metric, weight in weights.items():
        component = _percentile_rank(frame[metric], directions[metric])
        frame[f"rank_component_{metric}"] = component
        score += float(weight) * component
    frame["fold_score"] = 100.0 * score
    frame["fold_rank"] = frame["fold_score"].rank(
        method="min", ascending=False
    ).astype(int)
    return frame.sort_values(["fold_rank", "candidate_id"]).reset_index(drop=True)


def _bootstrap_differences(
    frame: pd.DataFrame,
    fold: RollingFold,
    strongest_baseline: str,
    training_mode_regime: str,
) -> np.ndarray:
    evaluation = frame.loc[
        frame["state_date"].isin(set(fold.evaluation_dates))
    ].sort_values("state_date").copy()
    candidate_hit = (
        evaluation["decision_regime"].astype(str)
        == evaluation["actual_regime"].astype(str)
    ).astype(float)
    if strongest_baseline == "training_mode":
        baseline_hit = (
            evaluation["actual_regime"].astype(str)
            == str(training_mode_regime)
        ).astype(float)
        return (candidate_hit - baseline_hit).to_numpy(dtype=float)
    ordered = frame.sort_values("state_date").copy()
    ordered["_ordinal"] = pd.PeriodIndex(ordered["state_date"], freq="M").asi8
    ordered["_previous_ordinal"] = ordered["_ordinal"].shift(1)
    ordered["persistence_prediction"] = ordered["actual_regime"].shift(1)
    ordered.loc[
        (ordered["_ordinal"] - ordered["_previous_ordinal"]) != 1,
        "persistence_prediction",
    ] = None
    evaluation = ordered.loc[
        ordered["state_date"].isin(set(fold.evaluation_dates))
    ].dropna(subset=["persistence_prediction"])
    candidate_hit = (
        evaluation["decision_regime"].astype(str)
        == evaluation["actual_regime"].astype(str)
    ).astype(float)
    baseline_hit = (
        evaluation["persistence_prediction"].astype(str)
        == evaluation["actual_regime"].astype(str)
    ).astype(float)
    return (candidate_hit - baseline_hit).to_numpy(dtype=float)


def aggregate_stability(
    fold_metrics: pd.DataFrame,
    candidate_frames: dict[tuple[str, str], pd.DataFrame],
    plan: RollingTournamentPlan,
    baseline_by_fold: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> pd.DataFrame:
    section = config["hierarchical_diagnostics"]
    total_candidates = int(fold_metrics["candidate_id"].nunique())
    leading_cutoff = max(1, math.ceil(total_candidates / 3.0))
    catastrophic_cutoff = max(1, math.ceil(total_candidates * 0.85))
    rows: list[dict[str, Any]] = []
    for candidate_id, group in fold_metrics.groupby("candidate_id"):
        group = group.sort_values("fold_id")
        differences = []
        for record in group.itertuples(index=False):
            fold = next(item for item in plan.folds if item.fold_id == record.fold_id)
            frame = candidate_frames[(candidate_id, record.fold_id)]
            differences.append(
                _bootstrap_differences(
                    frame,
                    fold,
                    str(baseline_by_fold[record.fold_id]["strongest_baseline"]),
                    str(baseline_by_fold[record.fold_id]["training_mode_regime"]),
                )
            )
        bootstrap = block_bootstrap_margin_ci(
            differences,
            repetitions=int(section["bootstrap_repetitions"]),
            block_months=int(section["bootstrap_block_months"]),
            confidence=float(section["bootstrap_confidence"]),
            seed=int(section["random_seed"]) + sum(ord(char) for char in candidate_id),
        )
        first = group.iloc[0]
        rows.append(
            {
                "candidate_id": candidate_id,
                "calibration_method": first["calibration_method"],
                "architecture_id": first["architecture_id"],
                "mean_fold_score": float(group["fold_score"].mean()),
                "median_fold_score": float(group["fold_score"].median()),
                "median_fold_rank": float(group["fold_rank"].median()),
                "rank_std": float(group["fold_rank"].std(ddof=0)),
                "worst_fold_rank": int(group["fold_rank"].max()),
                "leading_third_rate": float((group["fold_rank"] <= leading_cutoff).mean()),
                "catastrophic_fold_rate": float((group["fold_rank"] >= catastrophic_cutoff).mean()),
                "baseline_dominance_rate": float(group["beats_strongest_baseline"].mean()),
                "mean_macro_f1": float(group["macro_f1"].mean()),
                "mean_balanced_accuracy": float(group["balanced_accuracy"].mean()),
                "mean_family_macro_f1": float(group["family_macro_f1"].mean()),
                "mean_family_balanced_accuracy": float(group["family_balanced_accuracy"].mean()),
                "mean_transition_recall": float(group["transition_recall"].mean()),
                "mean_false_transition_rate": float(group["false_transition_rate"].mean()),
                "mean_abstention_rate": float(group["abstention_rate"].mean()),
                "regime_collapse_fold_rate": float(group["regime_collapse"].mean()),
                "mean_growth_abs_bias": float(group["growth_bias"].abs().mean()),
                "mean_labour_abs_bias": float(group["labour_bias"].abs().mean()),
                **bootstrap,
            }
        )
    aggregate = pd.DataFrame(rows)
    weights = section["stability_score_weights"]
    directions = {
        "mean_fold_score": True,
        "median_fold_score": True,
        "median_fold_rank": False,
        "rank_std": False,
        "leading_third_rate": True,
        "baseline_dominance_rate": True,
        "mean_macro_f1": True,
        "mean_family_macro_f1": True,
        "mean_transition_recall": True,
        "mean_false_transition_rate": False,
    }
    score = pd.Series(0.0, index=aggregate.index)
    for metric, weight in weights.items():
        component = _percentile_rank(aggregate[metric], directions[metric])
        aggregate[f"rank_component_{metric}"] = component
        score += float(weight) * component
    aggregate["stability_score"] = 100.0 * score
    aggregate["stability_rank"] = aggregate["stability_score"].rank(
        method="min", ascending=False
    ).astype(int)
    return aggregate.sort_values(
        ["stability_rank", "candidate_id"]
    ).reset_index(drop=True)


def governance_failures(row: pd.Series, config: dict[str, Any]) -> list[str]:
    gate = config["hierarchical_diagnostics"]["governance"]
    checks = [
        (
            float(row["baseline_dominance_rate"])
            < float(gate["minimum_baseline_dominance_rate"]),
            "naive-baseline dominance rate is below the gate",
        ),
        (
            float(row["mean_macro_f1"]) < float(gate["minimum_macro_f1"]),
            "eight-regime macro-F1 is below the gate",
        ),
        (
            float(row["mean_balanced_accuracy"])
            < float(gate["minimum_balanced_accuracy"]),
            "eight-regime balanced accuracy is below the gate",
        ),
        (
            float(row["mean_family_macro_f1"])
            < float(gate["minimum_family_macro_f1"]),
            "regime-family macro-F1 is below the gate",
        ),
        (
            float(row["mean_transition_recall"])
            < float(gate["minimum_transition_recall"]),
            "transition recall is below the gate",
        ),
        (
            float(row["mean_false_transition_rate"])
            > float(gate["maximum_false_transition_rate"]),
            "false-transition rate exceeds the gate",
        ),
        (
            float(row["regime_collapse_fold_rate"])
            > float(gate["maximum_regime_collapse_fold_rate"]),
            "regime-collapse fold rate exceeds the gate",
        ),
        (
            float(row["bootstrap_margin_lower"])
            <= float(gate["minimum_bootstrap_margin_lower"]),
            "block-bootstrap margin versus the strongest naive baseline is not strictly positive",
        ),
    ]
    return [message for failed, message in checks if failed]


def run_hierarchical_diagnostics(
    monthly: pd.DataFrame,
    plan: RollingTournamentPlan,
    core_candidate: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    candidates = build_hierarchical_candidates(config)
    thresholds = core_candidate["thresholds"]
    fold_rows: list[dict[str, Any]] = []
    calibration_rows: list[pd.DataFrame] = []
    candidate_frames: dict[tuple[str, str], pd.DataFrame] = {}
    baseline_by_fold: dict[str, dict[str, Any]] = {}

    for fold in plan.folds:
        baseline = candidate_fold_baseline(monthly, fold)
        baseline_by_fold[fold.fold_id] = baseline
        raw_rows = []
        for candidate in candidates:
            frame, calibrations = build_candidate_frame(
                monthly,
                training_dates=fold.training_dates,
                evaluation_dates=fold.evaluation_dates,
                candidate=candidate,
                thresholds=thresholds,
                config=config,
            )
            candidate_frames[(candidate["candidate_id"], fold.fold_id)] = frame
            metrics = candidate_metrics(
                frame,
                dates=fold.evaluation_dates,
                strongest_baseline_accuracy=float(
                    baseline["strongest_baseline_accuracy"]
                ),
                config=config,
            )
            raw_rows.append(
                {
                    "fold_id": fold.fold_id,
                    "evaluation_start": fold.evaluation_dates[0],
                    "evaluation_end": fold.evaluation_dates[-1],
                    **candidate,
                    **baseline,
                    **metrics,
                }
            )
            calibrations.insert(0, "fold_id", fold.fold_id)
            calibrations.insert(1, "candidate_id", candidate["candidate_id"])
            calibration_rows.append(calibrations)
        ranked = rank_fold_candidates(pd.DataFrame(raw_rows), config)
        fold_rows.extend(ranked.to_dict(orient="records"))

    fold_metrics = pd.DataFrame(fold_rows)
    aggregate = aggregate_stability(
        fold_metrics,
        candidate_frames,
        plan,
        baseline_by_fold,
        config,
    )

    audit_rows: list[dict[str, Any]] = []
    audit_frames: dict[str, pd.DataFrame] = {}
    for candidate in candidates:
        frame, calibration = build_candidate_frame(
            monthly,
            training_dates=plan.selection_dates,
            evaluation_dates=plan.audit_dates,
            candidate=candidate,
            thresholds=thresholds,
            config=config,
        )
        audit_frames[candidate["candidate_id"]] = frame
        audit_baseline = candidate_fold_baseline(
            monthly,
            RollingFold(
                fold_id="consumed_audit",
                training_dates=plan.selection_dates,
                evaluation_dates=plan.audit_dates,
            ),
        )
        audit_rows.append(
            {
                **candidate,
                **audit_baseline,
                **candidate_metrics(
                    frame,
                    dates=plan.audit_dates,
                    strongest_baseline_accuracy=float(
                        audit_baseline["strongest_baseline_accuracy"]
                    ),
                    config=config,
                ),
            }
        )
    audit = rank_fold_candidates(pd.DataFrame(audit_rows), config).rename(
        columns={"fold_rank": "audit_rank", "fold_score": "audit_score"}
    )
    aggregate = aggregate.merge(
        audit[["candidate_id", "audit_rank", "audit_score"]],
        on="candidate_id",
        how="left",
    )
    aggregate["governance_failures"] = aggregate.apply(
        lambda row: governance_failures(row, config), axis=1
    )
    aggregate["governance_pass"] = aggregate["governance_failures"].map(
        lambda value: len(value) == 0
    )
    selected = aggregate.sort_values(
        ["stability_rank", "candidate_id"]
    ).iloc[0]
    selected_id = str(selected["candidate_id"])
    selected_selection_frames = [
        candidate_frames[(selected_id, fold.fold_id)] for fold in plan.folds
    ]
    selected_selection = (
        pd.concat(selected_selection_frames, ignore_index=True)
        .drop_duplicates(subset=["state_date"], keep="last")
        .sort_values("state_date")
    )
    return {
        "candidates": candidates,
        "fold_metrics": fold_metrics,
        "calibration_metrics": pd.concat(calibration_rows, ignore_index=True),
        "stability": aggregate.sort_values(
            ["stability_rank", "candidate_id"]
        ).reset_index(drop=True),
        "audit": audit.sort_values(["audit_rank", "candidate_id"]).reset_index(drop=True),
        "selected_candidate_id": selected_id,
        "selected_selection_frame": selected_selection,
        "selected_audit_frame": audit_frames[selected_id],
    }


def per_regime_metrics(
    frame: pd.DataFrame,
    dates: Iterable[date],
) -> pd.DataFrame:
    date_set = {pd.Timestamp(item).date() for item in dates}
    subset = frame.loc[frame["state_date"].isin(date_set)]
    rows = []
    for regime in REGIMES:
        actual = subset["actual_regime"].astype(str) == regime
        predicted = subset["decision_regime"].astype(str) == regime
        support = int(actual.sum())
        forecast_count = int(predicted.sum())
        true_positive = int((actual & predicted).sum())
        precision = true_positive / forecast_count if forecast_count else 0.0
        recall = true_positive / support if support else 0.0
        f1 = (
            2.0 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        rows.append(
            {
                "regime": regime,
                "support": support,
                "forecast_count": forecast_count,
                "true_positive": true_positive,
                "precision": precision,
                "recall": recall,
                "f1": f1,
            }
        )
    return pd.DataFrame(rows)


def confusion_table(frame: pd.DataFrame, dates: Iterable[date]) -> pd.DataFrame:
    date_set = {pd.Timestamp(item).date() for item in dates}
    subset = frame.loc[frame["state_date"].isin(date_set)]
    matrix = pd.crosstab(subset["actual_regime"], subset["decision_regime"])
    matrix = matrix.reindex(index=REGIMES, columns=REGIMES, fill_value=0)
    return (
        matrix.stack(future_stack=True)
        .rename("count")
        .reset_index()
        .rename(columns={"decision_regime": "predicted_regime"})
    )


def expanding_candidate_frame(
    monthly: pd.DataFrame,
    *,
    evaluation_dates: Iterable[date],
    candidate: dict[str, str],
    thresholds: dict[str, Any],
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    ordered_dates = tuple(
        sorted({pd.Timestamp(item).date() for item in monthly["state_date"]})
    )
    evaluation_set = {
        pd.Timestamp(item).date() for item in evaluation_dates
    }
    minimum_history = int(
        config["hierarchical_diagnostics"]["calibration"]["minimum_history"]
    )
    frames: list[pd.DataFrame] = []
    calibrations: list[pd.DataFrame] = []
    for state_date in ordered_dates:
        if state_date not in evaluation_set:
            continue
        training_dates = tuple(item for item in ordered_dates if item < state_date)
        if len(training_dates) < minimum_history:
            continue
        frame, calibration = build_candidate_frame(
            monthly,
            training_dates=training_dates,
            evaluation_dates=(state_date,),
            candidate=candidate,
            thresholds=thresholds,
            config=config,
        )
        frames.append(frame)
        calibration.insert(0, "state_date", state_date)
        calibrations.append(calibration)
    return (
        pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(),
        pd.concat(calibrations, ignore_index=True)
        if calibrations
        else pd.DataFrame(),
    )
