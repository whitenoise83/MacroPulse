from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.prospective_shadow import (
    REQUIRED_BENCHMARKS,
    canonical_json,
    prospective_shadow_plan,
    sha256_json,
)
from macropulse.macro_state.realtime_soft_targets import (
    _definition_map,
    _target_actual_from_frame,
    soft_actual_distribution,
)
from macropulse.macro_state.shadow_outcomes import (
    build_outcome_rows,
    target_hash,
)
from macropulse.macro_state.tournament import (
    ALL_TARGETS,
    GDP_TARGET,
    build_core_candidates,
    candidate_monthly_states,
    load_tournament_dataset,
)
from macropulse.macro_state.versioning import load_macro_state_governance
from macropulse.settings import settings


def _utc_now_naive() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC").tz_localize(None)


def _today() -> date:
    return date.today()


def _period(target: str, value: Any) -> pd.Period:
    return pd.Period(str(value), freq="Q" if target == GDP_TARGET else "M")


def _period_ordinal(target: str, value: Any) -> int:
    return int(_period(target, value).ordinal)


def _component_evaluation_date(
    target: str,
    target_period: Any,
    horizon_days: int,
) -> date:
    return _period(target, target_period).end_time.normalize().date() + timedelta(
        days=int(horizon_days)
    )


def _eligible_shadow_runs(
    repository: MacroRepository,
    *,
    resolution_as_of: date,
    shadow_run_id: str | None,
) -> pd.DataFrame:
    parameters: list[Any] = []
    where = [
        "r.status = 'predicted'",
        "NOT EXISTS (SELECT 1 FROM macro_state_shadow_outcomes o "
        "WHERE o.shadow_run_id = r.shadow_run_id)",
    ]
    if shadow_run_id is not None:
        where.append("r.shadow_run_id = ?")
        parameters.append(str(shadow_run_id))
    else:
        where.append("r.target_expected_available_date <= ?")
        parameters.append(resolution_as_of)
    return repository.query_df(
        f"""
        SELECT r.*
        FROM macro_state_shadow_runs r
        WHERE {' AND '.join(where)}
        ORDER BY r.state_date, r.created_at, r.shadow_run_id
        """,
        parameters,
    )


def _prediction_rows(
    repository: MacroRepository,
    shadow_run_id: str,
) -> pd.DataFrame:
    frame = repository.query_df(
        """
        SELECT *
        FROM macro_state_shadow_predictions
        WHERE shadow_run_id = ?
        ORDER BY benchmark_id
        """,
        [shadow_run_id],
    )
    if len(frame) != 2 or set(frame["benchmark_id"].astype(str)) != set(
        REQUIRED_BENCHMARKS
    ):
        raise ValueError(
            "Exactly the source and rolling_frequency predictions must exist "
            "before resolution"
        )
    return frame


def _source_inputs(
    repository: MacroRepository,
    source_macro_state_run_id: str,
) -> pd.DataFrame:
    frame = repository.query_df(
        """
        SELECT source_target, target_period, point_forecast, lower_80,
               upper_80, source_model_id, source_model_version,
               source_run_id, information_cutoff, data_as_of, source_hash
        FROM macro_state_inputs
        WHERE run_id = ?
        ORDER BY source_target
        """,
        [source_macro_state_run_id],
    )
    if frame.empty:
        raise ValueError(
            "The persisted source macro-state run has no input lineage"
        )
    observed = set(frame["source_target"].astype(str))
    if observed != set(ALL_TARGETS):
        raise ValueError(
            "The source macro-state run must contain all eight governed targets; "
            f"observed={sorted(observed)}"
        )
    if frame["source_target"].astype(str).duplicated().any():
        raise ValueError("Source macro-state target rows must be unique")
    return frame.reset_index(drop=True)


