from __future__ import annotations

from macropulse.bvar.data import REQUIRED_SERIES, build_complete_quarter_panel
from macropulse.bvar.model import candidate_grid, fit_bvar
from macropulse.bvar.probabilistic import DEFAULT_SEED, simulate_posterior_predictive
from macropulse.data.repository import MacroRepository


def latest_common_cutoff(repo: MacroRepository):
    placeholders = ", ".join(["?"] * len(REQUIRED_SERIES))
    query = (
        "SELECT MAX(as_of_date) FROM ("
        "SELECT as_of_date FROM snapshot_downloads "
        "WHERE status = 'success' AND series_id IN (" + placeholders + ") "
        "GROUP BY as_of_date HAVING COUNT(DISTINCT series_id) = ?)"
    )
    params = [*REQUIRED_SERIES, len(REQUIRED_SERIES)]
    with repo.connect(read_only=True) as connection:
        return connection.execute(query, params).fetchone()[0]


def main() -> int:
    repo = MacroRepository()
    cutoff = latest_common_cutoff(repo)
    if cutoff is None:
        print("Model 2D probabilistic smoke: COVERAGE_NOT_READY")
        return 2
    snapshot = repo.historical_snapshot(as_of_date=cutoff, series_ids=list(REQUIRED_SERIES))
    panel = build_complete_quarter_panel(snapshot, cutoff)
    print("Model 2D posterior-predictive read-only smoke")
    print("As-of: " + str(cutoff))
    print("Panel: " + str(panel.index[0]) + " -> " + str(panel.index[-1]) + " n=" + str(len(panel)))
    print("Candidates: 6; selection/ranking: prohibited in 2D")
    print("Smoke simulations per candidate: 1000")
    print("Seed: " + str(DEFAULT_SEED))
    print()
    print("p lambda h1_gdp_med h1_gdp_80_lo h1_gdp_80_hi h1_pce_med h1_unrate_med h1_rate_med draw_hash")
    print("-" * 118)
    for candidate in candidate_grid():
        posterior = fit_bvar(panel, candidate)
        simulation = simulate_posterior_predictive(panel, posterior, simulations=1000, seed=DEFAULT_SEED)
        h1 = simulation.summary[simulation.summary["horizon"] == 1].set_index("variable")
        print(
            f"{candidate.lags:1d} {candidate.shrinkage:6.3f} "
            f"{h1.loc['real_gdp_growth','median']:10.3f} "
            f"{h1.loc['real_gdp_growth','lower_80']:12.3f} "
            f"{h1.loc['real_gdp_growth','upper_80']:12.3f} "
            f"{h1.loc['core_pce_inflation','median']:10.3f} "
            f"{h1.loc['unemployment_rate','median']:13.3f} "
            f"{h1.loc['policy_rate','median']:11.3f} "
            f"{simulation.draw_hash[:12]}"
        )
    print()
    print("Smoke is read-only. No candidate was selected or ranked.")
    print("Intervals are posterior predictive, not calibration claims.")
    print("No scenario conditioning was applied.")
    print("No estimation/evaluation start was selected.")
    print("Production authority: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
