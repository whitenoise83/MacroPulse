from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

import numpy as np
import pandas as pd

from macropulse.macro_state.rolling_tournament import (
    RollingFold,
    RollingTournamentPlan,
    block_bootstrap_margin_ci,
    build_normalized_score_cache,
    candidate_monthly_states_from_cache,
    rolling_origin_plan,
)
from macropulse.macro_state.tournament import (
    REGIMES,
    REGIME_FAMILY,
    build_core_candidates,
    load_tournament_dataset,
    uncertainty_monthly,
)

TEMPORAL_POLICIES = (
    "raw_monthly",
    "hysteresis_thresholds",
    "one_month_confirmation",
    "persistence_prior",
)


@dataclass(frozen=True)
class TemporalSource:
    stability_id: str
    reconstruction_id: str
    candidate_id: str
    core_candidate_id: str
    uncertainty_id: str
    governance_pass: bool


def latest_temporal_source(repository: Any, stability_id: str | None = None) -> TemporalSource:
    if stability_id:
        frame = repository.query_df(
            """
            SELECT * FROM macro_state_stability_runs
            WHERE stability_id = ? AND status = 'success'
            LIMIT 1
            """,
            [stability_id],
        )
    else:
        frame = repository.query_df(
            """
            SELECT * FROM macro_state_stability_runs
            WHERE status = 'success'
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
    if frame.empty:
        raise RuntimeError("No successful Model 1D stability run is available.")
    row = frame.iloc[0]
    return TemporalSource(
        stability_id=str(row["stability_id"]),
        reconstruction_id=str(row["reconstruction_id"]),
        candidate_id=str(row["selected_candidate_id"]),
        core_candidate_id=str(row["selected_core_candidate_id"]),
        uncertainty_id=str(row["selected_uncertainty_id"]),
        governance_pass=bool(row["selected_governance_pass"]),
    )


def source_candidate_monthly(
    repository: Any,
    config: dict[str, Any],
    stability_id: str | None = None,
) -> tuple[TemporalSource, dict[str, Any], pd.DataFrame]:
    source = latest_temporal_source(repository, stability_id)
    reconstruction_id, dataset = load_tournament_dataset(
        repository, source.reconstruction_id
    )
    if reconstruction_id != source.reconstruction_id:
        raise RuntimeError("Stability and reconstruction lineage do not match.")
    candidate_map = {
        str(item["candidate_id"]): item for item in build_core_candidates(config)
    }
    if source.core_candidate_id not in candidate_map:
        raise RuntimeError("Selected v0.3.1 core candidate is absent from governance.")
    core = candidate_map[source.core_candidate_id]
    cache = build_normalized_score_cache(dataset, config)
    monthly = candidate_monthly_states_from_cache(
        cache[str(core["normalization_id"])], core
    )
    final = uncertainty_monthly(monthly, core, source.uncertainty_id, config)
    final["state_date"] = pd.to_datetime(final["state_date"]).dt.date
    return source, core, final.sort_values("state_date").reset_index(drop=True)


def temporal_plan(state_dates: Iterable[date], config: dict[str, Any]) -> RollingTournamentPlan:
    section = config["stability_tournament"]
    return rolling_origin_plan(
        state_dates,
        minimum_training_months=int(section["minimum_training_months"]),
        evaluation_months=int(section["evaluation_months"]),
        step_months=int(section["step_months"]),
        audit_months=int(section["audit_months"]),
        minimum_folds=int(section["minimum_folds"]),
    )


def _month_ordinal(value: Any) -> int:
    return int(pd.Period(pd.Timestamp(value), freq="M").ordinal)


def _contiguous(previous: Any, current: Any) -> bool:
    return _month_ordinal(current) - _month_ordinal(previous) == 1


def _probabilities(value: Any) -> dict[str, float]:
    parsed = json.loads(value) if isinstance(value, str) else dict(value or {})
    output = {regime: max(0.0, float(parsed.get(regime, 0.0))) for regime in REGIMES}
    total = float(sum(output.values()))
    if total <= 0:
        return {regime: 1.0 / len(REGIMES) for regime in REGIMES}
    return {regime: probability / total for regime, probability in output.items()}


def _probability_summary(probabilities: dict[str, float], actual: str) -> dict[str, Any]:
    vector = np.asarray([probabilities[regime] for regime in REGIMES])
    target = np.asarray([1.0 if regime == actual else 0.0 for regime in REGIMES])
    top = max(probabilities, key=probabilities.get)
    actual_probability = max(probabilities[actual], 1e-12)
    entropy = -sum(value * math.log(value) for value in probabilities.values() if value > 0)
    return {
        "decision_top_regime": top,
        "decision_top_probability": float(probabilities[top]),
        "decision_actual_probability": float(actual_probability),
        "decision_brier_score": float(np.square(vector - target).sum()),
        "decision_log_loss": float(-math.log(actual_probability)),
        "decision_effective_regimes": float(math.exp(entropy)),
    }


def apply_temporal_policy(
    monthly: pd.DataFrame,
    policy_id: str,
    config: dict[str, Any],
) -> pd.DataFrame:
    if policy_id not in TEMPORAL_POLICIES:
        raise ValueError(f"Unknown temporal policy: {policy_id}")
    section = config["temporal_diagnostics"]
    rows: list[dict[str, Any]] = []
    previous_date: date | None = None
    previous_decision: str | None = None
    pending_regime: str | None = None
    pending_count = 0

    for row in monthly.sort_values("state_date").itertuples(index=False):
        state_date = pd.Timestamp(row.state_date).date()
        raw = str(row.forecast_regime)
        actual = str(row.actual_regime)
        source_probabilities = _probabilities(row.probabilities_json)
        is_contiguous = previous_date is not None and _contiguous(previous_date, state_date)
        gap_reset = previous_date is not None and not is_contiguous

        if previous_decision is None or gap_reset:
            decision = raw
            decision_probabilities = dict(source_probabilities)
            pending_regime = None
            pending_count = 0
        elif policy_id == "raw_monthly":
            decision = raw
            decision_probabilities = dict(source_probabilities)
        elif policy_id == "hysteresis_thresholds":
            settings = section["policies"][policy_id]
            raw_probability = source_probabilities[raw]
            prior_probability = source_probabilities[previous_decision]
            switch = (
                raw != previous_decision
                and raw_probability >= float(settings["minimum_top_probability"])
                and raw_probability - prior_probability
                >= float(settings["minimum_probability_advantage"])
            )
            decision = raw if switch else previous_decision
            decision_probabilities = dict(source_probabilities)
        elif policy_id == "one_month_confirmation":
            required = int(section["policies"][policy_id]["consecutive_months_required"])
            if raw == previous_decision:
                decision = previous_decision
                pending_regime = None
                pending_count = 0
            else:
                if pending_regime == raw:
                    pending_count += 1
                else:
                    pending_regime = raw
                    pending_count = 1
                if pending_count >= required:
                    decision = raw
                    pending_regime = None
                    pending_count = 0
                else:
                    decision = previous_decision
            decision_probabilities = dict(source_probabilities)
        else:
            weight = float(section["policies"][policy_id]["persistence_weight"])
            decision_probabilities = {
                regime: (1.0 - weight) * probability
                + weight * (1.0 if regime == previous_decision else 0.0)
                for regime, probability in source_probabilities.items()
            }
            total = sum(decision_probabilities.values())
            decision_probabilities = {
                regime: probability / total
                for regime, probability in decision_probabilities.items()
            }
            decision = max(decision_probabilities, key=decision_probabilities.get)

        rows.append(
            {
                **row._asdict(),
                "policy_id": policy_id,
                "raw_regime": raw,
                "decision_regime": decision,
                "decision_family": REGIME_FAMILY[decision],
                "actual_family": REGIME_FAMILY[actual],
                "contiguous_from_previous": is_contiguous,
                "gap_reset": gap_reset,
                "decision_changed": bool(
                    previous_decision is not None
                    and is_contiguous
                    and decision != previous_decision
                ),
                "decision_probabilities_json": json.dumps(
                    decision_probabilities, sort_keys=True
                ),
                **_probability_summary(decision_probabilities, actual),
            }
        )
        previous_date = state_date
        previous_decision = decision

    output = pd.DataFrame(rows).reset_index(drop=True)
    output["previous_actual_regime"] = output["actual_regime"].shift(1)
    output["previous_actual_date"] = output["state_date"].shift(1)
    actual_contiguous = [False]
    for previous, current in zip(output["state_date"].iloc[:-1], output["state_date"].iloc[1:]):
        actual_contiguous.append(_contiguous(previous, current))
    output["actual_contiguous"] = actual_contiguous
    output["actual_transition"] = (
        output["actual_contiguous"]
        & output["previous_actual_regime"].notna()
        & (output["actual_regime"].astype(str) != output["previous_actual_regime"].astype(str))
    )
    output["stable_actual_month"] = output["actual_contiguous"] & ~output["actual_transition"]
    output["persistence_prediction"] = output["previous_actual_regime"].where(
        output["actual_contiguous"]
    )
    output["decision_correct"] = output["decision_regime"].astype(str) == output["actual_regime"].astype(str)
    output["family_correct"] = output["decision_family"].astype(str) == output["actual_family"].astype(str)
    output["persistence_correct"] = (
        output["persistence_prediction"].notna()
        & (output["persistence_prediction"].astype(str) == output["actual_regime"].astype(str))
    )
    return output


def _subset(frame: pd.DataFrame, dates: Iterable[date]) -> pd.DataFrame:
    date_set = {pd.Timestamp(item).date() for item in dates}
    return frame.loc[frame["state_date"].isin(date_set)].copy()

def transition_events(
    frame: pd.DataFrame,
    dates: Iterable[date],
    matching_window_months: int,
) -> pd.DataFrame:
    subset = _subset(frame, dates).sort_values("state_date")
    actual_events: list[dict[str, Any]] = []
    predicted_events: list[dict[str, Any]] = []
    previous = None
    for row in subset.itertuples(index=False):
        if previous is not None and _contiguous(previous.state_date, row.state_date):
            if str(row.actual_regime) != str(previous.actual_regime):
                actual_events.append(
                    {
                        "actual_date": pd.Timestamp(row.state_date).date(),
                        "actual_from_regime": str(previous.actual_regime),
                        "actual_to_regime": str(row.actual_regime),
                    }
                )
            if str(row.decision_regime) != str(previous.decision_regime):
                predicted_events.append(
                    {
                        "predicted_date": pd.Timestamp(row.state_date).date(),
                        "predicted_from_regime": str(previous.decision_regime),
                        "predicted_to_regime": str(row.decision_regime),
                    }
                )
        previous = row

    unmatched = set(range(len(predicted_events)))
    rows: list[dict[str, Any]] = []
    for actual in actual_events:
        actual_ordinal = _month_ordinal(actual["actual_date"])
        choices: list[tuple[int, int]] = []
        for index in unmatched:
            predicted = predicted_events[index]
            if predicted["predicted_to_regime"] != actual["actual_to_regime"]:
                continue
            lag = _month_ordinal(predicted["predicted_date"]) - actual_ordinal
            if abs(lag) <= matching_window_months:
                choices.append((abs(lag), index))
        if choices:
            _, index = sorted(choices)[0]
            unmatched.remove(index)
            predicted = predicted_events[index]
            lag = _month_ordinal(predicted["predicted_date"]) - actual_ordinal
            rows.append(
                {
                    "event_type": "actual_transition",
                    **actual,
                    **predicted,
                    "matched": True,
                    "lead_lag_months": int(lag),
                }
            )
        else:
            rows.append(
                {
                    "event_type": "actual_transition",
                    **actual,
                    "predicted_date": None,
                    "predicted_from_regime": None,
                    "predicted_to_regime": None,
                    "matched": False,
                    "lead_lag_months": None,
                }
            )
    for index in sorted(unmatched):
        rows.append(
            {
                "event_type": "false_predicted_transition",
                "actual_date": None,
                "actual_from_regime": None,
                "actual_to_regime": None,
                **predicted_events[index],
                "matched": False,
                "lead_lag_months": None,
            }
        )
    return pd.DataFrame(rows)


def decision_metrics(
    frame: pd.DataFrame,
    dates: Iterable[date],
    config: dict[str, Any],
) -> dict[str, Any]:
    subset = _subset(frame, dates)
    if subset.empty:
        raise RuntimeError("Temporal diagnostics split contains no rows.")
    exact = float(subset["decision_correct"].mean())
    family = float(subset["family_correct"].mean())
    errors = subset[["growth_error", "inflation_error", "labour_error"]].to_numpy(dtype=float)
    dimension_rmse = float(np.sqrt(np.mean(np.square(errors))))
    deadzone = float(config["temporal_diagnostics"]["score_deadzone"])
    forecast_scores = subset[["forecast_growth", "forecast_inflation", "forecast_labour"]].to_numpy(dtype=float)
    actual_scores = subset[["actual_growth", "actual_inflation", "actual_labour"]].to_numpy(dtype=float)
    bucket = lambda values: np.where(values > deadzone, 1, np.where(values < -deadzone, -1, 0))
    sign_accuracy = float((bucket(forecast_scores) == bucket(actual_scores)).mean())

    stable = subset.loc[subset["stable_actual_month"]]
    changing = subset.loc[subset["actual_transition"]]
    stable_accuracy = float(stable["decision_correct"].mean()) if not stable.empty else 0.0
    transition_accuracy = float(changing["decision_correct"].mean()) if not changing.empty else 0.0

    events = transition_events(
        frame,
        dates,
        int(config["temporal_diagnostics"]["transition_matching_window_months"]),
    )
    actual_events = events.loc[events["event_type"] == "actual_transition"] if not events.empty else pd.DataFrame()
    matched = int(actual_events["matched"].sum()) if not actual_events.empty else 0
    false_count = int((events["event_type"] == "false_predicted_transition").sum()) if not events.empty else 0
    predicted_count = matched + false_count
    actual_count = len(actual_events)
    precision = matched / predicted_count if predicted_count else 0.0
    recall = matched / actual_count if actual_count else 0.0
    transition_f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    false_rate = false_count / predicted_count if predicted_count else 0.0
    matched_rows = actual_events.loc[actual_events["matched"]] if not actual_events.empty else pd.DataFrame()
    mean_lag = float(matched_rows["lead_lag_months"].mean()) if not matched_rows.empty else float("nan")
    exact_timing = float((matched_rows["lead_lag_months"] == 0).mean()) if not matched_rows.empty else 0.0

    valid_persistence = subset.loc[subset["persistence_prediction"].notna()]
    persistence_accuracy = float(valid_persistence["persistence_correct"].mean()) if not valid_persistence.empty else 0.0
    mode_regime = str(subset["actual_regime"].mode().astype(str).sort_values().iloc[0])
    mode_accuracy = float((subset["actual_regime"].astype(str) == mode_regime).mean())
    strongest = max(mode_accuracy, persistence_accuracy)
    margin = exact - strongest

    disagreements = valid_persistence.loc[
        valid_persistence["decision_regime"].astype(str)
        != valid_persistence["persistence_prediction"].astype(str)
    ]
    candidate_wins = int((disagreements["decision_correct"] & ~disagreements["persistence_correct"]).sum())
    persistence_wins = int((~disagreements["decision_correct"] & disagreements["persistence_correct"]).sum())

    occupancy = subset["decision_regime"].value_counts(normalize=True)
    entropy = -sum(value * math.log(value) for value in occupancy if value > 0)
    normalized_entropy = entropy / math.log(len(REGIMES)) if len(occupancy) > 1 else 0.0
    unique_regimes = int(subset["decision_regime"].nunique())
    maximum_share = float(occupancy.max())
    collapse = bool(
        unique_regimes < int(config["temporal_diagnostics"]["minimum_regimes_per_fold"])
        or maximum_share > float(config["temporal_diagnostics"]["maximum_regime_share"])
    )
    return {
        "months": int(len(subset)),
        "dimension_rmse": dimension_rmse,
        "sign_accuracy": sign_accuracy,
        "exact_regime_accuracy": exact,
        "family_accuracy": family,
        "stable_month_accuracy": stable_accuracy,
        "transition_month_accuracy": transition_accuracy,
        "actual_transition_count": int(actual_count),
        "predicted_transition_count": int(predicted_count),
        "matched_transition_count": int(matched),
        "false_transition_count": int(false_count),
        "transition_precision": float(precision),
        "transition_recall": float(recall),
        "transition_f1": float(transition_f1),
        "false_transition_rate": float(false_rate),
        "mean_transition_lead_lag": mean_lag,
        "exact_transition_timing_rate": exact_timing,
        "mode_accuracy": mode_accuracy,
        "persistence_accuracy": persistence_accuracy,
        "strongest_baseline_accuracy": strongest,
        "baseline_margin": margin,
        "beats_strongest_baseline": bool(margin > 0),
        "disagreement_months": int(len(disagreements)),
        "candidate_wins_disagreement": candidate_wins,
        "persistence_wins_disagreement": persistence_wins,
        "unique_regimes": unique_regimes,
        "maximum_regime_share": maximum_share,
        "normalized_regime_entropy": float(normalized_entropy),
        "regime_collapse": collapse,
        "brier_score": float(subset["decision_brier_score"].mean()),
        "log_loss": float(subset["decision_log_loss"].mean()),
        "top1_accuracy": float((subset["decision_top_regime"] == subset["actual_regime"]).mean()),
        "mean_top_probability": float(subset["decision_top_probability"].mean()),
        "mean_effective_regimes": float(subset["decision_effective_regimes"].mean()),
    }


def per_regime_metrics(frame: pd.DataFrame, dates: Iterable[date]) -> pd.DataFrame:
    subset = _subset(frame, dates)
    rows = []
    for regime in REGIMES:
        actual = subset["actual_regime"].astype(str) == regime
        predicted = subset["decision_regime"].astype(str) == regime
        true_positive = int((actual & predicted).sum())
        forecast_count = int(predicted.sum())
        support = int(actual.sum())
        precision = true_positive / forecast_count if forecast_count else 0.0
        recall = true_positive / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
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
    subset = _subset(frame, dates)
    matrix = pd.crosstab(subset["actual_regime"], subset["decision_regime"])
    matrix = matrix.reindex(index=REGIMES, columns=REGIMES, fill_value=0)
    return matrix.stack(future_stack=True).rename("count").reset_index().rename(
        columns={"decision_regime": "predicted_regime"}
    )


def target_decomposition(monthly: pd.DataFrame, dates: Iterable[date]) -> pd.DataFrame:
    subset = _subset(monthly, dates)
    rows = []
    for dimension in ("growth", "inflation", "labour"):
        forecast = pd.to_numeric(subset[f"forecast_{dimension}"])
        actual = pd.to_numeric(subset[f"actual_{dimension}"])
        error = forecast - actual
        rows.append(
            {
                "dimension": dimension,
                "months": int(len(subset)),
                "rmse": float(np.sqrt(np.mean(np.square(error)))),
                "mae": float(np.mean(np.abs(error))),
                "bias": float(np.mean(error)),
                "correlation": float(forecast.corr(actual)),
                "accuracy": float((np.sign(forecast) == np.sign(actual)).mean()),
            }
        )
    rows.extend(
        [
            {
                "dimension": "eight_regime_point_decision",
                "months": int(len(subset)),
                "rmse": None,
                "mae": None,
                "bias": None,
                "correlation": None,
                "accuracy": float((subset["forecast_regime"] == subset["actual_regime"]).mean()),
            },
            {
                "dimension": "regime_family_point_decision",
                "months": int(len(subset)),
                "rmse": None,
                "mae": None,
                "bias": None,
                "correlation": None,
                "accuracy": float((subset["forecast_family"] == subset["actual_family"]).mean()),
            },
            {
                "dimension": "probability_top1_decision",
                "months": int(len(subset)),
                "rmse": None,
                "mae": None,
                "bias": None,
                "correlation": None,
                "accuracy": float((subset["top_regime"] == subset["actual_regime"]).mean()),
            },
        ]
    )
    return pd.DataFrame(rows)

def _rank_percentile(series: pd.Series, higher: bool) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    if values.isna().any():
        raise ValueError("Temporal ranking metrics cannot contain missing values.")
    return values.rank(method="average", pct=True, ascending=higher)


def rank_fold_policies(metrics: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    frame = metrics.copy()
    weights = config["temporal_diagnostics"]["fold_score_weights"]
    directions = {
        "exact_regime_accuracy": True,
        "family_accuracy": True,
        "stable_month_accuracy": True,
        "transition_f1": True,
        "baseline_margin": True,
        "false_transition_rate": False,
    }
    score = pd.Series(0.0, index=frame.index)
    for metric, weight in weights.items():
        component = _rank_percentile(frame[metric].fillna(0.0), directions[metric])
        score += float(weight) * component
    frame["policy_score"] = 100.0 * score
    frame["policy_rank"] = frame["policy_score"].rank(method="min", ascending=False).astype(int)
    return frame.sort_values(["policy_rank", "policy_id"]).reset_index(drop=True)


def _bootstrap_margin(
    policy_frame: pd.DataFrame,
    folds: tuple[RollingFold, ...],
    fold_metrics: pd.DataFrame,
    config: dict[str, Any],
    policy_id: str,
) -> dict[str, float]:
    differences: list[np.ndarray] = []
    policy_metrics = fold_metrics.loc[fold_metrics["policy_id"] == policy_id].set_index("fold_id")
    for fold in folds:
        subset = _subset(policy_frame, fold.evaluation_dates)
        strongest = str(policy_metrics.loc[fold.fold_id, "strongest_baseline"])
        candidate_hit = subset["decision_correct"].astype(float)
        if strongest == "training_mode":
            training = _subset(policy_frame, fold.training_dates)
            mode = str(training["actual_regime"].mode().astype(str).sort_values().iloc[0])
            baseline_hit = (subset["actual_regime"].astype(str) == mode).astype(float)
        else:
            valid = subset["persistence_prediction"].notna()
            candidate_hit = candidate_hit.loc[valid]
            baseline_hit = subset.loc[valid, "persistence_correct"].astype(float)
        differences.append((candidate_hit - baseline_hit).to_numpy(dtype=float))
    section = config["temporal_diagnostics"]
    return block_bootstrap_margin_ci(
        differences,
        repetitions=int(section["bootstrap_repetitions"]),
        block_months=int(section["bootstrap_block_months"]),
        confidence=float(section["bootstrap_confidence"]),
        seed=int(section["random_seed"]) + sum(ord(char) for char in policy_id),
    )


def run_temporal_policy_diagnostics(
    monthly: pd.DataFrame,
    plan: RollingTournamentPlan,
    config: dict[str, Any],
) -> dict[str, Any]:
    policy_frames = {
        policy_id: apply_temporal_policy(monthly, policy_id, config)
        for policy_id in TEMPORAL_POLICIES
    }
    fold_parts = []
    for fold in plan.folds:
        rows = []
        for policy_id, frame in policy_frames.items():
            metrics = decision_metrics(frame, fold.evaluation_dates, config)
            strongest = (
                "training_mode"
                if metrics["mode_accuracy"] >= metrics["persistence_accuracy"]
                else "persistence"
            )
            rows.append(
                {
                    "fold_id": fold.fold_id,
                    "policy_id": policy_id,
                    "evaluation_start": fold.evaluation_dates[0],
                    "evaluation_end": fold.evaluation_dates[-1],
                    "evaluation_months": len(fold.evaluation_dates),
                    "strongest_baseline": strongest,
                    **metrics,
                }
            )
        fold_parts.append(rank_fold_policies(pd.DataFrame(rows), config))
    fold_metrics = pd.concat(fold_parts, ignore_index=True)

    aggregate_rows = []
    policy_count = len(TEMPORAL_POLICIES)
    for policy_id, frame in fold_metrics.groupby("policy_id"):
        ranks = frame["policy_rank"].astype(float)
        aggregate_rows.append(
            {
                "policy_id": str(policy_id),
                "folds": int(len(frame)),
                "mean_fold_score": float(frame["policy_score"].mean()),
                "median_fold_score": float(frame["policy_score"].median()),
                "mean_fold_rank": float(ranks.mean()),
                "median_fold_rank": float(ranks.median()),
                "rank_std": float(ranks.std(ddof=0)),
                "rank_stability": float(
                    max(0.0, 1.0 - ranks.std(ddof=0) / max(policy_count - 1, 1))
                ),
                "best_fold_rank": int(ranks.min()),
                "worst_fold_rank": int(ranks.max()),
                "fold_win_rate": float((ranks == 1).mean()),
                "baseline_dominance_rate": float(frame["beats_strongest_baseline"].mean()),
                "mean_baseline_margin": float(frame["baseline_margin"].mean()),
                "mean_exact_regime_accuracy": float(frame["exact_regime_accuracy"].mean()),
                "mean_family_accuracy": float(frame["family_accuracy"].mean()),
                "mean_stable_month_accuracy": float(frame["stable_month_accuracy"].mean()),
                "mean_transition_month_accuracy": float(frame["transition_month_accuracy"].mean()),
                "mean_transition_precision": float(frame["transition_precision"].mean()),
                "mean_transition_recall": float(frame["transition_recall"].mean()),
                "mean_transition_f1": float(frame["transition_f1"].mean()),
                "mean_false_transition_rate": float(frame["false_transition_rate"].mean()),
                "regime_collapse_fold_rate": float(frame["regime_collapse"].mean()),
                **_bootstrap_margin(policy_frames[str(policy_id)], plan.folds, fold_metrics, config, str(policy_id)),
            }
        )
    aggregate = pd.DataFrame(aggregate_rows)
    weights = config["temporal_diagnostics"]["stability_score_weights"]
    directions = {
        "mean_fold_score": True,
        "median_fold_score": True,
        "rank_stability": True,
        "baseline_dominance_rate": True,
        "mean_transition_f1": True,
    }
    score = pd.Series(0.0, index=aggregate.index)
    for metric, weight in weights.items():
        score += float(weight) * _rank_percentile(aggregate[metric], directions[metric])
    aggregate["stability_score"] = 100.0 * score
    aggregate["stability_rank"] = aggregate["stability_score"].rank(method="min", ascending=False).astype(int)

    audit_rows = []
    for policy_id, frame in policy_frames.items():
        audit_rows.append({"policy_id": policy_id, **decision_metrics(frame, plan.audit_dates, config)})
    audit = rank_fold_policies(pd.DataFrame(audit_rows), config).rename(
        columns={"policy_score": "audit_score", "policy_rank": "audit_rank"}
    )
    aggregate = aggregate.merge(
        audit[[
            "policy_id", "audit_score", "audit_rank", "exact_regime_accuracy",
            "family_accuracy", "transition_f1", "baseline_margin", "false_transition_rate",
        ]].rename(
            columns={
                "exact_regime_accuracy": "audit_exact_regime_accuracy",
                "family_accuracy": "audit_family_accuracy",
                "transition_f1": "audit_transition_f1",
                "baseline_margin": "audit_baseline_margin",
                "false_transition_rate": "audit_false_transition_rate",
            }
        ),
        on="policy_id",
        how="left",
    )
    gate = config["temporal_diagnostics"]["governance"]
    aggregate["governance_pass"] = (
        (aggregate["baseline_dominance_rate"] >= float(gate["minimum_baseline_dominance_rate"]))
        & (aggregate["mean_family_accuracy"] >= float(gate["minimum_family_accuracy"]))
        & (aggregate["mean_transition_recall"] >= float(gate["minimum_transition_recall"]))
        & (aggregate["mean_false_transition_rate"] <= float(gate["maximum_false_transition_rate"]))
        & (aggregate["regime_collapse_fold_rate"] <= float(gate["maximum_regime_collapse_fold_rate"]))
        & (aggregate["bootstrap_margin_lower"] > float(gate["minimum_bootstrap_margin_lower"]))
    )
    aggregate = aggregate.sort_values(["stability_rank", "policy_id"]).reset_index(drop=True)
    return {
        "policy_frames": policy_frames,
        "fold_metrics": fold_metrics,
        "policy_stability": aggregate,
        "audit": audit,
    }
