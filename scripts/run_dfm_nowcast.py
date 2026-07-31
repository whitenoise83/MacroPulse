from macropulse.services.nowcast_service import run_model_suite_nowcast


def _ascii(value: object) -> str:
    return str(value).replace("–", "-").replace("—", "-")


def main() -> None:
    result = run_model_suite_nowcast()
    print()
    print(f"Run ID: {result['run_id']}")
    print(f"Target period: {result['target_period']}")
    print(f"Data as of: {result['data_as_of']}")
    print(f"Forecast stage: {result.get('forecast_stage', 'not available')}")
    identity = result.get("model_identity", {})
    if identity:
        print(
            f"Model version: {identity.get('model_id')} "
            f"v{identity.get('model_version')} ({identity.get('lifecycle_status')})"
        )
        print(f"Information-set hash: {result.get('information_set_hash')}")
    print()
    forecasts = result["forecasts"][["model_name", "point_forecast", "lower_80", "upper_80"]].copy()
    forecasts["model_name"] = forecasts["model_name"].map(_ascii)
    print(forecasts.to_string(index=False))

    selection = result["metrics"].get("production_selection", {})
    print()
    print("Stable Stage Policy - production")
    for key in [
        "method",
        "forecast_stage",
        "declared_component",
        "selected_component",
        "fallback_used",
        "history_source",
    ]:
        if key in selection:
            print(f"  {key}: {_ascii(selection[key])}")

    shadow = result["metrics"].get("robust_shadow_selection", {})
    print()
    print("Robust Stage-Adaptive Policy - shadow challenger")
    for key in [
        "method",
        "selected_component",
        "incumbent_component",
        "challenger_component",
        "common_history",
        "switched",
        "switch_reason",
        "history_source",
        "max_prior_forecast_date",
    ]:
        if key in shadow:
            print(f"  {key}: {_ascii(shadow[key])}")

    print()
    print("Effective production weights")
    for name, weight in result["metrics"].get("production_weights", {}).items():
        print(f"  {_ascii(name)}: {weight:.1%}")
    rolling = result["metrics"].get("rolling_candidate_weights", {})
    if rolling:
        print("Rolling-ensemble candidate weights")
        for name, weight in rolling.items():
            print(f"  {_ascii(name)}: {weight:.1%}")

    diagnostics = result["metrics"]["dynamic_factor"]
    print()
    print("Dynamic Factor diagnostics")
    for key in [
        "status",
        "converged",
        "iterations",
        "convergence_criterion",
        "log_likelihood",
    ]:
        if key in diagnostics:
            print(f"  {key}: {diagnostics[key]}")

    freshness = result["metrics"].get("data_freshness", {})
    if freshness:
        stale = [name for name, item in freshness.items() if item.get("stale")]
        print()
        print("Data freshness")
        print(f"  stale series: {', '.join(stale) if stale else 'none'}")

    news = result.get("news_decomposition", {})
    print()
    print("News decomposition")
    print(f"  status: {news.get('status', 'not available')}")
    if news.get("status") == "success":
        print(f"  previous production forecast: {news.get('previous_forecast'):.3f}")
        print(f"  current production forecast: {news.get('current_forecast'):.3f}")
        print(f"  total change: {news.get('total_change'):+.3f} pp")
    elif news.get("error"):
        print(f"  error: {news['error']}")


if __name__ == "__main__":
    main()
