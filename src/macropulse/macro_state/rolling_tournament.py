from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

import numpy as np
import pandas as pd

from macropulse.macro_state.tournament import (
    ALL_TARGETS,
    GDP_TARGET,
    REGIME_FAMILY,
    build_core_candidates,
    classify_regime_with_thresholds,
    core_metrics,
    rank_core_metrics,
    rank_uncertainty_metrics,
    target_score,
    uncertainty_metrics,
    uncertainty_monthly,
)


@dataclass(frozen=True)
class RollingFold:
    fold_id: str
    training_dates: tuple[date, ...]
    evaluation_dates: tuple[date, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "fold_id": self.fold_id,
            "training_start": self.training_dates[0],
            "training_end": self.training_dates[-1],
            "training_months": len(self.training_dates),
            "evaluation_start": self.evaluation_dates[0],
            "evaluation_end": self.evaluation_dates[-1],
            "evaluation_months": len(self.evaluation_dates),
        }


@dataclass(frozen=True)
class RollingTournamentPlan:
    folds: tuple[RollingFold, ...]
    selection_dates: tuple[date, ...]
    audit_dates: tuple[date, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "folds": [fold.as_dict() for fold in self.folds],
            "selection_start": self.selection_dates[0],
            "selection_end": self.selection_dates[-1],
            "selection_months": len(self.selection_dates),
            "audit_start": self.audit_dates[0],
            "audit_end": self.audit_dates[-1],
            "audit_months": len(self.audit_dates),
        }


def rolling_origin_plan(
    state_dates: Iterable[date],
    *,
    minimum_training_months: int,
    evaluation_months: int,
    step_months: int,
    audit_months: int,
    minimum_folds: int,
) -> RollingTournamentPlan:
    ordered = tuple(sorted({pd.Timestamp(item).date() for item in state_dates}))
    if any(value <= 0 for value in (
        minimum_training_months,
        evaluation_months,
        step_months,
        audit_months,
        minimum_folds,
    )):
        raise ValueError("Rolling-origin configuration values must be positive.")
    minimum_required = (
        minimum_training_months + evaluation_months + audit_months
    )
    if len(ordered) < minimum_required:
        raise RuntimeError(
            "Rolling-origin tournament requires at least "
            f"{minimum_required} complete states; found {len(ordered)}."
        )
    audit_dates = ordered[-audit_months:]
    selection_dates = ordered[:-audit_months]
    folds: list[RollingFold] = []
    training_end = minimum_training_months
    while training_end + evaluation_months <= len(selection_dates):
        fold_number = len(folds) + 1
        folds.append(
            RollingFold(
                fold_id=f"fold_{fold_number:02d}",
                training_dates=selection_dates[:training_end],
                evaluation_dates=selection_dates[
                    training_end : training_end + evaluation_months
                ],
            )
        )
        training_end += step_months
    if len(folds) < minimum_folds:
        raise RuntimeError(
            "Rolling-origin tournament generated only "
            f"{len(folds)} folds; minimum is {minimum_folds}."
        )
    return RollingTournamentPlan(
        folds=tuple(folds),
        selection_dates=selection_dates,
        audit_dates=audit_dates,
    )


def _previous_actual_predictions(monthly: pd.DataFrame) -> pd.DataFrame:
    ordered = monthly.sort_values("state_date").copy()
    ordered["_ordinal"] = pd.PeriodIndex(
        ordered["state_date"], freq="M"
    ).asi8
    ordered["_previous_ordinal"] = ordered["_ordinal"].shift(1)
    ordered["persistence_prediction"] = ordered["actual_regime"].shift(1)
    ordered.loc[
        (ordered["_ordinal"] - ordered["_previous_ordinal"]) != 1,
        "persistence_prediction",
    ] = None
    return ordered


