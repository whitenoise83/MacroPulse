from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from macropulse.data.repository import MacroRepository
from macropulse.evaluation.ledger import build_forecast_evaluation_ledger
from macropulse.evaluation.performance import (
    build_performance_tables,
    serialise_performance_report,
)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only MacroPulse Phase III forecast accuracy, calibration "
            "and descriptive drift report."
        )
    )
    parser.add_argument(
        "--as-of",
        type=_parse_date,
        default=date.today(),
        help="Evaluation information date in YYYY-MM-DD form.",
    )
    parser.add_argument(
        "--component",
        choices=("1A", "1B", "1C"),
        help="Optionally restrict the report to one production component.",
    )
    parser.add_argument(
        "--target-series",
        help="Optionally restrict the report to one governed target series.",
    )
    parser.add_argument(
        "--breakdowns",
        action="store_true",
        help="Also print stage and forecast-horizon breakdowns.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print deterministic JSON instead of the text report.",
    )
    return parser


def _filter_ledger(ledger, *, component, target_series):
    result = ledger
    if component:
        result = result.loc[result["component"] == component]
    if target_series:
        result = result.loc[result["target_series"] == target_series]
    return result.reset_index(drop=True)


def main() -> int:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parents[1]
    repository = MacroRepository()

    ledger = build_forecast_evaluation_ledger(
        repository,
        as_of=args.as_of,
        project_root=root,
    )
    ledger = _filter_ledger(
        ledger,
        component=args.component,
        target_series=args.target_series,
    )

    if args.json:
        print(
            json.dumps(
                serialise_performance_report(
                    ledger,
                    as_of=args.as_of,
                ),
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
        )
        return 0

    tables = build_performance_tables(ledger)
    resolved = int(
        ledger["evaluation_status"].astype(str).eq("resolved").sum()
    )
    unresolved = int(
        ledger["evaluation_status"].astype(str).str.startswith("unresolved_").sum()
    )
    invalid = int(
        ledger["evaluation_status"].astype(str).str.startswith("invalid_").sum()
    )

    print("MacroPulse Phase III forecast performance report")
    print(f"As of: {args.as_of}")
    print("Mode: read-only / descriptive evidence")
    print("Cross-target raw-error pooling: prohibited")
    print("Automatic model action: none")
    print(
        f"Rows: {len(ledger)}; resolved={resolved}; "
        f"unresolved={unresolved}; invalid={invalid}"
    )
    print()

    target = tables["target_metrics"]
    if target.empty:
        print("Target metrics: no resolved forecast observations.")
    else:
        print("Target metrics:")
        columns = [
            "component",
            "target_series",
            "n_resolved",
            "sample_status",
            "mae",
            "rmse",
            "bias",
            "interval_coverage_80",
            "directional_accuracy",
        ]
        print(target[columns].to_string(index=False))

    print()
    drift = tables["drift_metrics"]
    if drift.empty:
        print("Drift evidence: no resolved target series.")
    else:
        print("Drift evidence:")
        columns = [
            "component",
            "target_series",
            "drift_status",
            "total_resolved",
            "required_resolved",
            "mae_ratio_recent_to_reference",
            "bias_shift",
            "coverage_shift",
        ]
        print(drift[columns].to_string(index=False))

    if args.breakdowns:
        print()
        print("Stage metrics:")
        stage = tables["stage_metrics"]
        print(
            "<none>"
            if stage.empty
            else stage[
                [
                    "component",
                    "target_series",
                    "forecast_stage",
                    "n_resolved",
                    "sample_status",
                    "mae",
                    "bias",
                ]
            ].to_string(index=False)
        )

        print()
        print("Horizon metrics:")
        horizon = tables["horizon_metrics"]
        print(
            "<none>"
            if horizon.empty
            else horizon[
                [
                    "component",
                    "target_series",
                    "horizon_bucket",
                    "n_resolved",
                    "sample_status",
                    "mae",
                    "bias",
                ]
            ].to_string(index=False)
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
