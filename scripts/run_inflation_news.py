from __future__ import annotations

import argparse

from macropulse.data.repository import MacroRepository
from macropulse.inflation.news import build_inflation_news_decomposition


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build or rebuild Model 1B inflation news decomposition."
    )
    parser.add_argument("--run-id", help="Governed live run ID. Defaults to the latest run.")
    args = parser.parse_args()
    repository = MacroRepository()
    repository.initialise()
    run_id = args.run_id
    if not run_id:
        latest = repository.query_df(
            "SELECT run_id FROM inflation_live_runs ORDER BY run_timestamp DESC LIMIT 1"
        )
        if latest.empty:
            raise RuntimeError("No governed Model 1B live run is available.")
        run_id = str(latest.iloc[0]["run_id"])
    result = build_inflation_news_decomposition(repository, run_id)
    print("Model 1B inflation news decomposition complete")
    print(f"Run ID: {run_id}")
    print(f"Status: {result['status']}")
    print(f"Targets: {result.get('targets', 0)}")
    print(f"Comparable targets: {result.get('comparable_targets', 0)}")
    if "maximum_residual" in result:
        print(f"Maximum residual: {result['maximum_residual']:.3e}")


if __name__ == "__main__":
    main()
