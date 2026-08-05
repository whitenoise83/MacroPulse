from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.prospective_shadow import (
    REQUIRED_DIMENSIONS,
    canonical_json,
    build_source_dimensions,
    information_set_hash,
    month_end,
    prediction_rows,
    prospective_shadow_plan,
    rolling_frequency_probabilities,
    sha256_json,
    source_family_probabilities,
)
from macropulse.macro_state.service import run_macro_state
from macropulse.macro_state.versioning import (
    current_macro_state_identity,
    load_macro_state_governance,
)
from macropulse.settings import settings


def _utc_now_naive() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC").tz_localize(None)


def _evidence_path(project_root: Path, stem: str) -> Path:
    return (
        project_root
        / "reports"
        / "macro_state_fixed_horizon_probabilistic"
        / f"{stem}_locked_targets.csv"
    )


def _load_frozen_target_history(
    *,
    project_root: Path,
    stem: str,
) -> pd.DataFrame:
    path = _evidence_path(project_root, stem)
    if not path.is_file():
        raise FileNotFoundError(
            "Frozen v0.3.6 locked-target evidence is missing: "
            f"{path}"
        )
    frame = pd.read_csv(path)
    required = {"state_date", "primary_family", "state_available_date"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(
            f"Frozen locked-target evidence is missing columns: {missing}"
        )
    return frame[list(required)].copy()


def _load_resolved_shadow_history(
    repository: MacroRepository,
    information_cutoff: date,
) -> pd.DataFrame:
    frame = repository.query_df(
        """
        SELECT state_date, actual_family AS primary_family,
               target_available_date AS state_available_date
        FROM macro_state_shadow_outcomes
        WHERE benchmark_id = 'source'
          AND target_available_date <= ?
        ORDER BY state_date
        """,
        [information_cutoff],
    )
    return frame


def _combined_target_history(
    *,
    repository: MacroRepository,
    project_root: Path,
    stem: str,
    information_cutoff: date,
) -> pd.DataFrame:
    frozen = _load_frozen_target_history(
        project_root=project_root,
        stem=stem,
    )
    resolved = _load_resolved_shadow_history(repository, information_cutoff)
    frames = [frozen]
    if not resolved.empty:
        frames.append(resolved)
    combined = pd.concat(frames, ignore_index=True)
    combined["state_date"] = pd.to_datetime(
        combined["state_date"], errors="raise"
    ).dt.date
    combined["state_available_date"] = pd.to_datetime(
        combined["state_available_date"], errors="raise"
    ).dt.date
    combined = combined.sort_values(
        ["state_date", "state_available_date"]
    )
    return combined.drop_duplicates("state_date", keep="last").reset_index(
        drop=True
    )


def _latest_history_inputs(
    repository: MacroRepository,
    state_date: date,
) -> pd.DataFrame:
    metadata = repository.query_df(
        """
        SELECT reconstruction_id
        FROM macro_state_history_runs
        WHERE no_look_ahead_pass = TRUE
        ORDER BY created_at DESC, reconstruction_id DESC
        LIMIT 1
        """
    )
    if metadata.empty:
        raise RuntimeError(
            "No validated Model 1D history reconstruction is available. "
            "Run the governed history reconstruction before the shadow runner."
        )
    reconstruction_id = str(metadata.iloc[0]["reconstruction_id"])
    return repository.query_df(
        """
        SELECT state_date, source_target, point_forecast
        FROM macro_state_history_inputs
        WHERE reconstruction_id = ?
          AND state_date < ?
          AND target_leakage = FALSE
          AND (
              max_observation_date IS NULL
              OR max_observation_date <= state_date
          )
        ORDER BY state_date, source_target
        """,
        [reconstruction_id, state_date],
    )


def _preflight_duplicate(
    repository: MacroRepository,
    *,
    model_version: str,
    state_date: date,
) -> None:
    existing = repository.query_df(
        """
        SELECT shadow_run_id
        FROM macro_state_shadow_runs
        WHERE model_version = ? AND state_date = ?
        LIMIT 1
        """,
        [model_version, state_date],
    )
    if not existing.empty:
        raise ValueError(
            "append-only violation: a prospective shadow run already exists "
            f"for Model 1D v{model_version} and {state_date}"
        )


def _dimension_lineage_frame(
    source_dimensions: pd.DataFrame,
    *,
    shadow_run_id: str,
    model_version: str,
    state_date: date,
    information_cutoff: date,
    created_at: pd.Timestamp,
) -> pd.DataFrame:
    frame = source_dimensions.copy()
    frame.insert(0, "shadow_run_id", shadow_run_id)
    frame.insert(1, "model_version", model_version)
    frame.insert(2, "state_date", state_date)
    frame.insert(3, "information_cutoff", information_cutoff)
    frame["no_look_ahead_pass"] = (
        pd.to_datetime(frame["source_information_cutoff"]).dt.date
        <= information_cutoff
    )
    frame["created_at"] = created_at
    columns = [
        "shadow_run_id",
        "model_version",
        "state_date",
        "information_cutoff",
        "dimension",
        "score",
        "lower_score",
        "upper_score",
        "label",
        "confidence",
        "source_model_id",
        "source_model_version",
        "source_run_id",
        "source_information_cutoff",
        "source_data_as_of",
        "source_hash",
        "no_look_ahead_pass",
        "created_at",
    ]
    return frame[columns]


def _governance_record(
    *,
    config: Mapping[str, Any],
    source_dimensions: pd.DataFrame,
    rolling_history: pd.DataFrame,
    prediction_timestamp: pd.Timestamp,
    target_expected_available_date: date,
    information_cutoff: date,
) -> dict[str, Any]:
    shadow = config["prospective_transition_shadow"]
    checks = {
        "research_only_no_promotion_authority": (
            str(shadow["promotion_authority"]) == "none"
        ),
        "frozen_source_version": (
            str(shadow["frozen_source"]["model_version"]) == "0.3.6"
        ),
        "frozen_source_specification": bool(
            shadow["frozen_source"]["specification_changes_prohibited"]
        ),
        "rolling_frequency_primary_comparator": (
            str(shadow["comparator"]["benchmark_id"])
            == "rolling_frequency"
            and bool(shadow["comparator"]["primary"])
        ),
        "adaptive_switching_prohibited": bool(
            shadow["comparator"]["adaptive_switching_prohibited"]
        ),
        "blending_prohibited": bool(
            shadow["comparator"]["blending_prohibited"]
        ),
        "latest_revised_substitution_prohibited": bool(
            shadow["target"]["latest_revised_substitution_prohibited"]
        ),
        "three_dimensions_present": (
            set(source_dimensions["dimension"].astype(str))
            == set(REQUIRED_DIMENSIONS)
        ),
        "dimension_cutoffs_not_after_information_cutoff": bool(
            (
                pd.to_datetime(
                    source_dimensions["source_information_cutoff"]
                ).dt.date
                <= information_cutoff
            ).all()
        ),
        "rolling_history_is_causal": bool(
            (
                pd.to_datetime(
                    rolling_history["state_available_date"]
                ).dt.date
                <= information_cutoff
            ).all()
        ),
        "prediction_precedes_expected_target_availability": (
            prediction_timestamp
            < pd.Timestamp(target_expected_available_date)
        ),
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "promotion_authority": "none",
        "adaptive_switching": "prohibited",
        "blending": "prohibited",
        "outcome_resolution": "not_part_of_phase_2",
    }


def run_macro_state_prospective_shadow(
    repository: MacroRepository | None = None,
    *,
    as_of: date | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    repository = repository or MacroRepository()
    repository.initialise()
    root = Path(project_root or settings.project_root)
    config = load_macro_state_governance(root)
    identity = current_macro_state_identity(root)
    plan = prospective_shadow_plan(config)

    if identity.model_version != plan.model_version:
        raise ValueError(
            f"Active Model 1D version {identity.model_version} does not match "
            f"the shadow plan version {plan.model_version}."
        )

    information_cutoff = as_of or date.today()
    state_date = month_end(information_cutoff)
    run_timestamp = _utc_now_naive()
    if run_timestamp < pd.Timestamp(information_cutoff):
        raise ValueError(
            "The information cutoff cannot be later than the run timestamp."
        )
    target_expected_available_date = (
        state_date + timedelta(days=plan.target_horizon_days)
    )
    if run_timestamp >= pd.Timestamp(target_expected_available_date):
        raise ValueError(
            "The expected target availability date must be later than the run."
        )

    _preflight_duplicate(
        repository,
        model_version=identity.model_version,
        state_date=state_date,
    )

    macro_result = run_macro_state(
        repository=repository,
        as_of=information_cutoff,
    )
    current_inputs = macro_result["inputs"].copy()
    history_inputs = _latest_history_inputs(repository, state_date)

    source_dimensions = build_source_dimensions(
        history_inputs=history_inputs,
        current_inputs=current_inputs,
        config=config,
        plan=plan,
    )
    source_probabilities = source_family_probabilities(
        source_dimensions,
        state_date=state_date,
        config=config,
        plan=plan,
    )

    all_target_history = _combined_target_history(
        repository=repository,
        project_root=root,
        stem=plan.source_evidence_stem,
        information_cutoff=information_cutoff,
    )
    rolling_probabilities, rolling_history = (
        rolling_frequency_probabilities(
            all_target_history,
            information_cutoff=information_cutoff,
            state_date=state_date,
            plan=plan,
        )
    )

    shadow_run_id = str(uuid.uuid4())
    prediction_timestamp = _utc_now_naive()
    created_at = prediction_timestamp
    predictions = prediction_rows(
        shadow_run_id=shadow_run_id,
        model_version=identity.model_version,
        state_date=state_date,
        information_cutoff=information_cutoff,
        prediction_timestamp=prediction_timestamp,
        probability_vectors={
            "source": source_probabilities,
            "rolling_frequency": rolling_probabilities,
        },
        plan=plan,
        created_at=created_at,
    )

    dimensions = _dimension_lineage_frame(
        source_dimensions,
        shadow_run_id=shadow_run_id,
        model_version=identity.model_version,
        state_date=state_date,
        information_cutoff=information_cutoff,
        created_at=created_at,
    )
    if not bool(dimensions["no_look_ahead_pass"].all()):
        raise ValueError(
            "A source dimension uses information after the shadow cutoff."
        )

    info_hash = information_set_hash(
        current_inputs=current_inputs,
        source_dimensions=source_dimensions,
        rolling_history=rolling_history,
        plan=plan,
    )
    governance = _governance_record(
        config=config,
        source_dimensions=source_dimensions,
        rolling_history=rolling_history,
        prediction_timestamp=prediction_timestamp,
        target_expected_available_date=target_expected_available_date,
        information_cutoff=information_cutoff,
    )
    if governance["status"] != "pass":
        failed = [
            key for key, passed in governance["checks"].items() if not passed
        ]
        raise ValueError(
            "Prospective shadow governance failed: " + ", ".join(failed)
        )

    source_runs = {
        str(row.source_model_id): str(row.source_run_id)
        for row in current_inputs.itertuples(index=False)
    }
    required_sources = config["required_sources"]
    gdp_id = str(required_sources["GDP"]["model_id"])
    inflation_id = str(required_sources["inflation"]["model_id"])
    labour_id = str(required_sources["labour"]["model_id"])

    run_record = pd.DataFrame(
        [
            {
                "shadow_run_id": shadow_run_id,
                "model_id": identity.model_id,
                "model_version": identity.model_version,
                "run_timestamp": run_timestamp,
                "state_date": state_date,
                "information_cutoff": information_cutoff,
                "target_mode": plan.target_mode,
                "target_horizon_days": plan.target_horizon_days,
                "target_expected_available_date": (
                    target_expected_available_date
                ),
                "source_candidate_id": plan.source_candidate_id,
                "source_evidence_version": plan.source_version,
                "primary_comparator": plan.primary_comparator,
                "source_macro_state_run_id": str(macro_result["run_id"]),
                "gdp_run_id": source_runs[gdp_id],
                "inflation_run_id": source_runs[inflation_id],
                "labour_run_id": source_runs[labour_id],
                "config_hash": identity.config_hash,
                "code_hash": identity.code_hash,
                "git_commit": identity.git_commit,
                "information_set_hash": info_hash,
                "source_bundle_hash": str(
                    macro_result["source_bundle_hash"]
                ),
                "no_look_ahead_pass": True,
                "status": "predicted",
                "governance_json": canonical_json(governance),
                "notes": (
                    "Prospective research shadow only; no promotion, "
                    "switching, or blending authority."
                ),
                "created_at": created_at,
            }
        ]
    )

    repository.save_macro_state_shadow_predictions(
        run_record,
        predictions,
        dimensions,
    )
    return {
        "shadow_run_id": shadow_run_id,
        "model_id": identity.model_id,
        "model_version": identity.model_version,
        "lifecycle_status": identity.lifecycle_status,
        "state_date": state_date,
        "information_cutoff": information_cutoff,
        "target_expected_available_date": target_expected_available_date,
        "source_macro_state_run_id": str(macro_result["run_id"]),
        "source_candidate_id": plan.source_candidate_id,
        "source_evidence_stem": plan.source_evidence_stem,
        "predictions": predictions,
        "dimensions": dimensions,
        "rolling_history": rolling_history,
        "information_set_hash": info_hash,
        "source_bundle_hash": str(macro_result["source_bundle_hash"]),
        "governance": governance,
        "promotion_authority": "none",
    }
