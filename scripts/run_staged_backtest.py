from __future__ import annotations

import argparse
import json

import pandas as pd

from macropulse.backtesting.production_selection import (
    ROBUST_STAGE_ADAPTIVE_MODEL_NAME,
    STABLE_STAGE_POLICY_NAME,
)
from macropulse.backtesting.staged import (
    StageBacktestConfig,
    run_staged_pseudo_realtime_backtest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Model 1A pseudo-real-time GDP backtest at multiple "
            "within-quarter cutoffs."
        )
    )
    parser.add_argument("--start", default="2020-01-01", help="First target-quarter date, YYYY-MM-DD.")
    parser.add_argument("--end", default=None, help="Last target-quarter date, YYYY-MM-DD.")
    parser.add_argument(
        "--stages",
        default=(
            "early_quarter,after_month_1,after_month_2,"
            "quarter_end,pre_advance_release"
        ),
        help="Comma-separated forecast stages.",
    )
    parser.add_argument("--refresh-snapshots", action="store_true")
    parser.add_argument("--skip-dfm", action="store_true")
    parser.add_argument("--request-pause", type=float, default=0.10)
    return parser.parse_args()


def _ascii(value: object) -> str:
    return str(value).replace("–", "-").replace("—", "-")


def _selection_frame(diagnostics: pd.DataFrame, model_name: str) -> pd.DataFrame:
    frame = diagnostics.loc[diagnostics["model_name"] == model_name].copy()
    if frame.empty:
        return frame
    parsed = frame["details_json"].map(lambda value: json.loads(value or "{}"))
    frame["selected_component"] = parsed.map(lambda item: _ascii(item.get("selected_component", "Unknown")))
    frame["selection_method"] = parsed.map(lambda item: item.get("method", "Unknown"))
    frame["switched"] = parsed.map(lambda item: bool(item.get("switched", False)))
    return frame


def _stability(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for stage, group in frame.groupby("forecast_stage", sort=False):
        group = group.sort_values("forecast_date")
        selected = group["selected_component"].astype(str).tolist()
        switches = sum(left != right for left, right in zip(selected, selected[1:]))
        run_lengths: list[int] = []
        if selected:
            length = 1
            for left, right in zip(selected, selected[1:]):
                if left == right:
                    length += 1
                else:
                    run_lengths.append(length)
                    length = 1
            run_lengths.append(length)
        rows.append(
            {
                "forecast_stage": stage,
                "forecasts": len(group),
                "switches": switches,
                "average_duration": round(sum(run_lengths) / len(run_lengths), 2) if run_lengths else 0,
                "minimum_duration": min(run_lengths) if run_lengths else 0,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    stages = tuple(item.strip() for item in args.stages.split(",") if item.strip())
    config = StageBacktestConfig(
        start_date=args.start,
        end_date=args.end or StageBacktestConfig().end_date,
        stages=stages,
        refresh_snapshots=args.refresh_snapshots,
        request_pause_seconds=args.request_pause,
        include_dfm=not args.skip_dfm,
    )
    result = run_staged_pseudo_realtime_backtest(config=config, progress=print)

    print("\nStaged backtest complete")
    print(f"ID: {result['stage_backtest_id']}")
    print(f"Status: {result['status']}")
    print(f"Forecast rows: {len(result['results'])}")
    print(f"Pending outcomes: {len(result['pending_outcomes'])}")
    print(f"Skipped stages/quarters: {len(result['skipped'])}")
    print(f"DFM failures: {len(result['model_failures'])}")

    if not result["stage_metrics"].empty:
        display = result["stage_metrics"].copy()
        display["model_name"] = display["model_name"].map(_ascii)
        for column in [
            "rmse",
            "trimmed_rmse_10",
            "mae",
            "median_ae",
            "p90_abs_error",
            "max_abs_error",
            "bias",
            "average_interval_width",
            "median_interval_width",
            "interval_score_80",
            "coverage_p_value",
            "average_days_to_release",
        ]:
            if column in display:
                display[column] = display[column].round(3)
        for column in [
            "direction_accuracy",
            "direction_skill",
            "interval_coverage",
            "raw_interval_coverage",
            "win_rate",
        ]:
            if column in display:
                display[column] = display[column].map(
                    lambda value: f"{value:.1%}" if value == value else ""
                )
        print("\nStage metrics")
        print(display.to_string(index=False))

    diagnostics = result["diagnostics"]
    if not diagnostics.empty:
        stable = _selection_frame(diagnostics, STABLE_STAGE_POLICY_NAME)
        if not stable.empty:
            stable_distribution = (
                stable.groupby(["forecast_stage", "selected_component"])
                .size()
                .rename("forecasts")
                .reset_index()
            )
            print("\nStable Stage Policy components")
            print(stable_distribution.to_string(index=False))

        robust = _selection_frame(diagnostics, ROBUST_STAGE_ADAPTIVE_MODEL_NAME)
        if not robust.empty:
            robust_distribution = (
                robust.groupby(["forecast_stage", "selected_component"])
                .size()
                .rename("forecasts")
                .reset_index()
            )
            print("\nRobust Stage-Adaptive Policy selections")
            print(robust_distribution.to_string(index=False))
            print("\nRobust selector stability")
            print(_stability(robust).to_string(index=False))

    if result["pending_outcomes"]:
        print("\nPending outcomes")
        for item in result["pending_outcomes"]:
            print(f"  {item['target_period']}: {item['reason']}")

    if result["skipped"] or result["model_failures"]:
        print("\nIssues")
        for item in result["skipped"] + result["model_failures"]:
            print(
                f"  {item.get('target_period')} {item.get('forecast_stage', '')}: "
                f"{item['reason']}"
            )


if __name__ == "__main__":
    main()
