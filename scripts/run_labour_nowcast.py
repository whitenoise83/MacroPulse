from __future__ import annotations

from macropulse.labour.service import run_labour_nowcast_suite


def main() -> None:
    result = run_labour_nowcast_suite()
    identity = result["identity"]
    print()
    print("Model 1C labour nowcast complete")
    print(f"Run ID: {result['run_id']}")
    print(
        f"Model: {identity['model_id']} v{identity['model_version']} "
        f"({identity['lifecycle_status']})"
    )
    print(f"Data as of: {result['data_as_of']}")
    print("Research status: development - not vintage validated or production approved")
    print()
    display = result["forecasts"].copy()
    print(
        display[
            [
                "target_name",
                "target_period",
                "target_unit",
                "model_name",
                "point_forecast",
                "lower_80",
                "upper_80",
            ]
        ].to_string(index=False, float_format=lambda value: f"{value:.3f}")
    )


if __name__ == "__main__":
    main()
