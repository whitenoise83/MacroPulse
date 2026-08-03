from __future__ import annotations

import argparse

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.tournament_service import (
    run_macro_state_tournament,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Model 1D v0.3 normalization, weighting, threshold, "
            "and uncertainty tournament."
        )
    )
    parser.add_argument(
        "--reconstruction-id",
        help=(
            "Production-vintage reconstruction ID. Defaults to the latest "
            "available reconstruction."
        ),
    )
    args = parser.parse_args()

    result = run_macro_state_tournament(
        repository=MacroRepository(),
        reconstruction_id=args.reconstruction_id,
    )
    split = result["split"]
    print("Model 1D specification tournament complete")
    print(f"Tournament ID: {result['tournament_id']}")
    print(
        f"Model: {result['model_id']} v{result['model_version']} "
        "(development)"
    )
    print(f"Reconstruction ID: {result['reconstruction_id']}")
    print(
        "Chronological split: "
        f"training {split.training_dates[0]} to {split.training_dates[-1]} "
        f"({len(split.training_dates)}), "
        f"validation {split.validation_dates[0]} to "
        f"{split.validation_dates[-1]} "
        f"({len(split.validation_dates)}), "
        f"holdout {split.holdout_dates[0]} to "
        f"{split.holdout_dates[-1]} "
        f"({len(split.holdout_dates)})"
    )
    print(f"Core candidates evaluated: {result['core_candidates']}")
    print(
        "Uncertainty candidates evaluated: "
        f"{result['uncertainty_candidates']}"
    )
    print()
    print("Provisional winner")
    print(f"  Candidate: {result['selected_candidate_id']}")
    print(f"  Core: {result['selected_core_candidate_id']}")
    print(f"  Uncertainty: {result['selected_uncertainty_id']}")
    print(
        "  Validation score: "
        f"{result['selected_validation_score']:.2f}"
    )
    print(f"  Holdout rank: {result['selected_holdout_rank']}")
    print()
    print("Naive baselines")
    for key, value in result["baselines"].items():
        if isinstance(value, float):
            print(f"  {key}: {value:.3f}")
        else:
            print(f"  {key}: {value}")
    if result["warnings"]:
        print()
        print("Governance warnings")
        for warning in result["warnings"]:
            print(f"- {warning}")
    print()
    print("Top final candidates")
    print(
        result["final_leaderboard"][
            [
                "final_rank",
                "candidate_id",
                "final_score",
                "holdout_final_rank",
                "holdout_final_score",
                "brier_score",
                "log_loss",
                "coverage_80",
                "top1_accuracy",
            ]
        ].head(12).to_string(index=False)
    )
    print()
    print(f"Report: {result['report_path']}")
    print(
        "Status: provisional research winner; not candidate-approved or "
        "production-approved."
    )


if __name__ == "__main__":
    main()
