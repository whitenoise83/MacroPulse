from __future__ import annotations

import argparse
from datetime import date

import pandas as pd

from macropulse.labour.service import run_labour_nowcast_suite


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return pd.Timestamp(value).date()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the governed Model 1C live labour forecast."
    )
    parser.add_argument(
        "--as-of",
        help=(
            "Optional information cutoff in YYYY-MM-DD format. Current stored "
            "observations are filtered to this date."
        ),
    )
    parser.add_argument(
        "--skip-news",
        action="store_true",
        help="Store the governed forecast without automatically building news decomposition.",
    )
    args = parser.parse_args()
    result = run_labour_nowcast_suite(
        information_cutoff=_parse_date(args.as_of),
        build_news=not args.skip_news,
    )
    identity = result["identity"]
    lifecycle = str(identity["lifecycle_status"])
    print()
    print("Model 1C governed labour nowcast complete")
    print(f"Run ID: {result['run_id']}")
    print(f"Model: {identity['model_id']} v{identity['model_version']} ({lifecycle})")
    print(f"Candidate validation ID: {result['candidate_validation_id']}")
    print(f"Backtest ID: {result['backtest_id']}")
    print(f"Information cutoff: {result['information_cutoff']}")
    print(f"Data as of: {result['data_as_of']}")
    print(f"Information-set hash: {result['information_set_hash']}")
    print(f"Model-state hash: {result['model_state_hash']}")
    print(f"Governance signature: {result['governance_signature']}")
    if lifecycle == "production":
        print("Lifecycle: production-approved governed live forecast")
    else:
        print("Lifecycle: governed live candidate - not production approved")
    print()
    display = result["forecasts"].copy()
    print(
        display[
            [
                "target_name",
                "target_period",
                "target_unit",
                "forecast_stage",
                "stable_model_name",
                "stable_point_forecast",
                "lower_80",
                "upper_80",
                "shadow_model_name",
                "shadow_point_forecast",
            ]
        ].to_string(index=False, float_format=lambda value: f"{value:.3f}")
    )
    print()
    news = result.get("news") or {}
    print(f"News decomposition: {news.get('status', 'not run')}")
    if news.get("previous_run_id"):
        print(f"Previous governed run: {news['previous_run_id']}")
    if "maximum_residual" in news:
        print(f"Maximum news reconciliation residual: {news['maximum_residual']:.3e}")


if __name__ == "__main__":
    main()
