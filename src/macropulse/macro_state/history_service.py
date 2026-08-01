from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any

import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.history import (
    reconstruct_history,
    reconstruction_dates,
    regime_durations,
    transition_matrix,
)
from macropulse.macro_state.vintage_history import (
    reconstruct_production_vintage_history,
)
from macropulse.macro_state.versioning import current_macro_state_identity


def _longest_contiguous_months(states: pd.DataFrame) -> int:
    if states.empty:
        return 0
    ordinals = pd.PeriodIndex(
        states.sort_values("state_date")["state_date"], freq="M"
    ).asi8
    longest = 1
    current = 1
    for previous, observed in zip(ordinals[:-1], ordinals[1:]):
        if observed - previous == 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return int(longest)


def _ensure_history_input_columns(
    inputs: pd.DataFrame,
    source_mode: str,
) -> pd.DataFrame:
    frame = inputs.copy()
    defaults = {
        "source_validation_id": None,
        "interval_source": (
            "live_governed_interval"
            if source_mode == "live_runs"
            else None
        ),
        "actual_release_date": None,
        "target_leakage": False,
        "max_observation_date": None,
        "model_name": None,
        "information_set_hash": None,
    }
    for column, value in defaults.items():
        if column not in frame.columns:
            frame[column] = value
    return frame


def run_macro_state_history(
    repository: MacroRepository | None = None,
    start_date: date = date(2015, 1, 1),
    end_date: date | None = None,
    source_mode: str = "production_vintage_backtests",
) -> dict[str, Any]:
    repository = repository or MacroRepository()
    repository.initialise()
    end_date = end_date or date.today()

    lineage_payload: dict[str, str] = {}
    if source_mode == "production_vintage_backtests":
        states, inputs, lineage = reconstruct_production_vintage_history(
            repository,
            start_date=start_date,
            end_date=end_date,
        )
        lineage_payload = lineage.as_dict()
        requested_dates = pd.date_range(
            start_date, end_date, freq="ME"
        )
    elif source_mode == "live_runs":
        states, inputs = reconstruct_history(
            repository,
            start_date=start_date,
            end_date=end_date,
        )
        requested_dates = reconstruction_dates(start_date, end_date)
    else:
        raise ValueError(
            "source_mode must be 'production_vintage_backtests' "
            "or 'live_runs'."
        )

    if states.empty:
        raise RuntimeError(
            "No complete historical Model 1D states could be reconstructed "
            f"using source mode {source_mode!r} between "
            f"{start_date} and {end_date}."
        )

    identity = current_macro_state_identity()
    reconstruction_id = str(uuid.uuid4())
    created_at = pd.Timestamp.now(tz="UTC").tz_localize(None)

    states = states.copy()
    states.insert(0, "reconstruction_id", reconstruction_id)
    states["created_at"] = created_at

    inputs = _ensure_history_input_columns(inputs, source_mode)
    inputs.insert(0, "reconstruction_id", reconstruction_id)
    inputs["created_at"] = created_at

    durations = regime_durations(states)
    if not durations.empty:
        durations.insert(0, "reconstruction_id", reconstruction_id)
        durations["created_at"] = created_at

    matrix = transition_matrix(states)
    matrix_rows: list[dict[str, Any]] = []
    if not matrix.empty:
        for from_regime, row in matrix.iterrows():
            for to_regime, probability in row.items():
                matrix_rows.append(
                    {
                        "reconstruction_id": reconstruction_id,
                        "from_regime": str(from_regime),
                        "to_regime": str(to_regime),
                        "transition_probability": float(probability),
                        "created_at": created_at,
                    }
                )
    transitions = pd.DataFrame(matrix_rows)

    months_requested = int(len(requested_dates))
    coverage_ratio = (
        float(len(states) / months_requested)
        if months_requested
        else 0.0
    )
    longest_contiguous = _longest_contiguous_months(states)

    metadata = pd.DataFrame(
        [
            {
                "reconstruction_id": reconstruction_id,
                "model_id": identity.model_id,
                "model_version": identity.model_version,
                "start_date": min(states["state_date"]),
                "end_date": max(states["state_date"]),
                "months_requested": months_requested,
                "months_reconstructed": len(states),
                "no_look_ahead_pass": bool(
                    states["no_look_ahead_pass"].all()
                ),
                "config_hash": identity.config_hash,
                "code_hash": identity.code_hash,
                "git_commit": identity.git_commit,
                "created_at": created_at,
                "notes": json.dumps(
                    {
                        "description": (
                            "Model 1D v0.2.1 production-lineage historical "
                            "reconstruction; not production approved."
                        ),
                        "lineage": lineage_payload,
                    },
                    sort_keys=True,
                ),
                "source_mode": source_mode,
                "gdp_source_id": lineage_payload.get(
                    "gdp_backtest_id"
                ),
                "inflation_source_id": lineage_payload.get(
                    "inflation_backtest_id"
                ),
                "labour_source_id": lineage_payload.get(
                    "labour_backtest_id"
                ),
                "coverage_ratio": coverage_ratio,
                "longest_contiguous_months": longest_contiguous,
            }
        ]
    )

    repository.save_macro_state_history(
        metadata=metadata,
        states=states,
        inputs=inputs,
        durations=durations,
        transitions=transitions,
    )
    return {
        "reconstruction_id": reconstruction_id,
        "model_id": identity.model_id,
        "model_version": identity.model_version,
        "source_mode": source_mode,
        "lineage": lineage_payload,
        "start_date": min(states["state_date"]),
        "end_date": max(states["state_date"]),
        "months_requested": months_requested,
        "months_reconstructed": len(states),
        "coverage_ratio": coverage_ratio,
        "longest_contiguous_months": longest_contiguous,
        "no_look_ahead_pass": bool(
            states["no_look_ahead_pass"].all()
        ),
        "states": states,
        "inputs": inputs,
        "durations": durations,
        "transition_matrix": matrix,
    }
