from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from macropulse.bvar.data import REQUIRED_SERIES, build_complete_quarter_panel
from macropulse.bvar.evaluation import (
    OutcomeObservation,
    aggregate_metrics,
    canonical_frame_hash,
    evaluate_origin,
    select_bvar_candidate,
)
from macropulse.bvar.origins import derive_origin_grid, validate_origin_grid
from macropulse.data.repository import MacroRepository


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "MODEL2G_EVALUATION_CONTRACT.json"
EVIDENCE_PATH = ROOT / "MODEL2G_SELECTION_EVIDENCE.json"
BASE_MODEL2F_CLOSURE = "c63ee4df92dd372f883feea4fc86eabae79ab358"
TERMINAL_QUARTER = pd.Period("2026Q1", freq="Q")
CANONICAL_SIMULATIONS = 5000
CANONICAL_BASE_SEED = 20260904

IMPLEMENTATION_PATHS = (
    "MODEL2G_EVALUATION_CONTRACT.json",
    "src/macropulse/bvar/data.py",
    "src/macropulse/bvar/origins.py",
    "src/macropulse/bvar/model.py",
    "src/macropulse/bvar/probabilistic.py",
    "src/macropulse/bvar/benchmarks.py",
    "src/macropulse/bvar/evaluation.py",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def common_cutoffs(repo: MacroRepository) -> list:
    placeholders = ", ".join(["?"] * len(REQUIRED_SERIES))
    query = (
        "SELECT as_of_date FROM snapshot_downloads "
        "WHERE status = 'success' AND series_id IN (" + placeholders + ") "
        "GROUP BY as_of_date "
        "HAVING COUNT(DISTINCT series_id) = ? "
        "ORDER BY as_of_date"
    )
    params = [*REQUIRED_SERIES, len(REQUIRED_SERIES)]
    with repo.connect(read_only=True) as connection:
        rows = connection.execute(query, params).fetchall()
    return [row[0] for row in rows]


def load_snapshot(repo: MacroRepository, cutoff):
    return repo.historical_snapshot(
        as_of_date=cutoff,
        series_ids=list(REQUIRED_SERIES),
    )


def frozen_origin_grid(repo: MacroRepository) -> pd.DataFrame:
    cutoffs = common_cutoffs(repo)
    if not cutoffs:
        raise RuntimeError("No common Model 2 exact-vintage cutoffs found.")

    grid = derive_origin_grid(
        cutoffs,
        lambda cutoff: load_snapshot(repo, cutoff),
    )
    validate_origin_grid(grid)
    quarters = pd.PeriodIndex(grid["origin_quarter"], freq="Q")
    frozen = grid.loc[quarters <= TERMINAL_QUARTER].copy()
    if frozen.empty:
        raise RuntimeError("Frozen Model 2G origin inventory is empty.")
    if str(frozen.iloc[-1]["origin_quarter"]) != str(TERMINAL_QUARTER):
        raise RuntimeError(
            "Frozen terminal origin quarter 2026Q1 is not present."
        )
    validate_origin_grid(frozen)
    return frozen.reset_index(drop=True)


def outcome_inventory(
    repo: MacroRepository,
    grid: pd.DataFrame,
) -> dict[str, dict]:
    outcomes = {}
    for row in grid.itertuples(index=False):
        quarter = str(row.origin_quarter)
        snapshot = load_snapshot(repo, row.as_of_date)
        panel = build_complete_quarter_panel(snapshot, row.as_of_date)
        period = pd.Period(quarter, freq="Q")
        if period not in panel.index:
            raise RuntimeError(
                "Target quarter missing from its first common exact-vintage panel: "
                + quarter
            )
        outcomes[quarter] = {
            "values": panel.loc[period].to_numpy(dtype=float),
            "as_of_date": row.as_of_date,
            "snapshot_hash": str(row.source_snapshot_hash),
        }
    return outcomes


def evaluate(
    repo: MacroRepository,
    *,
    simulations: int,
    base_seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    grid = frozen_origin_grid(repo)
    outcomes_by_quarter = outcome_inventory(repo, grid)

    pieces = []
    admissible = grid[
        grid["admissible_for_pseudo_real_time"].astype(bool)
    ]

    total = len(admissible)
    for position, row in enumerate(admissible.itertuples(index=False), start=1):
        origin_period = pd.Period(row.origin_quarter, freq="Q")
        resolved = {}
        for horizon in (1, 2, 4, 8):
            target = str(origin_period + horizon)
            if target not in outcomes_by_quarter:
                continue
            item = outcomes_by_quarter[target]
            resolved[horizon] = OutcomeObservation(
                horizon=horizon,
                target_quarter=target,
                values=item["values"],
                outcome_as_of_date=item["as_of_date"],
                outcome_snapshot_hash=item["snapshot_hash"],
            )

        if not resolved:
            continue

        snapshot = load_snapshot(repo, row.as_of_date)
        panel = build_complete_quarter_panel(snapshot, row.as_of_date)

        print(
            f"[{position:02d}/{total:02d}] origin={row.origin_quarter} "
            f"resolved_horizons={','.join(str(x) for x in sorted(resolved))}"
        )
        pieces.append(
            evaluate_origin(
                panel,
                origin_id=str(row.origin_id),
                origin_quarter=str(row.origin_quarter),
                origin_as_of_date=row.as_of_date,
                outcomes=resolved,
                simulations=simulations,
                base_seed=base_seed,
            )
        )

    if not pieces:
        raise RuntimeError("No resolved pseudo-real-time evaluation cases.")

    records = pd.concat(pieces, ignore_index=True)
    aggregate = aggregate_metrics(records)
    selection = select_bvar_candidate(aggregate)
    return grid, records, aggregate, selection


def evidence_payload(
    grid: pd.DataFrame,
    records: pd.DataFrame,
    aggregate: pd.DataFrame,
    selection: pd.DataFrame,
) -> dict:
    selected = selection.loc[selection["selected"]].iloc[0]

    implementation_hashes = {
        path: sha256_file(ROOT / path)
        for path in IMPLEMENTATION_PATHS
    }

    inventory_hash = canonical_frame_hash(
        grid,
        sort_columns=["origin_quarter"],
    )
    records_hash = canonical_frame_hash(
        records,
        sort_columns=[
            "origin_quarter", "horizon", "variable", "model_id"
        ],
    )
    aggregate_hash = canonical_frame_hash(
        aggregate,
        sort_columns=["model_id", "variable", "horizon"],
    )
    selection_hash = canonical_frame_hash(
        selection,
        sort_columns=["rank"],
    )

    selection_rows = []
    for row in selection.itertuples(index=False):
        selection_rows.append(
            {
                "rank": int(row.rank),
                "candidate_id": str(row.candidate_id),
                "lags": int(row.lags),
                "shrinkage": float(row.shrinkage),
                "cells": int(row.cells),
                "minimum_cell_n": int(row.minimum_cell_n),
                "mean_log_predictive_density": float(
                    row.mean_log_predictive_density
                ),
                "mean_crps": float(row.mean_crps),
                "mean_rmse": float(row.mean_rmse),
                "selected": bool(row.selected),
            }
        )

    payload = {
        "schema_version": 1,
        "workstream": "2G",
        "base_model2f_closure_commit": BASE_MODEL2F_CLOSURE,
        "development_terminal_origin_quarter": str(TERMINAL_QUARTER),
        "canonical_simulations": CANONICAL_SIMULATIONS,
        "canonical_base_seed": CANONICAL_BASE_SEED,
        "origin_rows": int(len(grid)),
        "admissible_origin_rows": int(
            grid["admissible_for_pseudo_real_time"].astype(bool).sum()
        ),
        "evaluation_rows": int(len(records)),
        "aggregate_rows": int(len(aggregate)),
        "development_origin_inventory_hash": inventory_hash,
        "evaluation_records_hash": records_hash,
        "aggregate_metrics_hash": aggregate_hash,
        "selection_table_hash": selection_hash,
        "implementation_hashes": implementation_hashes,
        "selection_rule": {
            "eligible_models": "six_bvar_candidates_only",
            "primary_horizons": [1, 2, 4],
            "primary_metric": "mean_log_predictive_density",
            "primary_direction": "higher_is_better",
            "tie_break_1": "mean_crps_lower_is_better",
            "tie_break_2": "mean_rmse_lower_is_better",
            "tie_break_3": "candidate_id_lexicographic",
            "minimum_cell_n": 8,
        },
        "selection_table": selection_rows,
        "selected_candidate": {
            "candidate_id": str(selected.candidate_id),
            "lags": int(selected.lags),
            "shrinkage": float(selected.shrinkage),
            "mean_log_predictive_density": float(
                selected.mean_log_predictive_density
            ),
            "mean_crps": float(selected.mean_crps),
            "mean_rmse": float(selected.mean_rmse),
        },
        "benchmarks_compared": [
            "benchmark::univariate_ar4",
            "benchmark::classical_var4",
            "benchmark::historical_mean_random_walk",
        ],
        "outcome_rule": "first_common_exact_vintage_panel_for_target_quarter",
        "prospective_retuning_after_freeze": False,
        "automatic_switching_after_freeze": False,
        "production_authority": "none",
    }

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    payload["evidence_payload_hash"] = hashlib.sha256(canonical).hexdigest()
    return payload


def write_evidence(payload: dict) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if EVIDENCE_PATH.exists():
        existing = EVIDENCE_PATH.read_text(encoding="utf-8")
        if existing == text:
            print("Canonical Model 2G evidence already exists and is identical.")
            return
        raise RuntimeError(
            "MODEL2G_SELECTION_EVIDENCE.json already exists with different "
            "content; overwrite is prohibited."
        )
    EVIDENCE_PATH.write_text(text, encoding="utf-8", newline="\n")
    print("Wrote frozen evidence: " + str(EVIDENCE_PATH.name))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--simulations",
        type=int,
        default=CANONICAL_SIMULATIONS,
    )
    parser.add_argument(
        "--base-seed",
        type=int,
        default=CANONICAL_BASE_SEED,
    )
    parser.add_argument(
        "--freeze-evidence",
        action="store_true",
    )
    args = parser.parse_args()

    if args.freeze_evidence and (
        args.simulations != CANONICAL_SIMULATIONS
        or args.base_seed != CANONICAL_BASE_SEED
    ):
        raise SystemExit(
            "Frozen 2G evidence requires canonical simulations and base seed."
        )

    repo = MacroRepository()
    grid, records, aggregate, selection = evaluate(
        repo,
        simulations=args.simulations,
        base_seed=args.base_seed,
    )

    print()
    print("Model 2G pseudo-real-time evaluation complete")
    print("Frozen terminal origin: " + str(TERMINAL_QUARTER))
    print("Origin rows: " + str(len(grid)))
    print("Evaluation rows: " + str(len(records)))
    print()
    print(
        selection[
            [
                "rank",
                "candidate_id",
                "lags",
                "shrinkage",
                "minimum_cell_n",
                "mean_log_predictive_density",
                "mean_crps",
                "mean_rmse",
                "selected",
            ]
        ].to_string(index=False)
    )
    print()
    print(
        "Selection uses only frozen pseudo-real-time development evidence; "
        "benchmarks are comparison-only."
    )
    print("Prospective retuning after freeze: prohibited")
    print("Production authority: none")

    if args.freeze_evidence:
        write_evidence(
            evidence_payload(
                grid,
                records,
                aggregate,
                selection,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
