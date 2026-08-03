from __future__ import annotations

import json
import uuid
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.tournament import (
    build_core_candidates,
    load_tournament_dataset,
    run_core_tournament,
    run_uncertainty_tournament,
    split_name_for_date,
)
from macropulse.macro_state.versioning import (
    current_macro_state_identity,
    load_macro_state_governance,
)
from macropulse.settings import settings


def _candidate_map(candidates: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item["candidate_id"]): item for item in candidates}


def _candidate_config(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": candidate["candidate_id"],
        "normalization_id": candidate["normalization_id"],
        "inflation_weights_id": candidate["inflation_weights_id"],
        "labour_weights_id": candidate["labour_weights_id"],
        "threshold_id": candidate["threshold_id"],
        "inflation_weights": candidate["inflation_weights"],
        "labour_weights": candidate["labour_weights"],
        "thresholds": candidate["thresholds"],
    }


def _candidate_table(
    *,
    tournament_id: str,
    created_at: pd.Timestamp,
    candidates: list[dict[str, Any]],
    core_leaderboard: pd.DataFrame,
    final_leaderboard: pd.DataFrame,
    uncertainty_config: dict[str, Any],
) -> pd.DataFrame:
    candidate_map = _candidate_map(candidates)
    rows: list[dict[str, Any]] = []
    for row in core_leaderboard.itertuples(index=False):
        candidate = candidate_map[str(row.candidate_id)]
        rows.append(
            {
                "tournament_id": tournament_id,
                "candidate_id": str(row.candidate_id),
                "candidate_type": "core",
                "core_candidate_id": str(row.candidate_id),
                "normalization_id": candidate["normalization_id"],
                "inflation_weights_id": candidate["inflation_weights_id"],
                "labour_weights_id": candidate["labour_weights_id"],
                "threshold_id": candidate["threshold_id"],
                "uncertainty_id": None,
                "selected": False,
                "validation_rank": int(row.core_rank),
                "holdout_rank": int(row.holdout_core_rank),
                "validation_score": float(row.core_score),
                "holdout_score": float(row.holdout_core_score),
                "config_json": json.dumps(
                    _candidate_config(candidate), sort_keys=True
                ),
                "created_at": created_at,
            }
        )

    selected_id = str(
        final_leaderboard.sort_values(
            ["final_rank", "candidate_id"]
        ).iloc[0]["candidate_id"]
    )
    for row in final_leaderboard.itertuples(index=False):
        core = candidate_map[str(row.core_candidate_id)]
        config_payload = _candidate_config(core)
        config_payload["uncertainty_id"] = str(row.uncertainty_id)
        config_payload["uncertainty"] = uncertainty_config[
            str(row.uncertainty_id)
        ]
        rows.append(
            {
                "tournament_id": tournament_id,
                "candidate_id": str(row.candidate_id),
                "candidate_type": "uncertainty",
                "core_candidate_id": str(row.core_candidate_id),
                "normalization_id": core["normalization_id"],
                "inflation_weights_id": core["inflation_weights_id"],
                "labour_weights_id": core["labour_weights_id"],
                "threshold_id": core["threshold_id"],
                "uncertainty_id": str(row.uncertainty_id),
                "selected": str(row.candidate_id) == selected_id,
                "validation_rank": int(row.final_rank),
                "holdout_rank": int(row.holdout_final_rank),
                "validation_score": float(row.final_score),
                "holdout_score": float(row.holdout_final_score),
                "config_json": json.dumps(config_payload, sort_keys=True),
                "created_at": created_at,
            }
        )
    return pd.DataFrame(rows)


def _metric_template() -> dict[str, Any]:
    return {
        "dimension_rmse": None,
        "dimension_mae": None,
        "exact_regime_accuracy": None,
        "family_accuracy": None,
        "sign_accuracy": None,
        "forecast_churn": None,
        "actual_churn": None,
        "churn_gap": None,
        "distribution_jsd": None,
        "forecast_regime_entropy": None,
        "actual_regime_entropy": None,
        "regime_collapse_penalty": None,
        "forecast_regime_count": None,
        "actual_regime_count": None,
        "brier_score": None,
        "log_loss": None,
        "coverage_80": None,
        "coverage_gap": None,
        "mean_top_probability": None,
        "mean_effective_regimes": None,
        "top1_accuracy": None,
        "core_score": None,
        "uncertainty_score": None,
        "final_score": None,
    }