def candidate_fold_baseline(
    monthly: pd.DataFrame,
    fold: RollingFold,
) -> dict[str, Any]:
    ordered = _previous_actual_predictions(monthly)
    training = ordered.loc[
        ordered["state_date"].isin(set(fold.training_dates))
    ]
    evaluation = ordered.loc[
        ordered["state_date"].isin(set(fold.evaluation_dates))
    ].copy()
    if training.empty or evaluation.empty:
        raise RuntimeError(f"{fold.fold_id} has no baseline observations.")
    mode_values = training["actual_regime"].mode().astype(str).sort_values()
    mode_regime = str(mode_values.iloc[0])
    mode_accuracy = float(
        (evaluation["actual_regime"].astype(str) == mode_regime).mean()
    )
    persistence_rows = evaluation.dropna(
        subset=["persistence_prediction"]
    )
    persistence_accuracy = (
        float(
            (
                persistence_rows["actual_regime"].astype(str)
                == persistence_rows["persistence_prediction"].astype(str)
            ).mean()
        )
        if not persistence_rows.empty
        else float("nan")
    )
    if np.isnan(persistence_accuracy) or mode_accuracy >= persistence_accuracy:
        strongest_name = "training_mode"
        strongest_accuracy = mode_accuracy
    else:
        strongest_name = "persistence"
        strongest_accuracy = persistence_accuracy
    return {
        "training_mode_regime": mode_regime,
        "mode_accuracy": mode_accuracy,
        "persistence_accuracy": persistence_accuracy,
        "strongest_baseline": strongest_name,
        "strongest_baseline_accuracy": strongest_accuracy,
    }


def _rank_percentile(
    series: pd.Series,
    *,
    higher_is_better: bool,
) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    if values.isna().any():
        raise ValueError("Stability ranking inputs cannot be missing.")
    if higher_is_better:
        return values.rank(method="average", pct=True)
    return (-values).rank(method="average", pct=True)


def _stability_score(
    frame: pd.DataFrame,
    *,
    weights: dict[str, float],
) -> pd.DataFrame:
    output = frame.copy()
    directions = {
        "mean_fold_score": True,
        "median_fold_score": True,
        "rank_stability": True,
        "leading_third_rate": True,
        "baseline_dominance_rate": True,
        "uncertainty_method_win_rate": True,
        "average_regret": False,
    }
    score = pd.Series(0.0, index=output.index)
    for metric, weight in weights.items():
        component = _rank_percentile(
            output[metric],
            higher_is_better=directions[metric],
        )
        output[f"stability_component_{metric}"] = component
        score = score + float(weight) * component
    output["stability_score"] = 100.0 * score
    output["stability_rank"] = output["stability_score"].rank(
        method="min", ascending=False
    ).astype(int)
    return output.sort_values(
        ["stability_rank", "candidate_id"]
    ).reset_index(drop=True)


