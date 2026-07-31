from __future__ import annotations

import argparse

import pandas as pd

from macropulse.inflation.vintage_backtest import run_vintage_inflation_backtest


def _csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Model 1B pseudo-real-time ALFRED inflation backtesting."
    )
    parser.add_argument("--start", default="2015-01", help="First target month, YYYY-MM.")
    parser.add_argument("--end", default=None, help="Final target month, YYYY-MM.")
    parser.add_argument(
        "--targets",
        default=None,
        help="Comma-separated target IDs. Default: all four inflation targets.",
    )
    parser.add_argument(
        "--stages",
        default=None,
        help=(
            "Comma-separated stages: month_open,mid_month,month_end,pre_release. "
            "Default: all stages."
        ),
    )
    parser.add_argument(
        "--refresh-snapshots",
        action="store_true",
        help="Replace cached ALFRED information sets.",
    )
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=0.10,
        help="Pause between uncached FRED requests.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_vintage_inflation_backtest(
        start_period=args.start,
        end_period=args.end,
        target_ids=_csv(args.targets),
        stage_codes=_csv(args.stages),
        refresh_snapshots=args.refresh_snapshots,
        pause_seconds=args.pause_seconds,
    )
    rows = []
    for target, stages in result["metrics"].items():
        for stage, models in stages.items():
            for model, values in models.items():
                rows.append(
                    {
                        "target_series": target,
                        "forecast_stage": stage,
                        "model_name": model,
                        **values,
                    }
                )
    metrics = pd.DataFrame(rows)
    notices = result["notices"]
    pending = [item for item in notices if item.get("kind") == "pending"]
    warmup = [item for item in notices if item.get("kind") == "warmup"]
    issues = [
        item for item in notices if item.get("kind") not in {"pending", "warmup"}
    ]

    print()
    print("Model 1B vintage inflation backtest complete")
    print(f"ID: {result['backtest_id']}")
    print(f"Status: {result['status']}")
    print(f"Forecast rows: {len(result['results']):,}")
    print(f"Pending target months: {len(pending):,}")
    print(f"Expected training warm-up skips: {len(warmup):,}")
    print(f"Issues: {len(issues):,}")
    print()
    print("Stage metrics")
    if metrics.empty:
        print("No metrics were generated.")
    else:
        columns = [
            "target_series",
            "forecast_stage",
            "model_name",
            "observations",
            "rmse",
            "mae",
            "bias",
            "median_ae",
            "max_abs_error",
            "interval_coverage",
            "average_days_to_release",
        ]
        metrics = metrics[columns].sort_values(
            ["target_series", "forecast_stage", "rmse"]
        )
        print(metrics.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    if pending:
        print()
        print("Pending target months")
        for item in pending:
            print(f"  {item['target_series']} {item['target_period']}: {item['message']}")
    if issues:
        print()
        print("Issues")
        for item in issues[:30]:
            label = " ".join(
                str(item.get(key, ""))
                for key in ["target_series", "target_period", "forecast_stage"]
            ).strip()
            print(f"  {label}: {item['message']}")
        if len(issues) > 30:
            print(f"  ... {len(issues) - 30} additional issues stored in DuckDB.")


if __name__ == "__main__":
    main()
