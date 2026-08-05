from __future__ import annotations

import argparse
from datetime import date

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.prospective_shadow_service import (
    run_macro_state_prospective_shadow,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run Model 1D v0.3.8 prospective source-versus-"
            "rolling-frequency shadow prediction."
        )
    )
    parser.add_argument(
        "--as-of",
        help=(
            "Information cutoff in YYYY-MM-DD format. Defaults to today. "
            "The shadow state date is the month-end containing this cutoff."
        ),
    )
    args = parser.parse_args()
    as_of = date.fromisoformat(args.as_of) if args.as_of else None

    result = run_macro_state_prospective_shadow(
        repository=MacroRepository(),
        as_of=as_of,
    )

    print("Model 1D prospective transition shadow prediction complete")
    print(f"Shadow run ID: {result['shadow_run_id']}")
    print(
        f"Model: {result['model_id']} v{result['model_version']} "
        f"({result['lifecycle_status']})"
    )
    print(f"State date: {result['state_date']}")
    print(f"Information cutoff: {result['information_cutoff']}")
    print(
        "Expected fixed-horizon target availability: "
        f"{result['target_expected_available_date']}"
    )
    print(f"Source macro-state run: {result['source_macro_state_run_id']}")
    print(f"Frozen source candidate: {result['source_candidate_id']}")
    print()
    print("Predictions")
    print(
        result["predictions"][
            [
                "benchmark_id",
                "predicted_family",
                "top1_probability",
                "top2_family",
                "top2_probability",
                "entropy",
                "probability_vector_hash",
            ]
        ].to_string(index=False)
    )
    print()
    print("Frozen source dimensions")
    print(
        result["dimensions"][
            [
                "dimension",
                "score",
                "lower_score",
                "upper_score",
                "label",
                "confidence",
                "source_information_cutoff",
            ]
        ].to_string(index=False)
    )
    print()
    print(
        "Governance: "
        f"{result['governance']['status'].upper()} "
        "(research only; promotion authority none)"
    )
    print(f"Information-set hash: {result['information_set_hash']}")
    print(f"Source-bundle hash: {result['source_bundle_hash']}")


if __name__ == "__main__":
    main()
