from __future__ import annotations

import argparse
from datetime import date

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.history_service import run_macro_state_history


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reconstruct Model 1D historical macro states."
    )
    parser.add_argument(
        "--start",
        default="2015-01-01",
        help="History start date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--end",
        help="History end date in YYYY-MM-DD format. Defaults to today.",
    )
    parser.add_argument(
        "--source-mode",
        choices=["production_vintage_backtests", "live_runs"],
        default="production_vintage_backtests",
        help=(
            "Use approved vintage backtests for genuine history, or stored "
            "live runs for operational snapshots."
        ),
    )
    args = parser.parse_args()

    result = run_macro_state_history(
        repository=MacroRepository(),
        start_date=date.fromisoformat(args.start),
        end_date=date.fromisoformat(args.end) if args.end else None,
        source_mode=args.source_mode,
    )

    print("Model 1D historical state reconstruction complete")
    print(f"Reconstruction ID: {result['reconstruction_id']}")
    print(
        f"Model: {result['model_id']} v{result['model_version']} "
        "(development)"
    )
    print(f"Source mode: {result['source_mode']}")
    print(f"History: {result['start_date']} to {result['end_date']}")
    print(
        f"Months reconstructed: {result['months_reconstructed']} / "
        f"{result['months_requested']} "
        f"({result['coverage_ratio']:.1%})"
    )
    print(
        f"Longest contiguous run: "
        f"{result['longest_contiguous_months']} months"
    )
    print(
        f"No-look-ahead audit: "
        f"{'pass' if result['no_look_ahead_pass'] else 'fail'}"
    )
    if result["lineage"]:
        print("Production validation lineage")
        print(
            f"  GDP: {result['lineage']['gdp_backtest_id']} "
            f"(validation {result['lineage']['gdp_validation_id']})"
        )
        print(
            f"  Inflation: "
            f"{result['lineage']['inflation_backtest_id']} "
            f"(validation "
            f"{result['lineage']['inflation_validation_id']})"
        )
        print(
            f"  Labour: {result['lineage']['labour_backtest_id']} "
            f"(validation {result['lineage']['labour_validation_id']})"
        )
    print()
    print("Latest reconstructed states")
    print(
        result["states"][
            [
                "state_date",
                "growth_score",
                "inflation_score",
                "labour_score",
                "primary_regime_label",
                "possible_regime_count",
                "source_cutoff_spread_days",
            ]
        ].tail(12).to_string(index=False)
    )
    print()
    print("Regime durations")
    if result["durations"].empty:
        print("No durations available.")
    else:
        print(
            result["durations"][
                [
                    "primary_regime_label",
                    "start_date",
                    "end_date",
                    "months",
                ]
            ].tail(20).to_string(index=False)
        )
    print()
    print("Transition matrix")
    if result["transition_matrix"].empty:
        print("No contiguous monthly transitions available.")
    else:
        print(result["transition_matrix"].round(3).to_string())


if __name__ == "__main__":
    main()
