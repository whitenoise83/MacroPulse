from __future__ import annotations

import argparse

from macropulse.labour.interval_calibration import (
    run_prior_only_labour_interval_calibration,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calibrate Model 1C intervals from strictly prior vintage forecast errors."
    )
    parser.add_argument("--backtest-id", default=None)
    parser.add_argument("--coverage", type=float, default=None)
    parser.add_argument("--minimum-prior-errors", type=int, default=None)
    parser.add_argument("--rolling-window", type=int, default=None)
    parser.add_argument("--decay", type=float, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_prior_only_labour_interval_calibration(
        backtest_id=args.backtest_id,
        coverage=args.coverage,
        minimum_prior_errors=args.minimum_prior_errors,
        rolling_window=args.rolling_window,
        decay=args.decay,
    )
    frame = result["results"]
    usable = frame.loc[frame["calibration_status"] == "calibrated"]
    summary = (
        usable.groupby(["target_series", "forecast_stage", "model_name"])
        .agg(
            observations=("interval_covered", "count"),
            coverage=("interval_covered", "mean"),
            average_half_width=("interval_half_width", "mean"),
            mean_interval_score=("interval_score", "mean"),
        )
        .reset_index()
        .sort_values(["target_series", "forecast_stage", "model_name"])
    )
    print("Model 1C prior-only interval calibration complete")
    print(f"Calibration ID: {result['calibration_id']}")
    print(f"Backtest ID: {result['backtest_id']}")
    print(f"Status: {result['status']}")
    print(f"Method: {result['method']}")
    print(f"Target coverage: {result['coverage']:.0%}")
    print(f"Minimum prior errors: {result['minimum_prior_errors']}")
    print(f"Rolling window: {result['rolling_window']}")
    print(f"Decay: {result['decay']:.3f}")
    print(f"Calibrated rows: {len(usable):,}")
    print(f"Warm-up rows: {int((frame['calibration_status'] == 'warmup').sum()):,}")
    print()
    print("Calibrated coverage")
    if summary.empty:
        print("No calibrated intervals were generated.")
    else:
        print(summary.to_string(index=False, float_format=lambda value: f"{value:.3f}"))


if __name__ == "__main__":
    main()
