from __future__ import annotations

import numpy as np

from macropulse.bvar.data import REQUIRED_SERIES, build_complete_quarter_panel
from macropulse.bvar.model import candidate_grid, fit_bvar
from macropulse.bvar.structural import structural_analysis
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
        print("Model 2E IRF/FEVD smoke: COVERAGE_NOT_READY")
        return 2

    snapshot = repo.historical_snapshot(
        as_of_date=cutoff,
        series_ids=list(REQUIRED_SERIES),
    )
    panel = build_complete_quarter_panel(snapshot, cutoff)

    print("Model 2E recursive IRF/FEVD read-only smoke")
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
        "Identification: recursive Cholesky; order="
        "GDP -> core PCE -> unemployment -> policy rate"
    )
    print("Horizons: 1, 4, 8, 12 quarters")
    print("Candidates: 6; selection/ranking: prohibited in 2E")
    print()
    print(
        "p lambda radius policyShock_h1_GDP policyShock_h1_PCE "
        "policyShock_h1_UNRATE policyShock_h1_RATE "
        "FEVD12_GDP_from_GDP FEVD12_RATE_from_RATE max_share_sum_error"
    )
    print("-" * 148)

    for candidate in candidate_grid():
        posterior = fit_bvar(panel, candidate)
        result = structural_analysis(posterior)

        h1 = result.irf[
            (result.irf["horizon"] == 1)
            & (result.irf["shock"] == "policy_rate")
        ].set_index("response")

        fevd12 = result.fevd[
            result.fevd["horizon"] == 12
        ].set_index(["response", "shock"])

        sums = result.fevd.groupby(
            ["horizon", "response"]
        )["share"].sum()
        max_error = float(np.max(np.abs(sums.to_numpy() - 1.0)))

        print(
            f"{candidate.lags:1d} "
            f"{candidate.shrinkage:6.3f} "
            f"{posterior.companion_spectral_radius:6.3f} "
            f"{h1.loc['real_gdp_growth', 'response_value']:18.4f} "
            f"{h1.loc['core_pce_inflation', 'response_value']:18.4f} "
            f"{h1.loc['unemployment_rate', 'response_value']:21.4f} "
            f"{h1.loc['policy_rate', 'response_value']:19.4f} "
            f"{fevd12.loc[('real_gdp_growth', 'real_gdp_growth'), 'share']:19.4f} "
            f"{fevd12.loc[('policy_rate', 'policy_rate'), 'share']:21.4f} "
            f"{max_error:19.2e}"
        )

    print()
    print("Smoke is read-only. No candidate was selected or ranked.")
    print(
        "IRFs/FEVDs are conditional on the recursive identification; "
        "they are not unconditional causal claims."
    )
    print("No scenario conditioning was applied.")
    print("No estimation/evaluation start was selected.")
    print("Production authority: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
