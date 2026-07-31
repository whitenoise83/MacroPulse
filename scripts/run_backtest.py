from __future__ import annotations

import argparse
from datetime import date

import pandas as pd

from macropulse.backtesting.pseudo_realtime import (
    BacktestConfig,
    run_pseudo_realtime_backtest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the MacroPulse quarter-end pseudo-real-time GDP backtest."
    )
    parser.add_argument(
        "--start",
        default="2020-03-31",
        help="First quarter included, as YYYY-MM-DD. Default: 2020-03-31.",
    )
    parser.add_argument(
        "--end",
        default=date.today().isoformat(),
        help="Last date included, as YYYY-MM-DD. Default: today.",
    )
    parser.add_argument(
        "--refresh-snapshots",
        action="store_true",
        help="Redownload historical snapshots even when they are cached.",
    )
    parser.add_argument(
        "--request-pause",
        type=float,
        default=0.15,
        help="Pause between FRED requests in seconds. Default: 0.15.",
    )
    parser.add_argument(
        "--skip-dfm",
        action="store_true",
        help="Run only the Bridge and AR(1) benchmark models.",
    )
    parser.add_argument(
        "--include-legacy-ensembles",
        action="store_true",
        help="Also calculate the former AR-contaminated equal-weight ensembles.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = BacktestConfig(
        start_date=args.start,
        end_date=args.end,
        refresh_snapshots=args.refresh_snapshots,
        request_pause_seconds=max(0.0, args.request_pause),
        include_dfm=not args.skip_dfm,
        include_legacy_ensembles=args.include_legacy_ensembles,
    )

    output = run_pseudo_realtime_backtest(config=config, progress=print)

    print("\nBacktest complete")
    print(f"ID: {output['backtest_id']}")
    print(f"Status: {output['status']}")
    print(f"Forecast rows: {len(output['results']):,}")
    print(f"Pending outcomes: {len(output['pending_outcomes']):,}")
    print(f"Skipped quarters: {len(output['skipped_quarters']):,}")
    print(f"DFM failures: {len(output['model_failures']):,}")

    metrics: pd.DataFrame = output["metrics"]
    if not metrics.empty:
        display_columns = [
            "model_name",
            "observations",
            "rmse",
            "trimmed_rmse_10",
            "mae",
            "median_ae",
            "bias",
            "direction_accuracy",
            "direction_skill",
            "interval_coverage",
            "win_rate",
        ]
        display = metrics[display_columns].copy()
        for column in [
            "rmse",
            "trimmed_rmse_10",
            "mae",
            "median_ae",
            "bias",
        ]:
            display[column] = display[column].round(3)
        for column in [
            "direction_accuracy",
            "direction_skill",
            "interval_coverage",
            "win_rate",
        ]:
            display[column] = (display[column] * 100).round(1).astype(str) + "%"
        print("\nModel metrics")
        print(display.to_string(index=False))

    if output["pending_outcomes"]:
        print("\nPending outcomes")
        for item in output["pending_outcomes"]:
            print(
                f"  {item['target_period']} ({item['forecast_date']}): "
                f"{item['reason']}"
            )

    if output["skipped"]:
        print("\nIssues")
        for item in output["skipped"]:
            label = item.get("model_name", item.get("scope", "issue"))
            print(
                f"  {item['target_period']} ({item['forecast_date']}) "
                f"[{label}]: {item['reason']}"
            )


if __name__ == "__main__":
    main()
