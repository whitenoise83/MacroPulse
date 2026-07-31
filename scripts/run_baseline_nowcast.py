from macropulse.services.nowcast_service import run_model_suite_nowcast


def main() -> None:
    result = run_model_suite_nowcast()
    print()
    print(f"Run ID: {result['run_id']}")
    print(f"Target period: {result['target_period']}")
    print(f"Data as of: {result['data_as_of']}")
    print()
    print(
        result["forecasts"][
            ["model_name", "point_forecast", "lower_80", "upper_80"]
        ].to_string(index=False)
    )
    print()
    print(f"Imputed bridge features: {result['metrics']['imputed_features']}")
    if result.get("dfm_error"):
        print(f"DFM fallback reason: {result['dfm_error']}")


if __name__ == "__main__":
    main()
