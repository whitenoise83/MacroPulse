from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.evaluation.ledger import collect_governed_forecasts
from macropulse.platform.status import component_specs


REVISION_SCHEMA_VERSION = "1.0.0"
ASSOCIATION_TYPE = "scheduled_release_between_governed_cutoffs"
CAUSALITY_CLAIM = False

REVISION_COLUMNS = [
    "revision_id",
    "component",
    "model_id",
    "model_version",
    "target_series",
    "target_name",
    "target_period",
    "comparison_status",
    "current_run_id",
    "current_information_cutoff",
    "current_data_as_of",
    "current_forecast_stage",
    "current_forecast_value",
    "current_lower_80",
    "current_upper_80",
    "current_interval_width",
    "previous_run_id",
    "previous_information_cutoff",
    "previous_data_as_of",
    "previous_forecast_stage",
    "previous_forecast_value",
    "previous_lower_80",
    "previous_upper_80",
    "previous_interval_width",
    "first_run_id",
    "first_information_cutoff",
    "first_forecast_value",
    "revision",
    "absolute_revision",
    "revision_direction",
    "cumulative_revision",
    "absolute_cumulative_revision",
    "lower_80_revision",
    "upper_80_revision",
    "interval_width_revision",
    "stage_changed",
    "days_between_runs",
    "associated_release_count",
    "advanced_source_release_count",
    "release_association_state",
    "associated_release_labels",
]

RELEASE_EVENT_COLUMNS = [
    "revision_id",
    "component",
    "target_series",
    "target_period",
    "previous_run_id",
    "current_run_id",
    "previous_information_cutoff",
    "current_information_cutoff",
    "release_date",
    "series_id",
    "release_id",
    "release_name",
    "previous_latest_observation_date",
    "current_latest_observation_date",
    "information_set_advanced",
    "association_type",
    "causality_claim",
]


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    result = float(value)
    if not np.isfinite(result):
        return None
    return result


def _to_date(value: Any) -> date | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return pd.Timestamp(value).date()


def _difference(current: Any, previous: Any) -> float | None:
    current_value = _to_float(current)
    previous_value = _to_float(previous)
    if current_value is None or previous_value is None:
        return None
    return float(current_value - previous_value)


def _direction(value: float | None) -> str | None:
    if value is None:
        return None
    if value > 0:
        return "upward"
    if value < 0:
        return "downward"
    return "unchanged"