def _latest_snapshot_date(
    repository: MacroRepository,
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


def _fixed_actual_value(
    repository: MacroRepository,
    *,
    target: str,
    target_period: pd.Period,
    evaluation_date: date,
    release_date: date | None,
    maximum_snapshot_gap_days: int,
    definitions: Mapping[str, Any],
    snapshot_cache: dict[tuple[str, date], pd.DataFrame] | None = None,
) -> dict[str, Any]:
    snapshot_date = _latest_snapshot_date(
        repository,
        target=target,
        release_date=release_date,
        evaluation_date=evaluation_date,
    )
    if snapshot_date is None:
        return {
            "availability_status": "missing_snapshot",
            "detail": "no eligible historical snapshot is cached",
        }
    gap_days = int((evaluation_date - snapshot_date).days)
    if gap_days > int(maximum_snapshot_gap_days):
        return {
            "availability_status": "snapshot_too_stale",
            "detail": (
                f"snapshot gap {gap_days} exceeds governed maximum "
                f"{maximum_snapshot_gap_days}"
            ),
            "snapshot_date": snapshot_date,
            "snapshot_gap_days": gap_days,
        }
    cache = snapshot_cache if snapshot_cache is not None else {}
    cache_key = (target, snapshot_date)
    if cache_key not in cache:
        cache[cache_key] = repository.historical_snapshot(
            snapshot_date, [target]
        )
    try:
        actual_value = _target_actual_from_frame(
            cache[cache_key],
            target=target,
            target_period=target_period,
            definitions=dict(definitions),
        )
    except (KeyError, TypeError, ValueError) as exc:
        return {
            "availability_status": "transformation_unavailable",
            "detail": str(exc),
            "snapshot_date": snapshot_date,
            "snapshot_gap_days": gap_days,
        }
    if not np.isfinite(float(actual_value)):
        return {
            "availability_status": "non_finite_actual",
            "detail": "transformed actual is not finite",
            "snapshot_date": snapshot_date,
            "snapshot_gap_days": gap_days,
        }
    return {
        "availability_status": "available",
        "snapshot_date": snapshot_date,
        "snapshot_gap_days": gap_days,
        "actual_value": float(actual_value),
    }


def _resolve_target_components(
    repository: MacroRepository,
    *,
    source_inputs: pd.DataFrame,
    resolution_as_of: date,
    horizon_days: int,
    maximum_snapshot_gap_days: int,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    definitions = _definition_map()
    snapshot_cache: dict[tuple[str, date], pd.DataFrame] = {}
    rows: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for source in source_inputs.sort_values("source_target").itertuples(
        index=False
    ):
        target = str(source.source_target)
        target_period = _period(target, source.target_period)
        evaluation_date = _component_evaluation_date(
            target,
            target_period,
            horizon_days,
        )
        base = {
            "source_target": target,
            "target_period": str(target_period),
            "requested_evaluation_date": evaluation_date,
        }
        if resolution_as_of < evaluation_date:
            unresolved.append(
                {
                    **base,
                    "availability_status": "not_yet_due",
                    "detail": (
                        f"resolution cutoff {resolution_as_of} precedes "
                        f"component evaluation date {evaluation_date}"
                    ),
                }
            )
            continue

        release_date = repository.initial_release_date(target, target_period)
        fixed = _fixed_actual_value(
            repository,
            target=target,
            target_period=target_period,
            evaluation_date=evaluation_date,
            release_date=release_date,
            maximum_snapshot_gap_days=maximum_snapshot_gap_days,
            definitions=definitions,
            snapshot_cache=snapshot_cache,
        )
        if fixed["availability_status"] != "available":
            unresolved.append({**base, **fixed})
            continue
        rows.append(
            {
                **base,
                "release_date": release_date,
                **fixed,
            }
        )
    return pd.DataFrame(rows), unresolved


def _fixed_horizon_history(
    repository: MacroRepository,
    *,
    historical: pd.DataFrame,
    horizon_days: int,
    maximum_snapshot_gap_days: int,
) -> pd.DataFrame:
    definitions = _definition_map()
    snapshot_cache: dict[tuple[str, date], pd.DataFrame] = {}
    value_cache: dict[tuple[str, str], dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    ordered = historical.sort_values(
        ["state_date", "source_target", "target_period"]
    )
    for row in ordered.itertuples(index=False):
        target = str(row.source_target)
        target_period = _period(target, row.target_period)
        key = (target, str(target_period))
        if key not in value_cache:
            evaluation_date = _component_evaluation_date(
                target, target_period, horizon_days
            )
            release_raw = getattr(row, "actual_release_date", None)
            release_date = (
                pd.Timestamp(release_raw).date()
                if release_raw is not None and pd.notna(release_raw)
                else repository.initial_release_date(target, target_period)
            )
            value_cache[key] = _fixed_actual_value(
                repository,
                target=target,
                target_period=target_period,
                evaluation_date=evaluation_date,
                release_date=release_date,
                maximum_snapshot_gap_days=maximum_snapshot_gap_days,
                definitions=definitions,
                snapshot_cache=snapshot_cache,
            )
        fixed = value_cache[key]
        if fixed["availability_status"] != "available":
            continue
        record = row._asdict()
        record["actual"] = float(fixed["actual_value"])
        rows.append(record)
    if not rows:
        raise ValueError(
            "No fixed-horizon historical states are available for target "
            "normalisation"
        )
    frame = pd.DataFrame(rows)
    counts = frame.groupby("state_date")["source_target"].nunique()
    complete_dates = set(counts.loc[counts == len(ALL_TARGETS)].index)
    frame = frame.loc[frame["state_date"].isin(complete_dates)].copy()
    if frame.empty:
        raise ValueError(
            "No complete fixed-horizon historical states contain all eight "
            "targets"
        )
    return frame.sort_values(
        ["state_date", "source_target"]
    ).reset_index(drop=True)

def _source_core_candidate(
    config: Mapping[str, Any],
    core_candidate_id: str,
) -> dict[str, Any]:
    candidates = {
        str(item["candidate_id"]): item
        for item in build_core_candidates(dict(config))
    }
    if core_candidate_id not in candidates:
        raise ValueError(
            f"Frozen source core candidate is absent: {core_candidate_id}"
        )
    return candidates[core_candidate_id]


def _actual_target_from_components(
    repository: MacroRepository,
    *,
    shadow_run: Mapping[str, Any],
    source_inputs: pd.DataFrame,
    components: pd.DataFrame,
    config: dict[str, Any],
    core_candidate_id: str,
    horizon_days: int,
    maximum_snapshot_gap_days: int,
) -> dict[str, Any]:
    _, historical = load_tournament_dataset(repository)
    state_date = pd.Timestamp(shadow_run["state_date"]).date()
    historical = historical.loc[
        pd.to_datetime(historical["state_date"]).dt.date < state_date
    ].copy()
    historical = _fixed_horizon_history(
        repository,
        historical=historical,
        horizon_days=horizon_days,
        maximum_snapshot_gap_days=maximum_snapshot_gap_days,
    )

    actual_by_target = components.set_index("source_target")["actual_value"]
    current = source_inputs.copy()
    current["state_date"] = state_date
    current["actual"] = current["source_target"].astype(str).map(
        actual_by_target
    )
    current["target_period_ordinal"] = current.apply(
        lambda row: _period_ordinal(
            str(row["source_target"]), row["target_period"]
        ),
        axis=1,
    )
    required = [
        "state_date",
        "source_target",
        "target_period",
        "target_period_ordinal",
        "point_forecast",
        "lower_80",
        "upper_80",
        "actual",
    ]
    if current[required].isna().any().any():
        raise ValueError("Current fixed-horizon target dataset is incomplete")
    combined = pd.concat(
        [historical[required], current[required]],
        ignore_index=True,
    )
    for column in ("point_forecast", "lower_80", "upper_80", "actual"):
        combined[column] = pd.to_numeric(combined[column], errors="raise")

    candidate = _source_core_candidate(config, core_candidate_id)
    monthly = candidate_monthly_states(combined, candidate, config)
    resolved = monthly.loc[
        pd.to_datetime(monthly["state_date"]).dt.date == state_date
    ]
    if len(resolved) != 1:
        raise ValueError(
            "The fixed-horizon target must resolve to exactly one monthly state"
        )
    row = resolved.iloc[0]
    actual_dimensions = {
        "growth": float(row["actual_growth"]),
        "inflation": float(row["actual_inflation"]),
        "labour": float(row["actual_labour"]),
    }
    soft = soft_actual_distribution(
        actual_dimensions["growth"],
        actual_dimensions["inflation"],
        actual_dimensions["labour"],
        config,
    )
    return {
        "actual_dimensions": actual_dimensions,
        "actual_family": str(soft["primary_family"]),
        "actual_probabilities": {
            str(key): float(value)
            for key, value in __import__("json").loads(
                soft["family_probabilities_json"]
            ).items()
        },
        "actual_confidence": float(soft["family_top_probability"]),
        "secondary_regime": str(soft["secondary_regime"]),
        "ambiguity_indicator": bool(soft["ambiguity_indicator"]),
    }


def _previous_actual_family(
    repository: MacroRepository,
    *,
    model_version: str,
    state_date: date,
) -> str | None:
    frame = repository.query_df(
        """
        SELECT actual_family
        FROM macro_state_shadow_outcomes
        WHERE model_version = ?
          AND benchmark_id = 'source'
          AND state_date < ?
        ORDER BY state_date DESC, resolved_at DESC
        LIMIT 1
        """,
        [model_version, state_date],
    )
    if frame.empty:
        return None
    return str(frame.iloc[0]["actual_family"])


def _resolve_one(
    repository: MacroRepository,
    *,
    shadow_run: Mapping[str, Any],
    resolution_as_of: date,
    resolved_at: pd.Timestamp,
    config: dict[str, Any],
) -> dict[str, Any]:
    plan = prospective_shadow_plan(config)
    if str(shadow_run["model_version"]) != plan.model_version:
        raise ValueError("Shadow run model version does not match governance")
    if str(shadow_run["target_mode"]) != plan.target_mode:
        raise ValueError("Shadow run target mode does not match governance")
    if int(shadow_run["target_horizon_days"]) != plan.target_horizon_days:
        raise ValueError("Shadow run target horizon does not match governance")

    source_inputs = _source_inputs(
        repository,
        str(shadow_run["source_macro_state_run_id"]),
    )
    components, unresolved = _resolve_target_components(
        repository,
        source_inputs=source_inputs,
        resolution_as_of=resolution_as_of,
        horizon_days=plan.target_horizon_days,
        maximum_snapshot_gap_days=int(
            config["real_time_soft_targets"]["maximum_snapshot_gap_days"]
        ),
    )
    strict_available_date = max(
        _component_evaluation_date(
            str(row.source_target),
            row.target_period,
            plan.target_horizon_days,
        )
        for row in source_inputs.itertuples(index=False)
    )
    if unresolved or len(components) != len(ALL_TARGETS):
        return {
            "status": "unresolved",
            "shadow_run_id": str(shadow_run["shadow_run_id"]),
            "state_date": pd.Timestamp(shadow_run["state_date"]).date(),
            "persisted_expected_available_date": pd.Timestamp(
                shadow_run["target_expected_available_date"]
            ).date(),
            "strict_target_available_date": strict_available_date,
            "unresolved_components": unresolved,
        }
    if resolution_as_of < strict_available_date:
        return {
            "status": "unresolved",
            "shadow_run_id": str(shadow_run["shadow_run_id"]),
            "state_date": pd.Timestamp(shadow_run["state_date"]).date(),
            "persisted_expected_available_date": pd.Timestamp(
                shadow_run["target_expected_available_date"]
            ).date(),
            "strict_target_available_date": strict_available_date,
            "unresolved_components": [
                {
                    "availability_status": "strict_target_not_yet_due",
                    "detail": (
                        f"resolution cutoff {resolution_as_of} precedes "
                        f"strict target availability {strict_available_date}"
                    ),
                }
            ],
        }

    actual = _actual_target_from_components(
        repository,
        shadow_run=shadow_run,
        source_inputs=source_inputs,
        components=components,
        config=config,
        core_candidate_id=plan.source_core_candidate_id,
        horizon_days=plan.target_horizon_days,
        maximum_snapshot_gap_days=int(
            config["real_time_soft_targets"]["maximum_snapshot_gap_days"]
        ),
    )
    target_payload_hash = target_hash(
        state_date=pd.Timestamp(shadow_run["state_date"]).date(),
        target_mode=plan.target_mode,
        target_horizon_days=plan.target_horizon_days,
        target_available_date=strict_available_date,
        target_components=components,
        actual_dimensions=actual["actual_dimensions"],
        actual_family=actual["actual_family"],
        actual_probabilities=actual["actual_probabilities"],
        actual_confidence=actual["actual_confidence"],
        plan=plan,
    )
    component_hash = sha256_json(
        components.sort_values(["source_target", "target_period"])[
            [
                "source_target",
                "target_period",
                "requested_evaluation_date",
                "snapshot_date",
                "snapshot_gap_days",
                "actual_value",
            ]
        ].to_dict("records")
    )
    target_vintage_id = f"fixed_horizon_90d:{component_hash}"
    previous = _previous_actual_family(
        repository,
        model_version=str(shadow_run["model_version"]),
        state_date=pd.Timestamp(shadow_run["state_date"]).date(),
    )
    predictions = _prediction_rows(
        repository,
        str(shadow_run["shadow_run_id"]),
    )
    outcomes = build_outcome_rows(
        shadow_run=shadow_run,
        predictions=predictions,
        resolved_at=resolved_at,
        target_available_date=strict_available_date,
        target_vintage_id=target_vintage_id,
        actual_family=actual["actual_family"],
        actual_probabilities=actual["actual_probabilities"],
        actual_confidence=actual["actual_confidence"],
        previous_actual_family=previous,
        target_hash_value=target_payload_hash,
        log_loss_floor=float(
            config["prospective_transition_shadow"]["probability_contract"][
                "log_loss_floor"
            ]
        ),
        plan=plan,
    )
    repository.save_macro_state_shadow_outcomes(outcomes)
    return {
        "status": "resolved",
        "shadow_run_id": str(shadow_run["shadow_run_id"]),
        "state_date": pd.Timestamp(shadow_run["state_date"]).date(),
        "persisted_expected_available_date": pd.Timestamp(
            shadow_run["target_expected_available_date"]
        ).date(),
        "strict_target_available_date": strict_available_date,
        "target_vintage_id": target_vintage_id,
        "target_hash": target_payload_hash,
        "actual_family": actual["actual_family"],
        "actual_confidence": actual["actual_confidence"],
        "actual_probabilities_json": canonical_json(
            actual["actual_probabilities"]
        ),
        "actual_dimensions": actual["actual_dimensions"],
        "secondary_regime": actual["secondary_regime"],
        "ambiguity_indicator": actual["ambiguity_indicator"],
        "outcomes": outcomes,
        "components": components,
    }


def resolve_macro_state_shadow_outcomes(
    repository: MacroRepository | None = None,
    *,
    as_of: date | None = None,
    shadow_run_id: str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    repository = repository or MacroRepository()
    repository.initialise()
    root = Path(project_root or settings.project_root)
    config = load_macro_state_governance(root)
    plan = prospective_shadow_plan(config)
    resolution_as_of = as_of or _today()
    if resolution_as_of > _today():
        raise ValueError(
            "Outcome resolution cutoff cannot be later than the current date"
        )
    resolved_at = _utc_now_naive()
    if resolved_at.date() < resolution_as_of:
        raise ValueError(
            "Resolution timestamp cannot precede the resolution cutoff"
        )

    candidates = _eligible_shadow_runs(
        repository,
        resolution_as_of=resolution_as_of,
        shadow_run_id=shadow_run_id,
    )
    resolved_records: list[dict[str, Any]] = []
    unresolved_records: list[dict[str, Any]] = []
    for row in candidates.to_dict("records"):
        result = _resolve_one(
            repository,
            shadow_run=row,
            resolution_as_of=resolution_as_of,
            resolved_at=resolved_at,
            config=config,
        )
        if result["status"] == "resolved":
            resolved_records.append(result)
        else:
            unresolved_records.append(result)

    resolved_summary = pd.DataFrame(
        [
            {
                "shadow_run_id": item["shadow_run_id"],
                "state_date": item["state_date"],
                "strict_target_available_date": item[
                    "strict_target_available_date"
                ],
                "actual_family": item["actual_family"],
                "actual_confidence": item["actual_confidence"],
                "target_vintage_id": item["target_vintage_id"],
                "target_hash": item["target_hash"],
            }
            for item in resolved_records
        ]
    )
    unresolved_summary = pd.DataFrame(
        [
            {
                "shadow_run_id": item["shadow_run_id"],
                "state_date": item["state_date"],
                "persisted_expected_available_date": item[
                    "persisted_expected_available_date"
                ],
                "strict_target_available_date": item[
                    "strict_target_available_date"
                ],
                "unresolved_components_json": canonical_json(
                    item["unresolved_components"]
                ),
            }
            for item in unresolved_records
        ]
    )
    return {
        "model_version": plan.model_version,
        "resolution_as_of": resolution_as_of,
        "eligible_runs": int(len(candidates)),
        "resolved_runs": int(len(resolved_records)),
        "unresolved_runs": int(len(unresolved_records)),
        "outcome_rows_appended": int(2 * len(resolved_records)),
        "resolved": resolved_summary,
        "unresolved": unresolved_summary,
        "details": resolved_records,
        "promotion_authority": "none",
    }
