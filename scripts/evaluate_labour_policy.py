from __future__ import annotations

import argparse

import pandas as pd

from macropulse.labour.policy import (
    SELECTED_INTERVAL_METHOD,
    STABLE_POLICY,
    run_labour_policy_evaluation,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the Model 1C stable labour policy, prior-only adaptive "
            "shadow, regime robustness, and calibrated interval performance."
        )
    )
    parser.add_argument("--backtest-id", default=None)
    return parser.parse_args()


def _print_frame(frame: pd.DataFrame) -> None:
    if frame.empty:
        print("Insufficient eligible history.")
    else:
        print(frame.to_string(index=False, float_format=lambda value: f"{value:.3f}"))


def main() -> None:
    args = parse_args()
    result = run_labour_policy_evaluation(backtest_id=args.backtest_id)
    print("Model 1C policy evaluation complete")
    print(f"Backtest ID: {result['backtest_id']}")
    print(f"Calibration ID: {result['calibration_id'] or 'not available'}")
    print()
    print("Stable candidate policy")
    policy_rows = [
        {"target_series": target, "forecast_stage": stage, "model_name": model}
        for target, stages in STABLE_POLICY.items()
        for stage, model in stages.items()
    ]
    _print_frame(pd.DataFrame(policy_rows).sort_values(["target_series", "forecast_stage"]))
    print()
    print("Fixed-policy performance")
    _print_frame(result["fixed_summary"])
    print()
    print("Prior-only shadow performance")
    _print_frame(result["shadow_summary"])
    print()
    print("Fixed versus shadow on identical eligible months")
    _print_frame(result["common_comparison"])
    print()
    print("Shadow switching stability")
    _print_frame(result["switching_summary"])
    print()
    print("Fixed-policy regime performance")
    _print_frame(result["regime_summary"])
    print()
    print(f"Stable-policy interval diagnostics: {SELECTED_INTERVAL_METHOD}")
    _print_frame(result["fixed_interval_summary"])
    print()
    print("Shadow-policy interval diagnostics")
    _print_frame(result["shadow_interval_summary"])
    print()
    print(f"Report: {result['report_path']}")
    print(f"Fixed-policy CSV: {result['fixed_csv']}")
    print(f"Shadow-policy CSV: {result['shadow_csv']}")
    print(f"Common-sample comparison CSV: {result['common_csv']}")
    print(f"Shadow-switching CSV: {result['switching_csv']}")
    print(f"Regime CSV: {result['regime_csv']}")
    print(f"Fixed-policy intervals CSV: {result['fixed_interval_csv']}")
    print(f"Shadow-policy intervals CSV: {result['shadow_interval_csv']}")


if __name__ == "__main__":
    main()
