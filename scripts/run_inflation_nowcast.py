from __future__ import annotations

from macropulse.inflation.service import run_inflation_nowcast_suite


def main() -> None:
    result = run_inflation_nowcast_suite()
    print()
    print("Model 1B inflation nowcast complete")
    print(f"Run ID: {result['run_id']}")
    identity = result["identity"]
    print(
        f"Model: {identity['model_id']} v{identity['model_version']} "
        f"({identity['lifecycle_status']})"
    )
    print(f"Data as of: {result['data_as_of']}")
    print("Research status: development - vintage backtesting available; not production approved")
    print()
    display = result["forecasts"].copy()
    print(
        display[
            [
                "target_name",
                "target_period",
                "model_name",
                "point_forecast",
                "lower_80",
                "upper_80",
            ]
        ].to_string(index=False, float_format=lambda value: f"{value:.3f}")
    )
    print()
    print("Latest observed inflation metrics")
    for series_id, metrics in result["metrics"].items():
        print(
            f"  {metrics['target_name']} ({series_id}): "
            f"1m annualised {metrics['latest_monthly_annualised']:.2f}%, "
            f"3m annualised {metrics['latest_three_month_annualised']:.2f}%, "
            f"year-over-year {metrics['latest_year_over_year']:.2f}%"
        )


if __name__ == "__main__":
    main()