def _aggregate_fold_stability(
    fold_metrics: pd.DataFrame,
    *,
    candidate_count: int,
    config: dict[str, Any],
    final_stage: bool,
) -> pd.DataFrame:
    section = config["stability_tournament"]
    leading_cutoff = max(
        1,
        int(math.ceil(
            candidate_count * float(section["leading_third_fraction"])
        )),
    )
    catastrophic_cutoff = max(
        leading_cutoff,
        int(math.ceil(
            candidate_count
            * float(section["catastrophic_rank_fraction"])
        )),
    )
    rank_column = "final_rank" if final_stage else "core_rank"
    score_column = "final_score" if final_stage else "core_score"
    best_by_fold = fold_metrics.groupby("fold_id")[score_column].max()
    records: list[dict[str, Any]] = []
    for candidate_id, frame in fold_metrics.groupby("candidate_id"):
        ranks = frame[rank_column].astype(float)
        scores = frame[score_column].astype(float)
        regrets = [
            float(best_by_fold.loc[row.fold_id] - getattr(row, score_column))
            for row in frame.itertuples(index=False)
        ]
        record = {
            "candidate_id": str(candidate_id),
            "folds": int(len(frame)),
            "mean_fold_score": float(scores.mean()),
            "median_fold_score": float(scores.median()),
            "mean_fold_rank": float(ranks.mean()),
            "median_fold_rank": float(ranks.median()),
            "rank_std": float(ranks.std(ddof=0)),
            "rank_stability": float(
                max(0.0, 1.0 - ranks.std(ddof=0) / max(candidate_count - 1, 1))
            ),
            "best_fold_rank": int(ranks.min()),
            "worst_fold_rank": int(ranks.max()),
            "fold_win_rate": float((ranks == 1).mean()),
            "leading_third_rate": float((ranks <= leading_cutoff).mean()),
            "catastrophic_fold_count": int(
                (ranks > catastrophic_cutoff).sum()
            ),
            "baseline_dominance_rate": float(
                frame["beats_strongest_baseline"].astype(bool).mean()
            ),
            "mean_baseline_margin": float(
                frame["baseline_margin"].mean()
            ),
            "average_regret": float(np.mean(regrets)),
            "regime_collapse_fold_rate": float(
                (frame["regime_collapse_penalty"] > 0.0).mean()
            ),
        }
        if final_stage:
            record["core_candidate_id"] = str(
                frame.iloc[0]["core_candidate_id"]
            )
            record["uncertainty_id"] = str(
                frame.iloc[0]["uncertainty_id"]
            )
            record["uncertainty_method_win_rate"] = float(
                (frame["uncertainty_method_rank"] == 1).mean()
            )
            comparable = frame.loc[
                frame["uncertainty_id"] != "independent_normal"
            ]
            record["proper_score_dominance_rate"] = (
                float(comparable["proper_score_dominates"].mean())
                if not comparable.empty
                else 1.0
            )
        else:
            record["uncertainty_method_win_rate"] = 0.0
        records.append(record)
    aggregate = pd.DataFrame(records)
    weights_key = (
        "final_stability_weights" if final_stage else "core_stability_weights"
    )
    ranked = _stability_score(
        aggregate,
        weights=section[weights_key],
    )
    ranked["leading_third_cutoff"] = leading_cutoff
    ranked["catastrophic_rank_cutoff"] = catastrophic_cutoff
    return ranked



