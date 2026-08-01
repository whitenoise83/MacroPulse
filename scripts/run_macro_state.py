from __future__ import annotations

import argparse
from datetime import date

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.service import run_macro_state


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Model 1D Unified US Macro State Engine."
    )
    parser.add_argument(
        "--as-of",
        help="State information cutoff in YYYY-MM-DD format. Defaults to today.",
    )
    args = parser.parse_args()
    as_of = date.fromisoformat(args.as_of) if args.as_of else None

    result = run_macro_state(
        repository=MacroRepository(),
        as_of=as_of,
    )

    print("Model 1D unified macro state complete")
    print(f"Run ID: {result['run_id']}")
    print(
        f"Model: {result['model_id']} v{result['model_version']} "
        f"({result['lifecycle_status']})"
    )
    print(f"State as of: {result['state_as_of']}")
    print(
        "Primary regime: "
        f"{result['primary_regime']['label']} "
        f"({result['primary_regime']['code']})"
    )
    print(
        f"Overall confidence: {result['overall_confidence']:.1f}/100"
    )
    print(
        f"Source cutoff spread: {result['cutoff_spread_days']} days"
    )
    print()
    print("Dimensions")
    print(
        result["dimensions"][
            [
                "dimension",
                "score",
                "lower_score",
                "upper_score",
                "label",
                "confidence",
                "delta_score",
            ]
        ].to_string(index=False)
    )
    print()
    print("Source inputs")
    print(
        result["inputs"][
            [
                "source_model_id",
                "source_target",
                "target_period",
                "forecast_stage",
                "point_forecast",
                "lower_80",
                "upper_80",
                "information_cutoff",
            ]
        ].to_string(index=False)
    )
    print()
    print(f"Risk flags: {len(result['risk_flags'])}")
    for flag in result["risk_flags"]:
        print(
            f"- [{flag['severity']}] {flag['code']}: "
            f"{flag['message']}"
        )
    print(f"Source bundle hash: {result['source_bundle_hash']}")
    print(f"State hash: {result['state_hash']}")


if __name__ == "__main__":
    main()