def _metrics_table(
    *,
    tournament_id: str,
    created_at: pd.Timestamp,
    core_metrics_frame: pd.DataFrame,
    core_leaderboard: pd.DataFrame,
    uncertainty_metrics_frame: pd.DataFrame,
    final_leaderboard: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    core_scores = {
        str(row.candidate_id): row
        for row in core_leaderboard.itertuples(index=False)
    }
    for row in core_metrics_frame.itertuples(index=False):
        output = _metric_template()
        for key in (
            "dimension_rmse",
            "dimension_mae",
            "exact_regime_accuracy",
            "family_accuracy",
            "sign_accuracy",
            "forecast_churn",
            "actual_churn",
            "churn_gap",
            "distribution_jsd",
            "forecast_regime_entropy",
            "actual_regime_entropy",
            "regime_collapse_penalty",
            "forecast_regime_count",
            "actual_regime_count",
        ):
            output[key] = getattr(row, key)
        score_row = core_scores[str(row.candidate_id)]
        output["core_score"] = float(
            score_row.core_score
            if row.split == "validation"
            else score_row.holdout_core_score
        )
        rows.append(
            {
                "tournament_id": tournament_id,
                "candidate_id": str(row.candidate_id),
                "split": str(row.split),
                "months": int(row.months),
                **output,
                "created_at": created_at,
            }
        )

    core_raw = {
        (str(row.candidate_id), str(row.split)): row
        for row in core_metrics_frame.itertuples(index=False)
    }
    final_scores = {
        str(row.candidate_id): row
        for row in final_leaderboard.itertuples(index=False)
    }
    for row in uncertainty_metrics_frame.itertuples(index=False):
        output = _metric_template()
        core = core_raw[(str(row.core_candidate_id), str(row.split))]
        for key in (
            "dimension_rmse",
            "dimension_mae",
            "exact_regime_accuracy",
            "family_accuracy",
            "sign_accuracy",
            "forecast_churn",
            "actual_churn",
            "churn_gap",
            "distribution_jsd",
            "forecast_regime_entropy",
            "actual_regime_entropy",
            "regime_collapse_penalty",
            "forecast_regime_count",
            "actual_regime_count",
        ):
            output[key] = getattr(core, key)
        for key in (
            "brier_score",
            "log_loss",
            "coverage_80",
            "coverage_gap",
            "mean_top_probability",
            "mean_effective_regimes",
            "top1_accuracy",
        ):
            output[key] = getattr(row, key)
        score_row = final_scores[str(row.candidate_id)]
        if row.split == "validation":
            output["core_score"] = float(score_row.core_score)
            output["uncertainty_score"] = float(
                score_row.uncertainty_score
            )
            output["final_score"] = float(score_row.final_score)
        else:
            output["core_score"] = float(
                score_row.holdout_core_score
            )
            output["uncertainty_score"] = float(
                score_row.holdout_uncertainty_score
            )
            output["final_score"] = float(
                score_row.holdout_final_score
            )
        rows.append(
            {
                "tournament_id": tournament_id,
                "candidate_id": str(row.candidate_id),
                "split": str(row.split),
                "months": int(row.months),
                **output,
                "created_at": created_at,
            }
        )
    return pd.DataFrame(rows)


def _monthly_table(
    *,
    tournament_id: str,
    created_at: pd.Timestamp,
    monthly_final: dict[str, pd.DataFrame],
    split: Any,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for candidate_id, frame in monthly_final.items():
        data = frame.copy()
        data.insert(0, "tournament_id", tournament_id)
        data["split"] = [
            split_name_for_date(item, split) for item in data["state_date"]
        ]
        data["created_at"] = created_at
        frames.append(data)
    return pd.concat(frames, ignore_index=True)


def _markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    data = frame[columns].copy()
    headers = [str(item) for item in data.columns]
    rows = ["| " + " | ".join(headers) + " |"]
    rows.append("| " + " | ".join("---" for _ in headers) + " |")
    for record in data.itertuples(index=False):
        formatted = []
        for value in record:
            if isinstance(value, float):
                formatted.append(f"{value:.4f}")
            else:
                formatted.append(str(value))
        rows.append("| " + " | ".join(formatted) + " |")
    return "\n".join(rows)


def _write_report(
    *,
    tournament_id: str,
    reconstruction_id: str,
    identity: Any,
    split: Any,
    core_leaderboard: pd.DataFrame,
    final_leaderboard: pd.DataFrame,
    baselines: dict[str, Any],
) -> Path:
    report_dir = settings.project_root / "reports" / "macro_state_tournament"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"model1d_tournament_{tournament_id}.md"
    winner = final_leaderboard.sort_values(
        ["final_rank", "candidate_id"]
    ).iloc[0]
    winner_core = core_leaderboard.loc[
        core_leaderboard["candidate_id"]
        == winner["core_candidate_id"]
    ].iloc[0]
    holdout_baseline = max(
        float(baselines["holdout_mode_accuracy"]),
        float(baselines["holdout_persistence_accuracy"]),
    )
    beats_baseline = (
        float(winner_core["holdout_exact_regime_accuracy"])
        >= holdout_baseline
    )
    content = f"""# Model 1D v0.3 Tournament Report

- Tournament ID: `{tournament_id}`
- Reconstruction ID: `{reconstruction_id}`
- Model: `{identity.model_id}` v`{identity.model_version}`
- Status: research tournament; not production approved

## Chronological split

- Training: {split.training_dates[0]} to {split.training_dates[-1]} ({len(split.training_dates)} states)
- Validation: {split.validation_dates[0]} to {split.validation_dates[-1]} ({len(split.validation_dates)} states)
- Holdout: {split.holdout_dates[0]} to {split.holdout_dates[-1]} ({len(split.holdout_dates)} states)

## Provisional winner

- Candidate: `{winner['candidate_id']}`
- Core specification: `{winner['core_candidate_id']}`
- Uncertainty method: `{winner['uncertainty_id']}`
- Validation score: {float(winner['final_score']):.2f}
- Validation rank: {int(winner['final_rank'])}
- Holdout score: {float(winner['holdout_final_score']):.2f}
- Holdout rank: {int(winner['holdout_final_rank'])}
- Holdout exact-regime accuracy beats best naive baseline: {beats_baseline}

## Naive baselines

```json
{json.dumps(baselines, indent=2, default=str)}
```

## Final leaderboard

{_markdown_table(final_leaderboard.head(12), [
    'final_rank', 'candidate_id', 'core_candidate_id', 'uncertainty_id',
    'final_score', 'holdout_final_rank', 'holdout_final_score',
    'brier_score', 'log_loss', 'coverage_80', 'top1_accuracy',
    'holdout_brier_score', 'holdout_log_loss', 'holdout_coverage_80',
    'holdout_top1_accuracy'
])}

## Core leaderboard

{_markdown_table(core_leaderboard.head(15), [
    'core_rank', 'candidate_id', 'core_score', 'holdout_core_rank',
    'holdout_core_score', 'dimension_rmse', 'exact_regime_accuracy',
    'family_accuracy', 'sign_accuracy', 'churn_gap', 'distribution_jsd',
    'regime_collapse_penalty',
    'holdout_dimension_rmse', 'holdout_exact_regime_accuracy',
    'holdout_family_accuracy', 'holdout_sign_accuracy'
])}

## Governance interpretation

The winner is provisional. It was selected on the validation window and audited
on a sealed chronological holdout. Model 1D must not be promoted from this
report alone. A later release should assess specification stability, economic
event sensitivity, and whether the selected uncertainty method is calibrated
across subperiods.
"""
    report_path.write_text(content, encoding="utf-8")
    return report_path


def run_macro_state_tournament(
    repository: MacroRepository | None = None,
    reconstruction_id: str | None = None,
) -> dict[str, Any]:
    repository = repository or MacroRepository()
    repository.initialise()
    config = load_macro_state_governance()
    identity = current_macro_state_identity()
    resolved_reconstruction, dataset = load_tournament_dataset(
        repository, reconstruction_id
    )
    (
        split,
        core_candidates,
        monthly_by_candidate,
        core_metrics_frame,
        core_leaderboard,
        baselines,
    ) = run_core_tournament(dataset, config)
    (
        final_leaderboard,
        uncertainty_metrics_frame,
        monthly_final,
    ) = run_uncertainty_tournament(
        core_candidates=core_candidates,
        monthly_by_candidate=monthly_by_candidate,
        core_leaderboard=core_leaderboard,
        split=split,
        config=config,
    )

    tournament_id = str(uuid.uuid4())
    created_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
    winner = final_leaderboard.sort_values(
        ["final_rank", "candidate_id"]
    ).iloc[0]
    candidate_rows = _candidate_table(
        tournament_id=tournament_id,
        created_at=created_at,
        candidates=core_candidates,
        core_leaderboard=core_leaderboard,
        final_leaderboard=final_leaderboard,
        uncertainty_config=config["tournament"]["uncertainty_candidates"],
    )
    metric_rows = _metrics_table(
        tournament_id=tournament_id,
        created_at=created_at,
        core_metrics_frame=core_metrics_frame,
        core_leaderboard=core_leaderboard,
        uncertainty_metrics_frame=uncertainty_metrics_frame,
        final_leaderboard=final_leaderboard,
    )
    monthly_rows = _monthly_table(
        tournament_id=tournament_id,
        created_at=created_at,
        monthly_final=monthly_final,
        split=split,
    )
    report_path = _write_report(
        tournament_id=tournament_id,
        reconstruction_id=resolved_reconstruction,
        identity=identity,
        split=split,
        core_leaderboard=core_leaderboard,
        final_leaderboard=final_leaderboard,
        baselines=baselines,
    )

    selected_core_id = str(winner["core_candidate_id"])
    selected_core = core_leaderboard.loc[
        core_leaderboard["candidate_id"] == selected_core_id
    ].iloc[0]
    best_validation_baseline = max(
        float(baselines["validation_mode_accuracy"]),
        float(baselines["validation_persistence_accuracy"]),
    )
    warnings: list[str] = []
    if float(selected_core["exact_regime_accuracy"]) < best_validation_baseline:
        warnings.append(
            "Selected core specification does not beat the strongest naive "
            "validation accuracy baseline."
        )
    if int(winner["holdout_final_rank"]) > max(
        3, len(final_leaderboard) // 3
    ):
        warnings.append(
            "Validation winner ranks outside the leading holdout third."
        )

    run_record = pd.DataFrame(
        [
            {
                "tournament_id": tournament_id,
                "model_id": identity.model_id,
                "model_version": identity.model_version,
                "reconstruction_id": resolved_reconstruction,
                "created_at": created_at,
                "status": "success",
                "training_start": split.training_dates[0],
                "training_end": split.training_dates[-1],
                "validation_start": split.validation_dates[0],
                "validation_end": split.validation_dates[-1],
                "holdout_start": split.holdout_dates[0],
                "holdout_end": split.holdout_dates[-1],
                "training_months": len(split.training_dates),
                "validation_months": len(split.validation_dates),
                "holdout_months": len(split.holdout_dates),
                "core_candidates": len(core_candidates),
                "uncertainty_candidates": len(final_leaderboard),
                "selected_candidate_id": str(winner["candidate_id"]),
                "selected_core_candidate_id": selected_core_id,
                "selected_validation_score": float(winner["final_score"]),
                "selected_holdout_rank": int(winner["holdout_final_rank"]),
                "config_hash": identity.config_hash,
                "code_hash": identity.code_hash,
                "git_commit": identity.git_commit,
                "baseline_metrics_json": json.dumps(
                    baselines, sort_keys=True, default=str
                ),
                "metrics_json": json.dumps(
                    {
                        "warnings": warnings,
                        "winner": winner.to_dict(),
                        "split": split.as_dict(),
                    },
                    sort_keys=True,
                    default=str,
                ),
                "report_path": str(report_path),
                "notes": (
                    "Model 1D v0.3 research tournament. The selected "
                    "specification is provisional and not production approved."
                ),
            }
        ]
    )
    repository.save_macro_state_tournament(
        run_record=run_record,
        candidates=candidate_rows,
        metrics=metric_rows,
        monthly=monthly_rows,
    )
    return {
        "tournament_id": tournament_id,
        "model_id": identity.model_id,
        "model_version": identity.model_version,
        "reconstruction_id": resolved_reconstruction,
        "split": split,
        "core_candidates": len(core_candidates),
        "uncertainty_candidates": len(final_leaderboard),
        "selected_candidate_id": str(winner["candidate_id"]),
        "selected_core_candidate_id": selected_core_id,
        "selected_uncertainty_id": str(winner["uncertainty_id"]),
        "selected_validation_score": float(winner["final_score"]),
        "selected_holdout_rank": int(winner["holdout_final_rank"]),
        "baselines": baselines,
        "warnings": warnings,
        "core_leaderboard": core_leaderboard,
        "final_leaderboard": final_leaderboard,
        "report_path": report_path,
    }
