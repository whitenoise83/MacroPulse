from __future__ import annotations

from macropulse.bvar.data import REQUIRED_SERIES
from macropulse.bvar.production import run_model2_forecast
from macropulse.data.repository import MacroRepository


SMOKE_SIMULATIONS = 1000
SMOKE_SEED = 20260904


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
        print("Model 2H release-candidate smoke: COVERAGE_NOT_READY")
        return 2

    snapshot = repo.historical_snapshot(
        as_of_date=cutoff,
        series_ids=list(REQUIRED_SERIES),
    )
    result = run_model2_forecast(
        snapshot,
        cutoff,
        simulations=SMOKE_SIMULATIONS,
        seed=SMOKE_SEED,
    )

    print("Model 2H release-candidate read-only smoke")
    print("As-of: " + str(cutoff))
    print(
        "Panel: "
        + result.estimation_first_quarter
        + " -> "
        + result.estimation_last_quarter
        + " n="
        + str(result.estimation_observations)
    )
    print(
        "Frozen candidate: p="
        + str(result.lags)
        + " lambda="
        + str(result.shrinkage)
        + " id="
        + result.candidate_id
    )
    print(
        "Posterior-mean companion spectral radius: "
        + f"{result.companion_spectral_radius:.6f}"
    )
    print("Simulations: " + str(result.simulations))
    print("Seed: " + str(result.seed))
    print("Predictive draw hash: " + result.predictive_draw_hash[:16])
    print("Output fingerprint: " + result.output_fingerprint[:16])
    print()
    print(
        result.point_forecast[
            [
                "horizon",
                "target_quarter",
                "real_gdp_growth",
                "core_pce_inflation",
                "unemployment_rate",
                "policy_rate",
            ]
        ].to_string(index=False)
    )
    print()
    h1 = result.predictive_summary[
        result.predictive_summary["horizon"] == 1
    ][["variable", "median", "lower_80", "upper_80"]]
    print("H1 posterior predictive summary")
    print(h1.to_string(index=False))
    print()
    print("Scenario conditioning: not automatic")
    print("Candidate reselection/retuning: prohibited")
    print("Database writes: none")
    print("Production authority before release tag: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