def _hash_revision_identity(
    *,
    component: str,
    target_series: str,
    target_period: str,
    current_run_id: str,
) -> str:
    text = "|".join(
        [component, target_series, target_period, current_run_id]
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_revision_table(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Build deterministic sequential revisions within identical targets.

    Comparable identity is strictly:
      component + target_series + target_period

    A target-period change starts a new baseline and is never treated as a
    revision of the prior target period.
    """
    if forecasts.empty:
        return pd.DataFrame(columns=REVISION_COLUMNS)

    required = {
        "component",
        "run_id",
        "model_id",
        "model_version",
        "information_cutoff",
        "data_as_of",
        "target_series",
        "target_name",
        "target_period",
        "forecast_stage",
        "forecast_value",
        "lower_80",
        "upper_80",
        "created_at",
    }
    missing = sorted(required - set(forecasts.columns))
    if missing:
        raise ValueError(
            "Phase 3D forecast input is missing required columns: "
            + ", ".join(missing)
        )

    frame = forecasts.copy()
    frame["information_cutoff"] = pd.to_datetime(
        frame["information_cutoff"],
        errors="coerce",
    )
    frame["created_at"] = pd.to_datetime(
        frame["created_at"],
        errors="coerce",
    )
    if frame["information_cutoff"].isna().any():
        raise ValueError(
            "Phase 3D refuses forecasts with missing information cutoff."
        )

    frame = frame.sort_values(
        [
            "component",
            "target_series",
            "target_period",
            "information_cutoff",
            "created_at",
            "run_id",
        ],
        kind="stable",
    ).reset_index(drop=True)

    records: list[dict[str, Any]] = []
    group_columns = ["component", "target_series", "target_period"]

    for _, group in frame.groupby(group_columns, sort=True):
        ordered = group.reset_index(drop=True)
        first = ordered.iloc[0]

        for index, current in ordered.iterrows():
            previous = ordered.iloc[index - 1] if index > 0 else None

            current_value = _to_float(current["forecast_value"])
            first_value = _to_float(first["forecast_value"])
            current_lower = _to_float(current["lower_80"])
            current_upper = _to_float(current["upper_80"])
            current_width = (
                float(current_upper - current_lower)
                if current_lower is not None and current_upper is not None
                else None
            )

            if previous is None:
                comparison_status = "baseline_no_previous"
                previous_run_id = None
                previous_cutoff = None
                previous_data_as_of = None
                previous_stage = None
                previous_value = None
                previous_lower = None
                previous_upper = None
                previous_width = None
                revision = None
                absolute_revision = None
                revision_direction = None
                lower_revision = None
                upper_revision = None
                width_revision = None
                stage_changed = None
                days_between = None
            else:
                comparison_status = "comparable_revision"
                previous_run_id = str(previous["run_id"])
                previous_cutoff = _to_date(previous["information_cutoff"])
                previous_data_as_of = _to_date(previous["data_as_of"])
                previous_stage = (
                    None
                    if pd.isna(previous["forecast_stage"])
                    else str(previous["forecast_stage"])
                )
                previous_value = _to_float(previous["forecast_value"])
                previous_lower = _to_float(previous["lower_80"])
                previous_upper = _to_float(previous["upper_80"])
                previous_width = (
                    float(previous_upper - previous_lower)
                    if previous_lower is not None and previous_upper is not None
                    else None
                )
                revision = _difference(current_value, previous_value)
                absolute_revision = (
                    abs(revision) if revision is not None else None
                )
                revision_direction = _direction(revision)
                lower_revision = _difference(current_lower, previous_lower)
                upper_revision = _difference(current_upper, previous_upper)
                width_revision = _difference(current_width, previous_width)
                current_stage = (
                    None
                    if pd.isna(current["forecast_stage"])
                    else str(current["forecast_stage"])
                )
                stage_changed = bool(current_stage != previous_stage)
                current_cutoff = _to_date(current["information_cutoff"])
                days_between = (
                    int((current_cutoff - previous_cutoff).days)
                    if current_cutoff is not None
                    and previous_cutoff is not None
                    else None
                )

            cumulative_revision = _difference(current_value, first_value)
            absolute_cumulative = (
                abs(cumulative_revision)
                if cumulative_revision is not None
                else None
            )

            component = str(current["component"])
            target_series = str(current["target_series"])
            target_period = str(current["target_period"])
            current_run_id = str(current["run_id"])

            records.append(
                {
                    "revision_id": _hash_revision_identity(
                        component=component,
                        target_series=target_series,
                        target_period=target_period,
                        current_run_id=current_run_id,
                    ),
                    "component": component,
                    "model_id": str(current["model_id"]),
                    "model_version": str(current["model_version"]),
                    "target_series": target_series,
                    "target_name": str(current["target_name"]),
                    "target_period": target_period,
                    "comparison_status": comparison_status,
                    "current_run_id": current_run_id,
                    "current_information_cutoff": _to_date(
                        current["information_cutoff"]
                    ),
                    "current_data_as_of": _to_date(current["data_as_of"]),
                    "current_forecast_stage": (
                        None
                        if pd.isna(current["forecast_stage"])
                        else str(current["forecast_stage"])
                    ),
                    "current_forecast_value": current_value,
                    "current_lower_80": current_lower,
                    "current_upper_80": current_upper,
                    "current_interval_width": current_width,
                    "previous_run_id": previous_run_id,
                    "previous_information_cutoff": previous_cutoff,
                    "previous_data_as_of": previous_data_as_of,
                    "previous_forecast_stage": previous_stage,
                    "previous_forecast_value": previous_value,
                    "previous_lower_80": previous_lower,
                    "previous_upper_80": previous_upper,
                    "previous_interval_width": previous_width,
                    "first_run_id": str(first["run_id"]),
                    "first_information_cutoff": _to_date(
                        first["information_cutoff"]
                    ),
                    "first_forecast_value": first_value,
                    "revision": revision,
                    "absolute_revision": absolute_revision,
                    "revision_direction": revision_direction,
                    "cumulative_revision": cumulative_revision,
                    "absolute_cumulative_revision": absolute_cumulative,
                    "lower_80_revision": lower_revision,
                    "upper_80_revision": upper_revision,
                    "interval_width_revision": width_revision,
                    "stage_changed": stage_changed,
                    "days_between_runs": days_between,
                    "associated_release_count": 0,
                    "advanced_source_release_count": 0,
                    "release_association_state": (
                        "baseline_no_previous"
                        if previous is None
                        else "unassessed"
                    ),
                    "associated_release_labels": "",
                }
            )

    # Records are already emitted deterministically:
    #   group identity is sorted by groupby(sort=True), and
    #   runs within each comparable group are ordered by
    #   information_cutoff -> created_at -> run_id.
    #
    # Do not re-sort by current_run_id here. A second sort would destroy the
    # governed within-cutoff chronology for multiple runs sharing the same
    # information cutoff.
    return pd.DataFrame.from_records(
        records,
        columns=REVISION_COLUMNS,
    ).reset_index(drop=True)


def _information_set_summary(
    repository: MacroRepository,
    *,
    table: str,
    run_id: str,
) -> pd.DataFrame:
    return repository.query_df(
        f"""
        SELECT series_id, MAX(observation_date) AS latest_observation_date
        FROM {table}
        WHERE run_id = ?
        GROUP BY series_id
        ORDER BY series_id
        """,
        [run_id],
    )


def _scheduled_releases(
    repository: MacroRepository,
    *,
    series_ids: list[str],
    start_exclusive: date,
    end_inclusive: date,
) -> pd.DataFrame:
    columns = ["series_id", "release_id", "release_name", "release_date"]
    if not series_ids or end_inclusive <= start_exclusive:
        return pd.DataFrame(columns=columns)

    placeholders = ", ".join(["?"] * len(series_ids))
    frame = repository.query_df(
        f"""
        SELECT series_id, release_id, release_name, release_date
        FROM release_calendar
        WHERE series_id IN ({placeholders})
          AND release_date > ?
          AND release_date <= ?
        ORDER BY release_date, series_id, release_id
        """,
        [*series_ids, start_exclusive, end_inclusive],
    )
    if frame.empty:
        return pd.DataFrame(columns=columns)
    return (
        frame.drop_duplicates(
            subset=["series_id", "release_id", "release_date"]
        )
        .sort_values(
            ["release_date", "series_id", "release_id"],
            kind="stable",
        )
        .reset_index(drop=True)
    )


def _latest_observation_map(frame: pd.DataFrame) -> dict[str, date | None]:
    if frame.empty:
        return {}
    return {
        str(row.series_id): _to_date(row.latest_observation_date)
        for row in frame.itertuples(index=False)
    }


def _source_advanced(
    *,
    series_id: str,
    previous: dict[str, date | None],
    current: dict[str, date | None],
) -> bool:
    current_date = current.get(series_id)
    previous_date = previous.get(series_id)
    if current_date is None:
        return False
    if previous_date is None:
        return True
    return bool(current_date > previous_date)


def associate_scheduled_releases(
    repository: MacroRepository,
    revisions: pd.DataFrame,
    *,
    project_root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Associate scheduled source releases with comparable forecast revisions.

    This is descriptive temporal association only. It is not causal
    attribution. A separate flag records whether the source's maximum
    observation date actually advanced between the two governed information
    sets.
    """
    if revisions.empty:
        return (
            pd.DataFrame(columns=REVISION_COLUMNS),
            pd.DataFrame(columns=RELEASE_EVENT_COLUMNS),
        )

    specs = component_specs(project_root)
    output = revisions.copy()
    events: list[dict[str, Any]] = []
    cache: dict[
        tuple[str, str, str, date, date],
        tuple[pd.DataFrame, dict[str, date | None], dict[str, date | None]],
    ] = {}

    for index, row in output.iterrows():
        if row["comparison_status"] != "comparable_revision":
            continue

        component = str(row["component"])
        spec = specs.get(component)
        if spec is None or spec.information_set_table is None:
            output.at[index, "release_association_state"] = (
                "missing_information_set_contract"
            )
            continue

        previous_run = str(row["previous_run_id"])
        current_run = str(row["current_run_id"])
        previous_cutoff = _to_date(row["previous_information_cutoff"])
        current_cutoff = _to_date(row["current_information_cutoff"])

        if previous_cutoff is None or current_cutoff is None:
            output.at[index, "release_association_state"] = (
                "missing_cutoff"
            )
            continue

        if current_cutoff < previous_cutoff:
            output.at[index, "release_association_state"] = (
                "invalid_cutoff_order"
            )
            continue

        if current_cutoff == previous_cutoff:
            output.at[index, "release_association_state"] = (
                "same_cutoff_no_calendar_window"
            )
            continue

        cache_key = (
            component,
            previous_run,
            current_run,
            previous_cutoff,
            current_cutoff,
        )
        if cache_key not in cache:
            previous_info = _information_set_summary(
                repository,
                table=str(spec.information_set_table),
                run_id=previous_run,
            )
            current_info = _information_set_summary(
                repository,
                table=str(spec.information_set_table),
                run_id=current_run,
            )
            previous_map = _latest_observation_map(previous_info)
            current_map = _latest_observation_map(current_info)

            series_ids = sorted(current_map)
            releases = _scheduled_releases(
                repository,
                series_ids=series_ids,
                start_exclusive=previous_cutoff,
                end_inclusive=current_cutoff,
            )
            cache[cache_key] = (releases, previous_map, current_map)

        releases, previous_map, current_map = cache[cache_key]

        if releases.empty:
            output.at[index, "release_association_state"] = (
                "no_scheduled_release"
            )
            continue

        labels: list[str] = []
        advanced_count = 0
        for release in releases.itertuples(index=False):
            series_id = str(release.series_id)
            advanced = _source_advanced(
                series_id=series_id,
                previous=previous_map,
                current=current_map,
            )
            if advanced:
                advanced_count += 1

            release_date = _to_date(release.release_date)
            label = (
                f"{release_date.isoformat() if release_date else 'UNKNOWN'}:"
                f"{series_id}:{str(release.release_name)}"
            )
            labels.append(label)

            events.append(
                {
                    "revision_id": str(row["revision_id"]),
                    "component": component,
                    "target_series": str(row["target_series"]),
                    "target_period": str(row["target_period"]),
                    "previous_run_id": previous_run,
                    "current_run_id": current_run,
                    "previous_information_cutoff": previous_cutoff,
                    "current_information_cutoff": current_cutoff,
                    "release_date": release_date,
                    "series_id": series_id,
                    "release_id": str(release.release_id),
                    "release_name": str(release.release_name),
                    "previous_latest_observation_date": previous_map.get(
                        series_id
                    ),
                    "current_latest_observation_date": current_map.get(
                        series_id
                    ),
                    "information_set_advanced": bool(advanced),
                    "association_type": ASSOCIATION_TYPE,
                    "causality_claim": CAUSALITY_CLAIM,
                }
            )

        output.at[index, "associated_release_count"] = int(len(releases))
        output.at[index, "advanced_source_release_count"] = int(
            advanced_count
        )
        output.at[index, "release_association_state"] = (
            "scheduled_releases_with_source_advance"
            if advanced_count
            else "scheduled_releases_none_advanced"
        )
        output.at[index, "associated_release_labels"] = "|".join(
            sorted(labels)
        )

    event_frame = pd.DataFrame.from_records(
        events,
        columns=RELEASE_EVENT_COLUMNS,
    )
    if not event_frame.empty:
        event_frame = event_frame.sort_values(
            [
                "current_information_cutoff",
                "component",
                "target_series",
                "target_period",
                "release_date",
                "series_id",
                "release_id",
            ],
            kind="stable",
        ).reset_index(drop=True)

    return output[REVISION_COLUMNS], event_frame


def build_revision_release_analytics(
    repository: MacroRepository,
    *,
    as_of: date,
    project_root: Path,
) -> dict[str, pd.DataFrame]:
    if as_of > date.today():
        raise ValueError("Phase 3D as-of date cannot be in the future.")

    forecasts = collect_governed_forecasts(
        repository,
        as_of=as_of,
        project_root=project_root,
    )
    revisions = build_revision_table(forecasts)
    revisions, release_events = associate_scheduled_releases(
        repository,
        revisions,
        project_root=project_root,
    )
    return {
        "revisions": revisions,
        "release_events": release_events,
    }


def summarise_revision_release_analytics(
    result: dict[str, pd.DataFrame],
    *,
    as_of: date,
) -> dict[str, Any]:
    revisions = result["revisions"]
    events = result["release_events"]

    comparable = (
        revisions["comparison_status"].astype(str).eq(
            "comparable_revision"
        )
        if not revisions.empty
        else pd.Series(dtype=bool)
    )
    changed = (
        pd.to_numeric(
            revisions.loc[comparable, "absolute_revision"],
            errors="coerce",
        )
        .fillna(0.0)
        .gt(0.0)
        if not revisions.empty
        else pd.Series(dtype=bool)
    )

    return {
        "as_of": as_of,
        "forecast_rows": int(len(revisions)),
        "baseline_rows": int(
            revisions["comparison_status"]
            .astype(str)
            .eq("baseline_no_previous")
            .sum()
        )
        if not revisions.empty
        else 0,
        "comparable_revision_rows": int(comparable.sum()),
        "nonzero_revision_rows": int(changed.sum()),
        "release_event_rows": int(len(events)),
        "revision_rows_with_scheduled_release": int(
            revisions["associated_release_count"].fillna(0).astype(int).gt(0).sum()
        )
        if not revisions.empty
        else 0,
        "revision_rows_with_source_advance": int(
            revisions["advanced_source_release_count"]
            .fillna(0)
            .astype(int)
            .gt(0)
            .sum()
        )
        if not revisions.empty
        else 0,
        "association_type": ASSOCIATION_TYPE,
        "causality_claim": CAUSALITY_CLAIM,
    }


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, np.generic):
        value = value.item()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {key: _json_value(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def serialise_revision_release_analytics(
    result: dict[str, pd.DataFrame],
    *,
    as_of: date,
) -> dict[str, Any]:
    summary = summarise_revision_release_analytics(result, as_of=as_of)
    return {
        "schema_version": REVISION_SCHEMA_VERSION,
        "summary": {
            key: _json_value(value)
            for key, value in summary.items()
        },
        "policy": {
            "comparison_identity": (
                "component+target_series+target_period"
            ),
            "target_period_change_is_revision": False,
            "release_window": (
                "previous_cutoff_exclusive_current_cutoff_inclusive"
            ),
            "release_association_is_causal": False,
            "automatic_model_action": False,
            "model1d_included": False,
        },
        "revisions": _records(result["revisions"]),
        "release_events": _records(result["release_events"]),
    }
