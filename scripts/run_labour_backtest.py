from __future__ import annotations

import argparse

import pandas as pd

from macropulse.labour.backtest import run_chronological_labour_backtest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the latest-revised Model 1C chronological baseline backtest."
    )
    parser.add_argument(
        "--start",
        default="2016-01",
        help="First evaluated target month in YYYY-MM format.",
    )
    args = parser.parse_args()
    result = run_chronological_labour_backtest(start_date=args.start)
    print()
    print("Model 1C labour baseline backtest complete")
    print(f"Backtest ID: {result['backtest_id']}")
    print("Method: chronological expanding window using latest-revised data")
    print("Research status: engineering benchmark only; not pseudo-real-time")
    print()
    rows: list[dict] = []
    for target, models in result["metrics"].items():
        for model, metrics in models.items():
            rows.append({"target_series": target, "model_name": model, **metrics})
    if rows:
        frame = pd.DataFrame(rows).sort_values(["target_series", "rmse", "mae"])
        print(frame.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    else:
        print("No evaluated observations were produced.")


if __name__ == "__main__":
    main()
