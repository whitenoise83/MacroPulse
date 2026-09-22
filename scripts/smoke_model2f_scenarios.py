from __future__ import annotations

import pandas as pd

from macropulse.bvar.data import REQUIRED_SERIES, build_complete_quarter_panel
from macropulse.bvar.model import candidate_grid, fit_bvar
from macropulse.bvar.scenario import (
    run_path_scenario,
    unconditional_baseline_path,
)
from macropulse.data.repository import MacroRepository


def latest_common_cutoff(repo: MacroRepository):
    placeholders = ", ".join(["?"] * len(REQUIRED_SERIES))
    query = (
        "SELECT MAX(as_of_date) FROM ("
        "SELECT as_of_date FROM snapshot_downloads "
        "WHERE status = 'success' AND series_id IN (" + placeholders + ") "
        "GROUP BY as_of_date "
        "HAVING COUNT(DISTINCT series_id) = ?"
        ")"
    )
    params = [*REQUIRED_SERIES, len(REQUIRED_SERIES)]
    with repo.connect(read_only=True) as connection:
        return connection.execute(query, params).fetchone()[0]


def main() -> int:
    repo = MacroRepository()
    cutoff = latest_common_cutoff(repo)
    if cutoff is None:
        print("Model 2F scenario smoke: COVERAGE_NOT_READY")
        return 2

    snapshot = repo.historical_snapshot(
        as_of_date=cutoff,
        series_ids=list(REQUIRED_SERIES),
    )
    panel = build_complete_quarter_panel(snapshot, cutoff)

    print("Model 2F deterministic path-scenario read-only smoke")
    print("As-of: " + str(cutoff))
    print(
        "Panel: "
        + str(panel.index[0])
        + " -> "
        + str(panel.index[-1])
        + " n="
        + str(len(panel))
    )
    print(
        "Scenario: policy rate fixed 1 percentage point above "
        "candidate baseline at horizons 1-4"
    )
    print("Candidates: 6; selection/ranking: prohibited in 2F")
    print()
    print(
        "p lambda h1_dGDP h1_dPCE h1_dUNRATE h1_dRATE "
        "h4_dGDP h4_dPCE h4_dUNRATE h4_dRATE scenario_id"
    )
    print("-" * 118)

    for candidate in candidate_grid():
        posterior = fit_bvar(panel, candidate)
        baseline = unconditional_baseline_path(panel, posterior)

        constraints = pd.DataFrame(
            [
                {
                    "horizon": horizon,
                    "variable": "policy_rate",
                    "value": float(
                        baseline.loc[
                            baseline["horizon"] == horizon,
                            "policy_rate",
                        ].iloc[0]
                    )
                    + 1.0,
                }
                for horizon in range(1, 5)
            ]
        )

        result = run_path_scenario(
            panel,
            posterior,
            constraints,
            scenario_name="policy_rate_plus_1pp_h1_h4",
        )

        comparison = result.comparison.set_index(
            ["horizon", "variable"]
        )

        def dev(horizon: int, variable: str) -> float:
            return float(
                comparison.loc[(horizon, variable), "deviation"]
            )

        print(
            f"{candidate.lags:1d} "
            f"{candidate.shrinkage:6.3f} "
            f"{dev(1, 'real_gdp_growth'):8.4f} "
            f"{dev(1, 'core_pce_inflation'):8.4f} "
            f"{dev(1, 'unemployment_rate'):11.4f} "
            f"{dev(1, 'policy_rate'):8.4f} "
            f"{dev(4, 'real_gdp_growth'):8.4f} "
            f"{dev(4, 'core_pce_inflation'):8.4f} "
            f"{dev(4, 'unemployment_rate'):11.4f} "
            f"{dev(4, 'policy_rate'):8.4f} "
            f"{result.scenario_id[:12]}"
        )

    print()
    print("Smoke is read-only. No candidate was selected or ranked.")
    print(
        "Scenario paths are deterministic hard constraints around the "
        "unconditional baseline."
    )
    print("No scenario probability or Bayesian conditional density was computed.")
    print("Scenario deviations are not causal effects.")
    print("No estimation/evaluation start was selected.")
    print("Production authority: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
