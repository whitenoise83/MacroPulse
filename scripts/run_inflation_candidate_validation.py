from __future__ import annotations

import argparse

from macropulse.inflation.candidate_validation import (
    run_inflation_candidate_validation,
)
from macropulse.inflation.policy import SELECTED_INTERVAL_METHOD


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the Model 1B stable target-stage point policy, its prior-only "
            "adaptive shadow, and the selected exp-weighted 80% interval method."
        )
    )
    parser.add_argument("--backtest-id", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_inflation_candidate_validation(backtest_id=args.backtest_id)
    print("Model 1B candidate validation complete")
    print(f"Validation ID: {result['validation_id']}")
    print(f"Backtest ID: {result['backtest_id']}")
    print(f"Status: {result['status']}")
    print(f"Passed: {result['passed']}")
    print(f"Failed: {result['failed']}")
    print(f"Warnings: {result['warnings']}")
    print("Point policy: stable candidate")
    print("Adaptive selector: shadow challenger only")
    print(f"Interval candidate: {SELECTED_INTERVAL_METHOD}")
    print(f"Report: {result['report_path']}")
    attention = result["checks"].loc[result["checks"]["status"] != "pass"]
    if not attention.empty:
        print()
        print("Checks requiring attention")
        print(attention.to_string(index=False))


if __name__ == "__main__":
    main()
