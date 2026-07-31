from __future__ import annotations

import argparse

import pandas as pd

from macropulse.inflation.backtest import run_chronological_inflation_backtest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Model 1B chronological baseline backtest."
    )
    parser.add_argument(
        "--start", default="2015-01", help="First monthly target period, YYYY-MM."
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_chronological_inflation_backtest(start_date=args.start)
    rows = []
    for target, models in result["metrics"].items():
        for model, metrics in models.items():
            rows.append({"target_series": target, "model_name": model, **metrics})
    table = pd.DataFrame(rows).sort_values(["target_series", "rmse"])
    print()
    print("Model 1B chronological baseline backtest complete")
    print(f"ID: {result['backtest_id']}")
    print("Method: expanding window using latest revised data (not vintage-aware)")
    print()
    if table.empty:
        print("No backtest observations were generated.")
    else:
        print(table.to_string(index=False, float_format=lambda value: f"{value:.3f}"))


if __name__ == "__main__":
    main()
