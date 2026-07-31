from __future__ import annotations

import argparse

import pandas as pd

from macropulse.inflation.policy import (
    SELECTED_INTERVAL_METHOD,
    STABLE_POLICY,
    run_policy_evaluation,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the Model 1B stable point-forecast policy, prior-only shadow "
            "selector, and predeclared interval-calibration candidates."
        )
    )
    parser.add_argument("--backtest-id", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_policy_evaluation(backtest_id=args.backtest_id)
    print("Model 1B policy evaluation complete")
    print(f"Backtest ID: {result['backtest_id']}")
    print()
    print("Stable candidate policy")
    policy_rows = [
        {"target_series": target, "forecast_stage": stage, "model_name": model}
        for target, stages in STABLE_POLICY.items()
        for stage, model in stages.items()
    ]
    print(pd.DataFrame(policy_rows).sort_values(["target_series", "forecast_stage"]).to_string(index=False))
    print()
    print("Fixed-policy performance")
    print(result["fixed_summary"].to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print()
    print("Prior-only shadow performance")
    if result["shadow_summary"].empty:
        print("Insufficient prior forecast-error history.")
    else:
        print(result["shadow_summary"].to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print()
    print("Fixed versus shadow on identical eligible months")
    if result["common_comparison"].empty:
        print("Insufficient common prior-only history.")
    else:
        print(result["common_comparison"].to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print()
    print("Shadow switching stability")
    if result["switching_summary"].empty:
        print("Insufficient prior-only history.")
    else:
        print(result["switching_summary"].to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print()
    print("Interval-method tournament")
    if result["interval_summary"].empty:
        print("Insufficient prior forecast-error history.")
    else:
        print(result["interval_summary"].to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print()
    print(f"Selected interval candidate: {SELECTED_INTERVAL_METHOD}")
    if result["selected_interval_summary"].empty:
        print("Insufficient calibrated history.")
    else:
        print(result["selected_interval_summary"].to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print()
    print(f"Report: {result['report_path']}")
    print(f"Fixed-policy CSV: {result['fixed_csv']}")
    print(f"Shadow-policy CSV: {result['shadow_csv']}")
    print(f"Common-sample comparison CSV: {result['common_csv']}")
    print(f"Shadow-switching CSV: {result['switching_csv']}")
    print(f"Interval-tournament CSV: {result['interval_csv']}")
    print(f"Selected-interval diagnostics CSV: {result['selected_interval_csv']}")


if __name__ == "__main__":
    main()
