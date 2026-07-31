from __future__ import annotations

import argparse
import json

import pandas as pd

from macropulse.labour.vintage_backtest import run_vintage_labour_backtest


def _csv_list(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Model 1C release-staged pseudo-real-time ALFRED backtest."
    )
    parser.add_argument("--start", default="2016-01", help="First target month in YYYY-MM format.")
    parser.add_argument("--end", default=None, help="Last target month in YYYY-MM format.")
    parser.add_argument("--targets", default=None, help="Comma-separated target series IDs.")
    parser.add_argument("--stages", default=None, help="Comma-separated forecast stage codes.")
    parser.add_argument("--refresh-snapshots", action="store_true")
    parser.add_argument("--pause-seconds", type=float, default=0.15)
    args = parser.parse_args()

    result = run_vintage_labour_backtest(
        start_period=args.start,
        end_period=args.end,
        target_ids=_csv_list(args.targets),
        stage_codes=_csv_list(args.stages),
        refresh_snapshots=args.refresh_snapshots,
        pause_seconds=args.pause_seconds,
    )
    print()
    print("Model 1C vintage labour backtest complete")
    print(f"Backtest ID: {result['backtest_id']}")
    print(f"Status: {result['status']}")
    print(f"Forecast rows: {len(result['results']):,}")
    pending = sum(item.get("kind") == "pending" for item in result["notices"])
    warmup = sum(item.get("kind") == "training_warmup" for item in result["notices"])
    print(f"Pending target months: {pending}")
    print(f"Expected training warm-ups: {warmup}")
    print(f"Hard issues: {len(result['hard_issues'])}")
    print()
    print("Stage metrics")
    rows: list[dict] = []
    for target, stages in result["metrics"].items():
        for stage, models in stages.items():
            for model, metrics in models.items():
                rows.append({
                    "target_series": target,
                    "forecast_stage": stage,
                    "model_name": model,
                    **metrics,
                })
    if rows:
        frame = pd.DataFrame(rows).sort_values(
            ["target_series", "forecast_stage", "rmse", "mae"]
        )
        print(frame.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    else:
        print("No evaluated forecasts were produced.")
    if result["hard_issues"]:
        print()
        print("First hard issues")
        print(json.dumps(result["hard_issues"][:10], indent=2, default=str))


if __name__ == "__main__":
    main()
