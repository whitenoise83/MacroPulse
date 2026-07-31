from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

DATABASE_PATH = Path("data/macropulse.duckdb")
PRODUCTION_MODEL = "Stable Stage Policy"
STATIC_MODELS = [
    "Bridge Ridge",
    "Dynamic Factor Model",
    "Bridge-DFM Ensemble",
    "Rolling Bridge-DFM Ensemble",
]


def metrics(group: pd.DataFrame) -> dict[str, float | int]:
    errors = pd.to_numeric(group["abs_error"], errors="coerce").dropna()
    squared = pd.to_numeric(group["squared_error"], errors="coerce").dropna()
    return {
        "observations": int(len(errors)),
        "rmse": float(squared.mean() ** 0.5),
        "mae": float(errors.mean()),
        "p90_abs_error": float(errors.quantile(0.90)),
        "max_abs_error": float(errors.max()),
    }


def main() -> None:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH.resolve()}")

    con = duckdb.connect(str(DATABASE_PATH), read_only=True)
    try:
        latest = con.execute(
            """
            SELECT stage_backtest_id, created_at, model_version
            FROM stage_backtest_runs
            WHERE model_version = '0.6.1'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).df()
        if latest.empty:
            latest = con.execute(
                """
                SELECT stage_backtest_id, created_at, model_version
                FROM stage_backtest_runs
                ORDER BY created_at DESC
                LIMIT 1
                """
            ).df()
        if latest.empty:
            raise RuntimeError("No staged backtest was found.")

        backtest_id = str(latest.iloc[0]["stage_backtest_id"])
        print("UPPER-TAIL VALIDATION DIAGNOSTIC")
        print("=" * 100)
        print(f"Stage backtest ID: {backtest_id}")
        print(f"Model version: {latest.iloc[0]['model_version']}")
        print(f"Created at: {latest.iloc[0]['created_at']}")

        results = con.execute(
            """
            SELECT *
            FROM stage_backtest_results
            WHERE stage_backtest_id = ?
            ORDER BY forecast_stage, target_period, model_name
            """,
            [backtest_id],
        ).df()
        if results.empty:
            raise RuntimeError(f"Staged backtest {backtest_id} contains no results.")

        rows: list[dict] = []
        for stage, stage_group in results.groupby("forecast_stage", sort=False):
            model_metrics: dict[str, dict] = {}
            for model_name, model_group in stage_group.groupby("model_name"):
                model_metrics[str(model_name)] = metrics(model_group)

            if PRODUCTION_MODEL not in model_metrics:
                continue
            eligible = {
                name: model_metrics[name]
                for name in STATIC_MODELS
                if name in model_metrics
            }
            if not eligible:
                continue

            best_name = min(eligible, key=lambda name: eligible[name]["p90_abs_error"])
            production = model_metrics[PRODUCTION_MODEL]
            best = eligible[best_name]
            rows.append(
                {
                    "forecast_stage": stage,
                    "production_p90": production["p90_abs_error"],
                    "best_static_p90": best["p90_abs_error"],
                    "p90_ratio": production["p90_abs_error"] / best["p90_abs_error"],
                    "best_p90_model": best_name,
                    "production_rmse": production["rmse"],
                    "best_static_rmse": min(v["rmse"] for v in eligible.values()),
                    "production_mae": production["mae"],
                    "best_static_mae": min(v["mae"] for v in eligible.values()),
                    "production_max": production["max_abs_error"],
                    "best_static_max": min(v["max_abs_error"] for v in eligible.values()),
                }
            )

        comparison = pd.DataFrame(rows).sort_values("p90_ratio", ascending=False)
        print("\n1. P90 comparison by forecast stage\n")
        print(comparison.round(4).to_string(index=False))

        if comparison.empty:
            return

        worst = comparison.iloc[0]
        worst_stage = str(worst["forecast_stage"])
        best_model = str(worst["best_p90_model"])
        print("\n" + "=" * 100)
        print("2. Worst stage")
        print(f"Forecast stage: {worst_stage}")
        print(f"Production model: {PRODUCTION_MODEL}")
        print(f"Best static p90 model: {best_model}")
        print(f"P90 ratio: {float(worst['p90_ratio']):.4f}")

        subset = results.loc[
            (results["forecast_stage"] == worst_stage)
            & (results["model_name"].isin([PRODUCTION_MODEL, best_model])),
            [
                "target_period",
                "forecast_date",
                "model_name",
                "point_forecast",
                "actual",
                "error",
                "abs_error",
            ],
        ].copy()

        pivot = subset.pivot_table(
            index=["target_period", "forecast_date", "actual"],
            columns="model_name",
            values=["point_forecast", "error", "abs_error"],
            aggfunc="first",
        )
        pivot.columns = [f"{metric}__{model}" for metric, model in pivot.columns]
        pivot = pivot.reset_index()
        production_abs = f"abs_error__{PRODUCTION_MODEL}"
        best_abs = f"abs_error__{best_model}"
        pivot["production_minus_best_abs_error"] = pivot[production_abs] - pivot[best_abs]
        pivot = pivot.sort_values(production_abs, ascending=False)

        print("\n3. Ten largest production absolute errors at the worst stage\n")
        display_columns = [
            "target_period",
            "forecast_date",
            "actual",
            f"point_forecast__{PRODUCTION_MODEL}",
            production_abs,
            f"point_forecast__{best_model}",
            best_abs,
            "production_minus_best_abs_error",
        ]
        print(pivot[display_columns].head(10).round(4).to_string(index=False))

        print("\n4. Quarters where production underperformed the best-p90 static model most\n")
        print(
            pivot.sort_values("production_minus_best_abs_error", ascending=False)[display_columns]
            .head(10)
            .round(4)
            .to_string(index=False)
        )

        diagnostics = con.execute(
            """
            SELECT forecast_stage, forecast_date, target_period, details_json
            FROM stage_backtest_diagnostics
            WHERE stage_backtest_id = ?
              AND model_name = ?
              AND forecast_stage = ?
            ORDER BY forecast_date
            """,
            [backtest_id, PRODUCTION_MODEL, worst_stage],
        ).df()
        if not diagnostics.empty:
            print("\n5. Stable-policy diagnostic rows for the worst stage\n")
            print(diagnostics.tail(10).to_string(index=False))

        print("\nDiagnostic complete.")
    finally:
        con.close()


if __name__ == "__main__":
    main()
