from pathlib import Path

import duckdb


DATABASE_PATH = Path("data/macropulse.duckdb")


def main() -> None:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH.resolve()}"
        )

    con = duckdb.connect(str(DATABASE_PATH), read_only=True)

    try:
        print("\nNEWS RECONCILIATION DIAGNOSTIC")
        print("=" * 80)

        print("\n1. Successful news runs with the largest residuals\n")

        problem_runs = con.execute(
            """
            SELECT
                decomposition_id,
                created_at,
                target_period,
                current_run_id,
                previous_run_id,
                total_change,
                residual_interaction,
                ABS(residual_interaction) AS absolute_residual,
                details_json
            FROM nowcast_news_runs
            WHERE status = 'success'
            ORDER BY ABS(residual_interaction) DESC
            LIMIT 10
            """
        ).df()

        if problem_runs.empty:
            print("No successful news-decomposition runs were found.")
        else:
            print(problem_runs.to_string(index=False))

        print("\n" + "=" * 80)
        print("\n2. Arithmetic reconciliation check\n")

        arithmetic_check = con.execute(
            """
            SELECT
                n.decomposition_id,
                n.created_at,
                n.target_period,
                n.total_change,
                COALESCE(SUM(c.impact), 0) AS displayed_contribution_sum,
                n.total_change
                    - COALESCE(SUM(c.impact), 0) AS arithmetic_gap,
                n.residual_interaction
            FROM nowcast_news_runs AS n
            LEFT JOIN nowcast_news_contributions AS c
                ON n.decomposition_id = c.decomposition_id
            WHERE n.status = 'success'
            GROUP BY
                n.decomposition_id,
                n.created_at,
                n.target_period,
                n.total_change,
                n.residual_interaction
            ORDER BY ABS(n.residual_interaction) DESC
            LIMIT 10
            """
        ).df()

        if arithmetic_check.empty:
            print("No reconciliation records were found.")
        else:
            print(arithmetic_check.to_string(index=False))

        print("\n" + "=" * 80)
        print("\n3. Contributions for the run with the largest residual\n")

        if not problem_runs.empty:
            largest_id = problem_runs.iloc[0]["decomposition_id"]

            contributions = con.execute(
                """
                SELECT *
                FROM nowcast_news_contributions
                WHERE decomposition_id = ?
                ORDER BY ABS(impact) DESC
                """,
                [largest_id],
            ).df()

            print(f"Decomposition ID: {largest_id}\n")

            if contributions.empty:
                print("No contribution rows were found for this run.")
            else:
                print(contributions.to_string(index=False))

        print("\nDiagnostic complete.")

    finally:
        con.close()


if __name__ == "__main__":
    main()