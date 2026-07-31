from __future__ import annotations

import argparse

from macropulse.inflation.validation import run_inflation_vintage_validation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the latest Model 1B vintage inflation backtest."
    )
    parser.add_argument("--backtest-id", default=None)
    parser.add_argument("--minimum-months", type=int, default=36)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_inflation_vintage_validation(
        backtest_id=args.backtest_id,
        minimum_months_per_stage=args.minimum_months,
    )
    print("Model 1B vintage validation complete")
    print(f"Validation ID: {result['validation_id']}")
    print(f"Backtest ID: {result['backtest_id']}")
    if result.get("calibration_id"):
        print(f"Calibration ID: {result['calibration_id']}")
    print(f"Status: {result['status']}")
    print(f"Passed: {result['passed']}")
    print(f"Failed: {result['failed']}")
    print(f"Warnings: {result['warnings']}")
    print(f"Report: {result['report_path']}")
    attention = result["checks"].loc[result["checks"]["status"] != "pass"]
    if not attention.empty:
        print()
        print("Checks requiring attention")
        print(attention.to_string(index=False))


if __name__ == "__main__":
    main()
