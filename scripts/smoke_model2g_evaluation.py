from __future__ import annotations

import pandas as pd

from macropulse.bvar.data import REQUIRED_SERIES, build_complete_quarter_panel
from macropulse.bvar.evaluation import (
    OutcomeObservation,
    aggregate_metrics,
    evaluate_origin,
)
from macropulse.bvar.origins import derive_origin_grid, validate_origin_grid
from macropulse.data.repository import MacroRepository


TERMINAL_QUARTER = pd.Period("2026Q1", freq="Q")
SMOKE_SIMULATIONS = 200
SMOKE_SEED = 20260904


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


def snapshot(repo: MacroRepository, cutoff):
    return repo.historical_snapshot(
        as_of_date=cutoff,
        series_ids=list(REQUIRED_SERIES),
    )


def main() -> int:
    repo = MacroRepository()
    grid = derive_origin_grid(
        common_cutoffs(repo),
        lambda cutoff: snapshot(repo, cutoff),
    )
    validate_origin_grid(grid)

    quarters = pd.PeriodIndex(grid["origin_quarter"], freq="Q")
    grid = grid.loc[quarters <= TERMINAL_QUARTER].reset_index(drop=True)
    validate_origin_grid(grid)

    target_origin = TERMINAL_QUARTER - 8
    row = grid.loc[
        grid["origin_quarter"].astype(str) == str(target_origin)
    ]
    if len(row) != 1:
        raise RuntimeError("Smoke origin not uniquely available.")
    row = row.iloc[0]

    origin_snapshot = snapshot(repo, row["as_of_date"])
    panel = build_complete_quarter_panel(
        origin_snapshot,
        row["as_of_date"],
    )

    outcome_rows = {
        str(item.origin_quarter): item
        for item in grid.itertuples(index=False)
    }
    outcomes = {}
    for horizon in (1, 2, 4, 8):
        target = str(target_origin + horizon)
        item = outcome_rows[target]
        target_snapshot = snapshot(repo, item.as_of_date)
        target_panel = build_complete_quarter_panel(
            target_snapshot,
            item.as_of_date,
        )
        outcomes[horizon] = OutcomeObservation(
            horizon=horizon,
            target_quarter=target,
            values=target_panel.loc[
                pd.Period(target, freq="Q")
            ].to_numpy(dtype=float),
            outcome_as_of_date=item.as_of_date,
            outcome_snapshot_hash=str(item.source_snapshot_hash),
        )

    records = evaluate_origin(
        panel,
        origin_id=str(row["origin_id"]),
        origin_quarter=str(row["origin_quarter"]),
        origin_as_of_date=row["as_of_date"],
        outcomes=outcomes,
        simulations=SMOKE_SIMULATIONS,
        base_seed=SMOKE_SEED,
    )
    aggregate = aggregate_metrics(records)

    print("Model 2G pseudo-real-time read-only smoke")
    print("Origin: " + str(row["origin_quarter"]))
    print("Origin cutoff: " + str(row["as_of_date"]))
    print("Resolved horizons: 1, 2, 4, 8")
    print("Models: 6 BVAR candidates + 3 benchmarks")
    print("Simulations per model: " + str(SMOKE_SIMULATIONS))
    print("Evaluation rows: " + str(len(records)))
    print()
    summary = (
        aggregate.groupby(["model_id", "model_family"], as_index=False)
        .agg(
            n_cells=("n", "size"),
            mean_lpd=("mean_log_predictive_density", "mean"),
            mean_crps=("mean_crps", "mean"),
            mean_rmse=("rmse", "mean"),
        )
        .sort_values(["model_family", "model_id"])
    )
    print(summary.to_string(index=False))
    print()
    print("Smoke is read-only and does not freeze candidate selection.")
    print("Outcomes use first common exact-vintage target-quarter panels.")
    print("No revised-data fallback or future-information fallback was used.")
    print("Production authority: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
