from __future__ import annotations

import json
from dataclasses import dataclass

import pandas as pd

from macropulse.backtesting.production_selection import ROBUST_STAGE_ADAPTIVE_MODEL_NAME
from macropulse.backtesting.stages import stage_forecast_date


@dataclass(frozen=True)
class AuditCheck:
    gate_name: str
    check_name: str
    status: str
    observed_value: str
    threshold: str
    details: dict

    def as_dict(self) -> dict:
        return {
            "gate_name": self.gate_name,
            "check_name": self.check_name,
            "status": self.status,
            "observed_value": self.observed_value,
            "threshold": self.threshold,
            "details_json": json.dumps(self.details),
        }


def _status(condition: bool) -> str:
    return "pass" if condition else "fail"


def audit_stage_backtest(
    results: pd.DataFrame,
    diagnostics: pd.DataFrame,
    target_snapshot_leakage_count: int = 0,
    future_observation_count: int = 0,
) -> list[AuditCheck]:
    checks: list[AuditCheck] = []
    if results.empty:
        return [
            AuditCheck(
                "Econometric validity",
                "Stage backtest contains evaluable forecasts",
                "fail",
                "0 rows",
                "> 0 rows",
                {},
            )
        ]

    frame = results.copy()
    frame["forecast_date"] = pd.to_datetime(frame["forecast_date"])
    frame["actual_release_date"] = pd.to_datetime(frame["actual_release_date"])

    outcome_order = bool((frame["forecast_date"] < frame["actual_release_date"]).all())
    violations = frame.loc[frame["forecast_date"] >= frame["actual_release_date"]]
    checks.append(
        AuditCheck(
            "Econometric validity",
            "Outcome release occurs after forecast cutoff",
            _status(outcome_order),
            f"{len(violations)} violations",
            "0 violations",
            {"violations": violations.head(20).to_dict(orient="records")},
        )
    )

    expected_mismatches: list[dict] = []
    unique_cutoffs = frame[
        ["target_period", "forecast_stage", "forecast_date", "actual_release_date"]
    ].drop_duplicates()
    for _, row in unique_cutoffs.iterrows():
        expected = stage_forecast_date(
            str(row["target_period"]),
            str(row["forecast_stage"]),
            pd.Timestamp(row["actual_release_date"]).date(),
        )
        observed = pd.Timestamp(row["forecast_date"]).date()
        if observed != expected:
            expected_mismatches.append(
                {
                    "target_period": row["target_period"],
                    "forecast_stage": row["forecast_stage"],
                    "observed": observed.isoformat(),
                    "expected": expected.isoformat(),
                }
            )
    checks.append(
        AuditCheck(
            "Econometric validity",
            "Forecast dates match pre-declared stage rules",
            _status(not expected_mismatches),
            f"{len(expected_mismatches)} mismatches",
            "0 mismatches",
            {"mismatches": expected_mismatches[:20]},
        )
    )

    duplicate_keys = ["forecast_stage", "forecast_date", "target_period", "model_name"]
    duplicates = frame.loc[frame.duplicated(duplicate_keys, keep=False)]
    checks.append(
        AuditCheck(
            "Data integrity",
            "One forecast per model, stage, and target quarter",
            _status(duplicates.empty),
            f"{len(duplicates)} duplicate rows",
            "0 duplicate rows",
            {"duplicates": duplicates.head(20).to_dict(orient="records")},
        )
    )

    valid_hashes = frame["information_set_hash"].notna() & (
        frame["information_set_hash"].astype(str).str.len() == 64
    )
    missing_hashes = int((~valid_hashes).sum())
    checks.append(
        AuditCheck(
            "Reproducibility",
            "Every forecast has a valid information-set hash",
            _status(missing_hashes == 0),
            f"{missing_hashes} invalid hashes",
            "0 invalid hashes",
            {},
        )
    )

    interval_violations: list[dict] = []
    for _, row in frame.iterrows():
        details = json.loads(row.get("interval_details_json") or "{}")
        maximum = details.get("max_prior_forecast_date")
        if maximum and pd.Timestamp(maximum) >= pd.Timestamp(row["forecast_date"]):
            interval_violations.append(
                {
                    "forecast_date": str(row["forecast_date"]),
                    "model_name": row["model_name"],
                    "max_prior_forecast_date": maximum,
                }
            )
    checks.append(
        AuditCheck(
            "Econometric validity",
            "Interval calibration uses prior forecast errors only",
            _status(not interval_violations),
            f"{len(interval_violations)} violations",
            "0 violations",
            {"violations": interval_violations[:20]},
        )
    )

    weight_violations: list[dict] = []
    if not diagnostics.empty:
        rolling = diagnostics.loc[
            diagnostics["model_name"] == "Rolling Bridge–DFM Ensemble"
        ]
        for _, row in rolling.iterrows():
            details = json.loads(row.get("details_json") or "{}")
            maximum = details.get("max_prior_forecast_date")
            if maximum and pd.Timestamp(maximum) >= pd.Timestamp(row["forecast_date"]):
                weight_violations.append(
                    {
                        "forecast_date": str(row["forecast_date"]),
                        "max_prior_forecast_date": maximum,
                    }
                )
    checks.append(
        AuditCheck(
            "Econometric validity",
            "Rolling ensemble weights use prior quarters only",
            _status(not weight_violations),
            f"{len(weight_violations)} violations",
            "0 violations",
            {"violations": weight_violations[:20]},
        )
    )


    champion_violations: list[dict] = []
    if not diagnostics.empty:
        champion_rows = diagnostics.loc[
            diagnostics["model_name"] == ROBUST_STAGE_ADAPTIVE_MODEL_NAME
        ]
        for _, row in champion_rows.iterrows():
            details = json.loads(row.get("details_json") or "{}")
            maximum = details.get("max_prior_forecast_date")
            if maximum and pd.Timestamp(maximum) >= pd.Timestamp(row["forecast_date"]):
                champion_violations.append(
                    {
                        "forecast_date": str(row["forecast_date"]),
                        "selected_component": details.get("selected_component"),
                        "max_prior_forecast_date": maximum,
                    }
                )
    checks.append(
        AuditCheck(
            "Econometric validity",
            "Robust shadow selection uses prior quarters only",
            _status(not champion_violations),
            f"{len(champion_violations)} violations",
            "0 violations",
            {"violations": champion_violations[:20]},
        )
    )

    checks.append(
        AuditCheck(
            "Econometric validity",
            "Target-quarter GDP is absent from forecast information sets",
            _status(target_snapshot_leakage_count == 0),
            f"{target_snapshot_leakage_count} leaked snapshots",
            "0 leaked snapshots",
            {},
        )
    )
    checks.append(
        AuditCheck(
            "Econometric validity",
            "No observation is dated after its information cutoff",
            _status(future_observation_count == 0),
            f"{future_observation_count} future-dated observations",
            "0 future-dated observations",
            {},
        )
    )
    return checks
