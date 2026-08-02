from __future__ import annotations

import argparse
import json

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.history_diagnostics import (
    diagnose_history_gaps,
    effective_coverage_metrics,
    transition_statistics,
    uncertainty_table,
)
from macropulse.macro_state.versioning import load_macro_state_governance


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Diagnose Model 1D historical coverage, transitions, and "
            "joint regime uncertainty."
        )
    )
    parser.add_argument(
        "--reconstruction-id",
        help="Specific reconstruction ID. Defaults to the latest run.",
    )
    args = parser.parse_args()

    repository = MacroRepository()
    repository.initialise()
    if args.reconstruction_id:
        run = repository.query_df(
            """
            SELECT *
            FROM macro_state_history_runs
            WHERE reconstruction_id = ?
            LIMIT 1
            """,
            [args.reconstruction_id],
        )
    else:
        run = repository.query_df(
            """
            SELECT *
            FROM macro_state_history_runs
            WHERE source_mode = 'production_vintage_backtests'
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
    if run.empty:
        raise RuntimeError(
            "No production-vintage Model 1D reconstruction was found."
        )

    reconstruction_id = str(run.iloc[0]["reconstruction_id"])
    states = repository.query_df(
        """
        SELECT *
        FROM macro_state_history_states
        WHERE reconstruction_id = ?
        ORDER BY state_date
        """,
        [reconstruction_id],
    )
    if states.empty:
        raise RuntimeError(
            f"Reconstruction {reconstruction_id} has no state rows."
        )

    config = load_macro_state_governance()
    minimum = int(config["history"]["transition_minimum_count"])
    coverage = effective_coverage_metrics(states)
    gaps = diagnose_history_gaps(repository, states)
    uncertainty = uncertainty_table(states)
    transitions = transition_statistics(states, minimum)

    print("Model 1D historical diagnostics complete")
    print(f"Reconstruction ID: {reconstruction_id}")
    print(
        "Effective common window: "
        f"{coverage['effective_start_date']} to "
        f"{coverage['effective_end_date']}"
    )
    print(
        "Effective coverage: "
        f"{len(states)} / {coverage['effective_months_requested']} "
        f"({coverage['effective_coverage_ratio']:.1%})"
    )
    print(f"Missing months: {coverage['gap_months']}")
    print(
        "Uncertainty method: "
        f"{config['history']['uncertainty_candidate']['method']}"
    )

    print("\nCoverage gaps")
    if gaps.empty:
        print("No missing effective-window months were diagnosed.")
    else:
        print(
            gaps[
                [
                    "state_date",
                    "source_model_id",
                    "source_target",
                    "target_period",
                    "forecast_stage",
                    "expected_model",
                    "reason",
                    "available_models",
                ]
            ].to_string(index=False)
        )

    print("\nLatest joint-regime diagnostics")
    latest = uncertainty.tail(12).copy()
    print(
        latest[
            [
                "state_date",
                "top_regime",
                "top_probability",
                "normalized_entropy",
                "effective_regimes",
                "material_regime_count",
            ]
        ].to_string(index=False)
    )
    print("\nLatest regime probability distributions")
    for row in latest.itertuples(index=False):
        probabilities = json.loads(row.probabilities_json)
        ranked = sorted(
            probabilities.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        summary = ", ".join(
            f"{regime}={probability:.1%}"
            for regime, probability in ranked
        )
        print(f"{row.state_date}: {summary}")

    print("\nTransition statistics")
    if transitions.empty:
        print("No contiguous monthly transitions are available.")
    else:
        print(
            transitions[
                [
                    "from_regime",
                    "to_regime",
                    "transition_count",
                    "from_regime_transitions",
                    "transition_probability",
                    "meets_minimum_count",
                ]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()
