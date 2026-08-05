from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yaml

from macropulse.operations.model1d_shadow_monitoring import (
    collect_shadow_monitoring,
    write_shadow_monitoring_report,
)


class FakeRepository:
    def __init__(self, tables: dict[str, pd.DataFrame]) -> None:
        self.tables = tables

    def query_df(self, query: str, parameters=None) -> pd.DataFrame:
        for name in (
            "macro_state_shadow_predictions",
            "macro_state_shadow_dimensions",
            "macro_state_shadow_outcomes",
            "macro_state_shadow_runs",
        ):
            if name in query:
                return self.tables[name].copy()
        raise AssertionError(query)


def _write_config(root: Path) -> None:
    path = root / "config" / "macro_state_governance.yml"
    path.parent.mkdir(parents=True)
    path.write_text(
        yaml.safe_dump(
            {
                "model": {
                    "model_id": "US_MACRO_STATE_1D",
                    "display_name": "Unified US Macro State Engine",
                    "version": "0.3.8",
                    "lifecycle_status": "development",
                },
                "prospective_transition_shadow": {
                    "model_version": "0.3.8",
                    "promotion_authority": "none",
                    "source_evidence": {"stem": "test", "core_candidate_id": "core", "stability_id": "stable"},
                    "engine": {
                        "rolling_window_months": 12,
                        "uncertainty_draws": 1024,
                        "random_seed": 13030,
                        "normal_interval_z": 1.2815515655446004,
                        "robust_mad_constant": 1.4826,
                        "robust_minimum_history": 18,
                        "robust_clip": 2.0,
                    },
                    "frozen_source": {
                        "model_version": "0.3.6",
                        "candidate_id": "candidate",
                        "specification_changes_prohibited": True,
                    },
                    "comparator": {
                        "benchmark_id": "rolling_frequency",
                        "primary": True,
                        "adaptive_switching_prohibited": True,
                        "blending_prohibited": True,
                    },
                    "target": {
                        "mode": "fixed_horizon_90d",
                        "horizon_days": 90,
                        "latest_revised_substitution_prohibited": True,
                        "target_must_be_available_before_resolution": True,
                    },
                    "probability_contract": {
                        "family_order": [
                            "adverse_supply",
                            "benign_expansion",
                            "contraction",
                            "inflationary_expansion",
                            "mixed",
                        ],
                        "required_sum": 1.0,
                        "sum_tolerance": 1e-10,
                        "log_loss_floor": 1e-12,
                    },
                    "persistence": {
                        "append_only": True,
                        "updates_prohibited": True,
                        "deletes_prohibited": True,
                        "prediction_overwrite_prohibited": True,
                    },
                    "required_dimensions": ["growth", "inflation", "labour"],
                    "minimum_evidence": {"complete_target_months": 12},
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_service_collects_and_writes_report(tmp_path: Path) -> None:
    _write_config(tmp_path)
    run_id = "run-1"
    state_date = date(2026, 8, 31)
    cutoff = date(2026, 8, 5)
    runs = pd.DataFrame(
        [
            {
                "shadow_run_id": run_id,
                "model_version": "0.3.8",
                "run_timestamp": pd.Timestamp(cutoff),
                "state_date": state_date,
                "information_cutoff": cutoff,
                "target_expected_available_date": state_date + timedelta(days=90),
                "no_look_ahead_pass": True,
                "status": "predicted",
            }
        ]
    )
    predictions = pd.DataFrame(
        [
            {
                "shadow_run_id": run_id,
                "model_version": "0.3.8",
                "state_date": state_date,
                "information_cutoff": cutoff,
                "benchmark_id": benchmark,
                "probability_sum": 1.0,
                "no_look_ahead_pass": True,
            }
            for benchmark in ("source", "rolling_frequency")
        ]
    )
    dimensions = pd.DataFrame(
        [
            {
                "shadow_run_id": run_id,
                "model_version": "0.3.8",
                "state_date": state_date,
                "information_cutoff": cutoff,
                "dimension": dimension,
                "no_look_ahead_pass": True,
            }
            for dimension in ("growth", "inflation", "labour")
        ]
    )
    repository = FakeRepository(
        {
            "macro_state_shadow_runs": runs,
            "macro_state_shadow_predictions": predictions,
            "macro_state_shadow_dimensions": dimensions,
            "macro_state_shadow_outcomes": pd.DataFrame(),
        }
    )
    result = collect_shadow_monitoring(
        repository,
        as_of=cutoff,
        project_root=tmp_path,
    )
    assert result["readiness"].iloc[0]["conclusion_status"] == "insufficient_prospective_evidence"
    paths = write_shadow_monitoring_report(result, project_root=tmp_path)
    assert Path(paths["report"]).exists()
    assert Path(paths["metadata"]).exists()
    assert Path(paths["run_status"]).exists()