def build_normalized_score_cache(
    dataset: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    actual_history = dataset[
        ["source_target", "target_period_ordinal", "actual"]
    ].copy()
    caches: dict[str, pd.DataFrame] = {}
    for normalization_id in config["tournament"][
        "normalization_candidates"
    ]:
        rows: list[dict[str, Any]] = []
        for row in dataset.itertuples(index=False):
            kwargs = {
                "target": str(row.source_target),
                "target_period_ordinal": int(row.target_period_ordinal),
                "normalization_id": str(normalization_id),
                "config": config,
                "actual_history": actual_history,
            }
            interval = sorted(
                [
                    target_score(float(row.lower_80), **kwargs),
                    target_score(float(row.upper_80), **kwargs),
                ]
            )
            rows.append(
                {
                    "state_date": pd.Timestamp(row.state_date).date(),
                    "source_target": str(row.source_target),
                    "point_score": target_score(
                        float(row.point_forecast), **kwargs
                    ),
                    "actual_score": target_score(float(row.actual), **kwargs),
                    "lower_score": float(interval[0]),
                    "upper_score": float(interval[1]),
                }
            )
        caches[str(normalization_id)] = pd.DataFrame(rows)
    return caches


def candidate_monthly_states_from_cache(
    score_cache: pd.DataFrame,
    candidate: dict[str, Any],
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    inflation_weights = candidate["inflation_weights"]
    labour_weights = candidate["labour_weights"]
    thresholds = candidate["thresholds"]

    def weighted(
        values: dict[str, float],
        weights: dict[str, float],
    ) -> float:
        return float(sum(values[key] * weights[key] for key in weights))

    for state_date, frame in score_cache.groupby("state_date", sort=True):
        target_rows = {
            str(row.source_target): row
            for row in frame.itertuples(index=False)
        }
        if set(target_rows) != set(ALL_TARGETS):
            continue
        point = {
            target: float(row.point_score)
            for target, row in target_rows.items()
        }
        actual = {
            target: float(row.actual_score)
            for target, row in target_rows.items()
        }
        lower = {
            target: float(row.lower_score)
            for target, row in target_rows.items()
        }
        upper = {
            target: float(row.upper_score)
            for target, row in target_rows.items()
        }
        forecast_growth = point[GDP_TARGET]
        actual_growth = actual[GDP_TARGET]
        forecast_inflation = weighted(point, inflation_weights)
        actual_inflation = weighted(actual, inflation_weights)
        forecast_labour = weighted(point, labour_weights)
        actual_labour = weighted(actual, labour_weights)
        lower_inflation = weighted(lower, inflation_weights)
        upper_inflation = weighted(upper, inflation_weights)
        lower_labour = weighted(lower, labour_weights)
        upper_labour = weighted(upper, labour_weights)
        forecast_regime = classify_regime_with_thresholds(
            forecast_growth,
            forecast_inflation,
            forecast_labour,
            thresholds,
        )
        actual_regime = classify_regime_with_thresholds(
            actual_growth,
            actual_inflation,
            actual_labour,
            thresholds,
        )
        records.append(
            {
                "candidate_id": str(candidate["candidate_id"]),
                "state_date": pd.Timestamp(state_date).date(),
                "forecast_growth": forecast_growth,
                "forecast_inflation": forecast_inflation,
                "forecast_labour": forecast_labour,
                "actual_growth": actual_growth,
                "actual_inflation": actual_inflation,
                "actual_labour": actual_labour,
                "growth_lower": lower[GDP_TARGET],
                "growth_upper": upper[GDP_TARGET],
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
    return pd.DataFrame(records).sort_values(
        "state_date"
    ).reset_index(drop=True)


def run_rolling_core_tournament(
    dataset: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[
    RollingTournamentPlan,
    list[dict[str, Any]],
    dict[str, pd.DataFrame],
    pd.DataFrame,
    pd.DataFrame,
]:
    section = config["stability_tournament"]
    plan = rolling_origin_plan(
        dataset["state_date"].unique(),
        minimum_training_months=int(section["minimum_training_months"]),
        evaluation_months=int(section["evaluation_months"]),
        step_months=int(section["step_months"]),
        audit_months=int(section["audit_months"]),
        minimum_folds=int(section["minimum_folds"]),
    )
    candidates = build_core_candidates(config)
    score_caches = build_normalized_score_cache(dataset, config)
    monthly_by_candidate: dict[str, pd.DataFrame] = {}
    raw_rows: list[dict[str, Any]] = []
    for candidate in candidates:
        monthly = candidate_monthly_states_from_cache(
            score_caches[str(candidate["normalization_id"])],
            candidate,
        )
        monthly_by_candidate[str(candidate["candidate_id"])] = monthly
        for fold in plan.folds:
            metrics = core_metrics(
                monthly,
                fold.evaluation_dates,
                deadzone=float(section["score_deadzone"]),
            )
            baseline = candidate_fold_baseline(monthly, fold)
            margin = (
                float(metrics["exact_regime_accuracy"])
                - float(baseline["strongest_baseline_accuracy"])
            )
            raw_rows.append(
                {
                    "fold_id": fold.fold_id,
                    "candidate_id": str(candidate["candidate_id"]),
                    "training_start": fold.training_dates[0],
                    "training_end": fold.training_dates[-1],
                    "training_months": len(fold.training_dates),
                    "evaluation_start": fold.evaluation_dates[0],
                    "evaluation_end": fold.evaluation_dates[-1],
                    "evaluation_months": len(fold.evaluation_dates),
                    **metrics,
                    **baseline,
                    "baseline_margin": margin,
                    "beats_strongest_baseline": bool(margin > 0.0),
                }
            )
    raw = pd.DataFrame(raw_rows)
    ranked_frames: list[pd.DataFrame] = []
    for fold_id, frame in raw.groupby("fold_id", sort=True):
        ranked = rank_core_metrics(
            frame.copy(),
            config["tournament"]["core_metric_weights"],
        )
        ranked["fold_id"] = fold_id
        ranked_frames.append(ranked)
    fold_metrics = pd.concat(ranked_frames, ignore_index=True)
    aggregate = _aggregate_fold_stability(
        fold_metrics,
        candidate_count=len(candidates),
        config=config,
        final_stage=False,
    )
    minimum_leading = float(section["minimum_leading_third_rate"])
    minimum_baseline = float(section["minimum_baseline_dominance_rate"])
    maximum_collapse = float(section["maximum_regime_collapse_fold_rate"])
    aggregate["governance_pass"] = (
        (aggregate["median_fold_rank"] <= aggregate["leading_third_cutoff"])
        & (aggregate["catastrophic_fold_count"] == 0)
        & (aggregate["leading_third_rate"] >= minimum_leading)
        & (aggregate["baseline_dominance_rate"] >= minimum_baseline)
        & (aggregate["regime_collapse_fold_rate"] <= maximum_collapse)
    )
    return plan, candidates, monthly_by_candidate, fold_metrics, aggregate


def _method_comparison(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["uncertainty_method_rank"] = output.groupby(
        ["fold_id", "core_candidate_id"]
    )["uncertainty_score"].rank(
        method="min", ascending=False
    ).astype(int)
    reference = output.loc[
        output["uncertainty_id"] == "independent_normal",
        [
            "fold_id",
            "core_candidate_id",
            "brier_score",
            "log_loss",
        ],
    ].rename(
        columns={
            "brier_score": "reference_brier_score",
            "log_loss": "reference_log_loss",
        }
    )
    output = output.merge(
        reference,
        on=["fold_id", "core_candidate_id"],
        how="left",
    )
    output["proper_score_improvement"] = 0.5 * (
        (output["reference_brier_score"] - output["brier_score"])
        / output["reference_brier_score"].clip(lower=1e-9)
    ) + 0.5 * (
        (output["reference_log_loss"] - output["log_loss"])
        / output["reference_log_loss"].clip(lower=1e-9)
    )
    output["proper_score_dominates"] = (
        (output["brier_score"] < output["reference_brier_score"])
        & (output["log_loss"] < output["reference_log_loss"])
    )
    output.loc[
        output["uncertainty_id"] == "independent_normal",
        "proper_score_dominates",
    ] = True
    return output


def run_rolling_uncertainty_tournament(
    *,
    core_candidates: list[dict[str, Any]],
    monthly_by_candidate: dict[str, pd.DataFrame],
    core_fold_metrics: pd.DataFrame,
    core_stability: pd.DataFrame,
    plan: RollingTournamentPlan,
    config: dict[str, Any],
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    dict[str, pd.DataFrame],
    pd.DataFrame,
]:
    section = config["stability_tournament"]
    top_n = int(section["top_core_candidates"])
    selected_core_ids = core_stability.nsmallest(
        top_n, "stability_rank"
    )["candidate_id"].astype(str).tolist()
    candidate_map = {
        str(candidate["candidate_id"]): candidate
        for candidate in core_candidates
    }
    monthly_final: dict[str, pd.DataFrame] = {}
    uncertainty_rows: list[dict[str, Any]] = []
    for core_id in selected_core_ids:
        core = candidate_map[core_id]
        monthly = monthly_by_candidate[core_id]
        for uncertainty_id in config["tournament"]["uncertainty_candidates"]:
            final = uncertainty_monthly(
                monthly, core, uncertainty_id, config
            )
            final_id = str(final.iloc[0]["candidate_id"])
            monthly_final[final_id] = final
            for fold in plan.folds:
                uncertainty_rows.append(
                    {
                        "fold_id": fold.fold_id,
                        "candidate_id": final_id,
                        "core_candidate_id": core_id,
                        "uncertainty_id": uncertainty_id,
                        "evaluation_start": fold.evaluation_dates[0],
                        "evaluation_end": fold.evaluation_dates[-1],
                        "evaluation_months": len(fold.evaluation_dates),
                        **uncertainty_metrics(
                            final, fold.evaluation_dates
                        ),
                    }
                )
    uncertainty_raw = pd.DataFrame(uncertainty_rows)
    uncertainty_ranked_frames: list[pd.DataFrame] = []
    for fold_id, frame in uncertainty_raw.groupby("fold_id", sort=True):
        ranked = rank_uncertainty_metrics(
            frame.copy(),
            config["tournament"]["uncertainty_metric_weights"],
        )
        ranked["fold_id"] = fold_id
        uncertainty_ranked_frames.append(ranked)
    uncertainty_fold = pd.concat(
        uncertainty_ranked_frames, ignore_index=True
    )
    core_columns = [
        "fold_id",
        "candidate_id",
        "core_score",
        "core_rank",
        "exact_regime_accuracy",
        "family_accuracy",
        "sign_accuracy",
        "dimension_rmse",
        "regime_collapse_penalty",
        "mode_accuracy",
        "persistence_accuracy",
        "strongest_baseline",
        "strongest_baseline_accuracy",
        "baseline_margin",
        "beats_strongest_baseline",
    ]
    final_fold = uncertainty_fold.merge(
        core_fold_metrics[core_columns].rename(
            columns={"candidate_id": "core_candidate_id"}
        ),
        on=["fold_id", "core_candidate_id"],
        how="left",
    )
    weights = config["tournament"]["final_score_weights"]
    final_fold["final_score"] = (
        float(weights["core"]) * final_fold["core_score"]
        + float(weights["uncertainty"])
        * final_fold["uncertainty_score"]
    )
    final_fold["final_rank"] = final_fold.groupby("fold_id")[
        "final_score"
    ].rank(method="min", ascending=False).astype(int)
    final_fold = _method_comparison(final_fold)
    aggregate = _aggregate_fold_stability(
        final_fold,
        candidate_count=int(final_fold["candidate_id"].nunique()),
        config=config,
        final_stage=True,
    )
    minimum_leading = float(section["minimum_leading_third_rate"])
    minimum_baseline = float(section["minimum_baseline_dominance_rate"])
    minimum_method = float(section["minimum_uncertainty_method_win_rate"])
    minimum_proper = float(section["minimum_proper_score_dominance_rate"])
    maximum_collapse = float(section["maximum_regime_collapse_fold_rate"])
    aggregate["governance_pass"] = (
        (aggregate["median_fold_rank"] <= aggregate["leading_third_cutoff"])
        & (aggregate["catastrophic_fold_count"] == 0)
        & (aggregate["leading_third_rate"] >= minimum_leading)
        & (aggregate["baseline_dominance_rate"] >= minimum_baseline)
        & (aggregate["uncertainty_method_win_rate"] >= minimum_method)
        & (aggregate["regime_collapse_fold_rate"] <= maximum_collapse)
        & (
            (aggregate["uncertainty_id"] == "independent_normal")
            | (
                aggregate["proper_score_dominance_rate"]
                >= minimum_proper
            )
        )
    )
    audit = audit_final_candidates(
        core_candidates=core_candidates,
        monthly_by_candidate=monthly_by_candidate,
        monthly_final=monthly_final,
        core_ids=selected_core_ids,
        plan=plan,
        config=config,
    )
    aggregate = aggregate.merge(
        audit[
            [
                "candidate_id",
                "audit_final_score",
                "audit_final_rank",
                "audit_exact_regime_accuracy",
                "audit_brier_score",
                "audit_log_loss",
                "audit_coverage_80",
                "audit_top1_accuracy",
                "audit_baseline_margin",
            ]
        ],
        on="candidate_id",
        how="left",
    )
    return aggregate, final_fold, monthly_final, audit


def audit_final_candidates(
    *,
    core_candidates: list[dict[str, Any]],
    monthly_by_candidate: dict[str, pd.DataFrame],
    monthly_final: dict[str, pd.DataFrame],
    core_ids: list[str],
    plan: RollingTournamentPlan,
    config: dict[str, Any],
) -> pd.DataFrame:
    candidate_map = {
        str(candidate["candidate_id"]): candidate
        for candidate in core_candidates
    }
    core_rows: list[dict[str, Any]] = []
    for core_id in core_ids:
        monthly = monthly_by_candidate[core_id]
        metrics = core_metrics(
            monthly,
            plan.audit_dates,
            deadzone=float(
                config["stability_tournament"]["score_deadzone"]
            ),
        )
        pseudo_fold = RollingFold(
            fold_id="audit",
            training_dates=plan.selection_dates,
            evaluation_dates=plan.audit_dates,
        )
        baseline = candidate_fold_baseline(monthly, pseudo_fold)
        core_rows.append(
            {"candidate_id": core_id, **metrics, **baseline}
        )
    core_ranked = rank_core_metrics(
        pd.DataFrame(core_rows),
        config["tournament"]["core_metric_weights"],
    ).rename(
        columns={
            "core_score": "audit_core_score",
            "core_rank": "audit_core_rank",
            "exact_regime_accuracy": "audit_exact_regime_accuracy",
            "family_accuracy": "audit_family_accuracy",
            "sign_accuracy": "audit_sign_accuracy",
            "dimension_rmse": "audit_dimension_rmse",
            "regime_collapse_penalty": "audit_regime_collapse_penalty",
            "strongest_baseline_accuracy": "audit_baseline_accuracy",
        }
    )
    uncertainty_rows: list[dict[str, Any]] = []
    for final_id, final in monthly_final.items():
        uncertainty_rows.append(
            {
                "candidate_id": final_id,
                "core_candidate_id": str(final.iloc[0]["core_candidate_id"]),
                "uncertainty_id": str(final.iloc[0]["uncertainty_id"]),
                **uncertainty_metrics(final, plan.audit_dates),
            }
        )
    uncertainty_ranked = rank_uncertainty_metrics(
        pd.DataFrame(uncertainty_rows),
        config["tournament"]["uncertainty_metric_weights"],
    ).rename(
        columns={
            "uncertainty_score": "audit_uncertainty_score",
            "uncertainty_rank": "audit_uncertainty_rank",
            "brier_score": "audit_brier_score",
            "log_loss": "audit_log_loss",
            "coverage_80": "audit_coverage_80",
            "top1_accuracy": "audit_top1_accuracy",
            "mean_effective_regimes": "audit_mean_effective_regimes",
        }
    )
    audit = uncertainty_ranked.merge(
        core_ranked[
            [
                "candidate_id",
                "audit_core_score",
                "audit_core_rank",
                "audit_exact_regime_accuracy",
                "audit_family_accuracy",
                "audit_sign_accuracy",
                "audit_dimension_rmse",
                "audit_regime_collapse_penalty",
                "audit_baseline_accuracy",
            ]
        ].rename(columns={"candidate_id": "core_candidate_id"}),
        on="core_candidate_id",
        how="left",
    )
    weights = config["tournament"]["final_score_weights"]
    audit["audit_final_score"] = (
        float(weights["core"]) * audit["audit_core_score"]
        + float(weights["uncertainty"])
        * audit["audit_uncertainty_score"]
    )
    audit["audit_final_rank"] = audit["audit_final_score"].rank(
        method="min", ascending=False
    ).astype(int)
    audit["audit_baseline_margin"] = (
        audit["audit_exact_regime_accuracy"]
        - audit["audit_baseline_accuracy"]
    )
    return audit.sort_values(
        ["audit_final_rank", "candidate_id"]
    ).reset_index(drop=True)


def _fold_difference_series(
    monthly: pd.DataFrame,
    fold: RollingFold,
    strongest_baseline: str,
) -> np.ndarray:
    ordered = _previous_actual_predictions(monthly)
    training = ordered.loc[
        ordered["state_date"].isin(set(fold.training_dates))
    ]
    evaluation = ordered.loc[
        ordered["state_date"].isin(set(fold.evaluation_dates))
    ].copy()
    mode_regime = str(
        training["actual_regime"].mode().astype(str).sort_values().iloc[0]
    )
    candidate_hit = (
        evaluation["forecast_regime"].astype(str)
        == evaluation["actual_regime"].astype(str)
    ).astype(float)
    if strongest_baseline == "training_mode":
        baseline_hit = (
            evaluation["actual_regime"].astype(str) == mode_regime
        ).astype(float)
        return (candidate_hit - baseline_hit).to_numpy(dtype=float)
    valid = evaluation["persistence_prediction"].notna()
    candidate_hit = candidate_hit.loc[valid]
    baseline_hit = (
        evaluation.loc[valid, "actual_regime"].astype(str)
        == evaluation.loc[valid, "persistence_prediction"].astype(str)
    ).astype(float)
    return (candidate_hit - baseline_hit).to_numpy(dtype=float)


def block_bootstrap_margin_ci(
    differences_by_fold: list[np.ndarray],
    *,
    repetitions: int,
    block_months: int,
    confidence: float,
    seed: int,
) -> dict[str, float]:
    arrays = [np.asarray(item, dtype=float) for item in differences_by_fold]
    arrays = [item for item in arrays if len(item)]
    if not arrays:
        return {
            "bootstrap_margin_mean": float("nan"),
            "bootstrap_margin_lower": float("nan"),
            "bootstrap_margin_upper": float("nan"),
        }
    observed = float(np.concatenate(arrays).mean())
    rng = np.random.default_rng(seed)
    estimates = np.empty(repetitions, dtype=float)
    for iteration in range(repetitions):
        sampled_parts: list[np.ndarray] = []
        for values in arrays:
            length = len(values)
            block = min(block_months, length)
            starts = np.arange(max(1, length - block + 1))
            pieces: list[np.ndarray] = []
            while sum(len(piece) for piece in pieces) < length:
                start = int(rng.choice(starts))
                pieces.append(values[start : start + block])
            sampled_parts.append(np.concatenate(pieces)[:length])
        estimates[iteration] = float(np.concatenate(sampled_parts).mean())
    alpha = 1.0 - confidence
    return {
        "bootstrap_margin_mean": observed,
        "bootstrap_margin_lower": float(
            np.quantile(estimates, alpha / 2.0)
        ),
        "bootstrap_margin_upper": float(
            np.quantile(estimates, 1.0 - alpha / 2.0)
        ),
    }


def attach_bootstrap_intervals(
    aggregate: pd.DataFrame,
    *,
    final_fold_metrics: pd.DataFrame,
    monthly_final: dict[str, pd.DataFrame],
    plan: RollingTournamentPlan,
    config: dict[str, Any],
) -> pd.DataFrame:
    section = config["stability_tournament"]
    rows = []
    for record in aggregate.itertuples(index=False):
        candidate_id = str(record.candidate_id)
        monthly = monthly_final[candidate_id]
        fold_rows = final_fold_metrics.loc[
            final_fold_metrics["candidate_id"] == candidate_id
        ].set_index("fold_id")
        differences = []
        for fold in plan.folds:
            strongest = str(
                fold_rows.loc[fold.fold_id, "strongest_baseline"]
            )
            differences.append(
                _fold_difference_series(monthly, fold, strongest)
            )
        digest = hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()
        seed = int(section["random_seed"]) + int(digest[:8], 16)
        rows.append(
            {
                "candidate_id": candidate_id,
                **block_bootstrap_margin_ci(
                    differences,
                    repetitions=int(section["bootstrap_repetitions"]),
                    block_months=int(section["bootstrap_block_months"]),
                    confidence=float(section["bootstrap_confidence"]),
                    seed=seed,
                ),
            }
        )
    return aggregate.merge(pd.DataFrame(rows), on="candidate_id", how="left")


def selected_subperiod_metrics(
    monthly: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for subperiod_id, bounds in config["stability_tournament"][
        "subperiods"
    ].items():
        start = pd.Timestamp(bounds["start"]).date()
        end = pd.Timestamp(bounds["end"]).date()
        dates = [
            item
            for item in monthly["state_date"]
            if start <= pd.Timestamp(item).date() <= end
        ]
        if not dates:
            continue
        core = core_metrics(
            monthly,
            dates,
            deadzone=float(
                config["stability_tournament"]["score_deadzone"]
            ),
        )
        uncertainty = uncertainty_metrics(monthly, dates)
        rows.append(
            {
                "subperiod_id": str(subperiod_id),
                "start_date": min(dates),
                "end_date": max(dates),
                **core,
                **uncertainty,
            }
        )
    return pd.DataFrame(rows)
