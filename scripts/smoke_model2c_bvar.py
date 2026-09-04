from __future__ import annotations

from macropulse.bvar.data import REQUIRED_SERIES, build_complete_quarter_panel
from macropulse.bvar.model import candidate_grid, fit_bvar, point_forecast
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
        print("Model 2C baseline BVAR smoke: COVERAGE_NOT_READY")
        return 2

    snapshot = repo.historical_snapshot(
        as_of_date=cutoff,
        series_ids=list(REQUIRED_SERIES),
    )
    panel = build_complete_quarter_panel(snapshot, cutoff)

    print("Model 2C baseline BVAR read-only smoke")
    print("As-of: " + str(cutoff))
    print(
        "Panel: "
        + str(panel.index[0])
        + " -> "
        + str(panel.index[-1])
        + " n="
        + str(len(panel))
    )
    print("Candidates: 6; selection/ranking: prohibited in 2C")
    print()
    print("p lambda effective_n spectral_radius h1_GDP h1_PCE h1_UNRATE h1_FEDFUNDS")
    print("-" * 88)

    for candidate in candidate_grid():
        posterior = fit_bvar(panel, candidate)
        forecast = point_forecast(panel, posterior)
        h1 = forecast.loc[forecast["horizon"] == 1].iloc[0]
        print(
            f"{candidate.lags:1d} "
            f"{candidate.shrinkage:6.3f} "
            f"{posterior.effective_observations:11d} "
            f"{posterior.companion_spectral_radius:15.6f} "
            f"{h1['real_gdp_growth']:7.3f} "
            f"{h1['core_pce_inflation']:7.3f} "
            f"{h1['unemployment_rate']:9.3f} "
            f"{h1['policy_rate']:11.3f}"
        )

    print()
    print("Smoke is read-only. No candidate was selected or ranked.")
    print("No density forecast or interval was produced.")
    print("No estimation/evaluation start was selected.")
    print("Production authority: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
