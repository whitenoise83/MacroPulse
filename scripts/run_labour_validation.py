from __future__ import annotations

import argparse

from macropulse.labour.validation import run_labour_vintage_validation


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a Model 1C vintage labour backtest.")
    parser.add_argument("--backtest-id", default=None)
    parser.add_argument("--minimum-months", type=int, default=36)
    args = parser.parse_args()
    result = run_labour_vintage_validation(
        backtest_id=args.backtest_id,
        minimum_months_per_stage=args.minimum_months,
    )
    print("Model 1C vintage validation complete")
    print(f"Validation ID: {result['validation_id']}")
    print(f"Backtest ID: {result['backtest_id']}")
    print(f"Status: {result['status']}")
    print(f"Passed: {result['passed']}")
    print(f"Failed: {result['failed']}")
    print(f"Warnings: {result['warnings']}")
    print(f"Report: {result['report_path']}")
    attention = result["checks"].loc[result["checks"]["status"] != "pass"]
    if not attention.empty:
        print()
        print("Checks requiring attention")
        print(attention.drop(columns=["validation_id", "created_at"]).to_string(index=False))


if __name__ == "__main__":
    main()
