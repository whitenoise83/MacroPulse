from __future__ import annotations

import argparse

import pandas as pd

from macropulse.governance.validation import run_model_validation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run automated validation gates for MacroPulse Model 1A."
    )
    parser.add_argument("--stage-backtest-id", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_model_validation(stage_backtest_id=args.stage_backtest_id)
    summary = result.get("summary", {})
    checks = result.get("checks", pd.DataFrame())

    passed = int(summary.get("passed", 0))
    failed = int(summary.get("failed", 0))
    warnings = int(summary.get("warnings", 0))

    # Defensive fallback for older/custom validation result shapes.
    if not checks.empty:
        passed = int(summary.get("passed", (checks["status"] == "pass").sum()))
        failed = int(summary.get("failed", (checks["status"] == "fail").sum()))
        warnings = int(summary.get("warnings", (checks["status"] == "warning").sum()))

    print("Model validation complete")
    print(f"Validation ID: {result['validation_id']}")
    print(f"Status: {result['status']}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Warnings: {warnings}")
    print(f"Report: {result['report_path']}")

    if checks.empty:
        print("\nNo validation checks were returned.")
        return

    display_columns = [
        "gate_name",
        "check_name",
        "status",
        "observed_value",
        "threshold",
    ]

    attention = checks.loc[checks["status"].isin(["fail", "warning"]), display_columns]
    if not attention.empty:
        print("\nChecks requiring attention")
        print(attention.to_string(index=False))

    print("\nAll checks")
    print(checks[display_columns].to_string(index=False))


if __name__ == "__main__":
    main()
