from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


def parse_metrics_json(value: str | Mapping[str, Any] | None) -> dict[str, Any]:
    """Parse a stored metrics payload without breaking the dashboard."""
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def humanise(value: Any) -> str:
    if value is None:
        return "Not available"
    text = str(value).strip()
    if not text:
        return "Not available"
    return text.replace("_", " ").replace("-", " ").title()


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def format_number(value: Any, decimals: int = 2, suffix: str = "") -> str:
    number = _as_float(value)
    if number is None:
        return "Not available"
    return f"{number:.{decimals}f}{suffix}"


def format_percentage(value: Any, decimals: int = 1) -> str:
    number = _as_float(value)
    if number is None:
        return "Not available"
    return f"{number:.{decimals}%}"


def overview_rows(metrics: Mapping[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def add(label: str, value: Any) -> None:
        if value is not None:
            rows.append({"Metric": label, "Value": str(value)})

    add("Production policy", metrics.get("preferred_model"))
    add("Selected component model", metrics.get("selected_component_model"))
    add("Forecast stage", humanise(metrics.get("forecast_stage")))
    add("Information cutoff", metrics.get("information_cutoff"))

    training = metrics.get("training_observations")
    if training is not None:
        add("Training observations", int(training))

    features = metrics.get("feature_count")
    if features is not None:
        add("Indicators used", int(features))

    imputed = metrics.get("imputed_features")
    if imputed is not None:
        add("Imputed indicators", ", ".join(map(str, imputed)) if imputed else "None")

    if metrics.get("bridge_rmse") is not None:
        add("Bridge Ridge RMSE", format_number(metrics.get("bridge_rmse"), 2, " pp"))
    if metrics.get("ar1_rmse") is not None:
        add("AR(1) benchmark RMSE", format_number(metrics.get("ar1_rmse"), 2, " pp"))
    if metrics.get("preferred_sigma") is not None:
        add(
            "Production forecast error standard deviation",
            format_number(metrics.get("preferred_sigma"), 2, " pp"),
        )
    if metrics.get("interval") is not None:
        add("Target forecast interval", format_percentage(metrics.get("interval"), 0))

    history_source = metrics.get("performance_history_source")
    if history_source:
        add("Performance history source", humanise(history_source))

    return rows


def weight_rows(metrics: Mapping[str, Any]) -> list[dict[str, Any]]:
    weights = metrics.get("production_weights")
    if not isinstance(weights, Mapping):
        return []
    rows = []
    for model, value in weights.items():
        number = _as_float(value)
        if number is None:
            continue
        rows.append(
            {
                "Model": str(model),
                "Weight": number,
                "Weight display": f"{number:.1%}",
            }
        )
    return rows


def weight_diagnostic_rows(metrics: Mapping[str, Any]) -> list[dict[str, str]]:
    diagnostics = metrics.get("weight_diagnostics")
    if not isinstance(diagnostics, Mapping):
        return []

    labels = {
        "weight_method": "Weighting method",
        "window": "Rolling window",
        "min_history": "Minimum history required",
        "common_history": "Common quarters used",
        "history_source": "History source",
    }
    rows: list[dict[str, str]] = []
    for key, label in labels.items():
        if key not in diagnostics:
            continue
        value = diagnostics[key]
        if key in {"window", "min_history", "common_history"}:
            value = f"{int(value)} quarters"
        else:
            value = humanise(value)
        rows.append({"Metric": label, "Value": str(value)})
    return rows


def selection_rows(metrics: Mapping[str, Any]) -> list[dict[str, str]]:
    selection = metrics.get("production_selection")
    if not isinstance(selection, Mapping):
        return []

    rows: list[dict[str, str]] = []
    selected = selection.get("selected_component", selection.get("selected_model"))
    if selected not in (None, ""):
        rows.append({"Metric": "Selected component model", "Value": str(selected)})

    labels = {
        "method": "Selection method",
        "history_source": "History source",
        "common_history": "Common completed quarters",
        "max_prior_forecast_date": "Latest selection evidence date",
        # Backward-compatible v0.5 fields:
        "sample": "Evaluation sample",
        "observations": "Completed quarters used",
    }
    for key, label in labels.items():
        if key not in selection or selection[key] in (None, ""):
            continue
        value = selection[key]
        if key in {"method", "history_source", "sample"}:
            value = humanise(value)
        rows.append({"Metric": label, "Value": str(value)})
    return rows



def shadow_selection_rows(metrics: Mapping[str, Any]) -> list[dict[str, str]]:
    selection = metrics.get("robust_shadow_selection")
    if not isinstance(selection, Mapping):
        return []
    labels = {
        "selected_component": "Shadow selected component",
        "incumbent_component": "Incumbent component",
        "challenger_component": "Leading challenger",
        "method": "Selection method",
        "common_history": "Common completed quarters",
        "switched": "Switched",
        "switch_reason": "Switch decision",
        "history_source": "History source",
        "max_prior_forecast_date": "Latest evidence date",
    }
    rows: list[dict[str, str]] = []
    for key, label in labels.items():
        if key not in selection or selection[key] in (None, ""):
            continue
        value = selection[key]
        if isinstance(value, bool):
            value = "Yes" if value else "No"
        elif key in {"method", "switch_reason", "history_source"}:
            value = humanise(value)
        rows.append({"Metric": label, "Value": str(value)})
    return rows

def dfm_rows(metrics: Mapping[str, Any]) -> list[dict[str, str]]:
    diagnostics = metrics.get("dynamic_factor")
    if not isinstance(diagnostics, Mapping):
        return []

    labels = {
        "status": "Status",
        "converged": "EM converged",
        "iterations": "EM iterations",
        "convergence_criterion": "Convergence criterion",
        "log_likelihood": "Log likelihood",
        "factor_count": "Factors",
        "factor_order": "Factor order",
        "error": "Error",
    }
    rows: list[dict[str, str]] = []
    for key, label in labels.items():
        if key not in diagnostics or diagnostics[key] is None:
            continue
        value = diagnostics[key]
        if isinstance(value, bool):
            value = "Yes" if value else "No"
        elif key in {"convergence_criterion", "log_likelihood"}:
            value = format_number(value, 6 if key == "convergence_criterion" else 2)
        elif key == "status":
            value = humanise(value)
        rows.append({"Metric": label, "Value": str(value)})
    return rows


def identity_rows(metrics: Mapping[str, Any]) -> list[dict[str, str]]:
    identity = metrics.get("model_identity")
    if not isinstance(identity, Mapping):
        return []
    labels = {
        "model_id": "Model ID",
        "model_version": "Model version",
        "config_hash": "Configuration hash",
        "code_hash": "Code hash",
        "git_commit": "Git commit",
    }
    rows = []
    for key, label in labels.items():
        value = identity.get(key)
        if value in (None, ""):
            continue
        text = str(value)
        if key in {"config_hash", "code_hash", "git_commit"} and len(text) > 16:
            text = f"{text[:12]}…"
        rows.append({"Metric": label, "Value": text})
    return rows


def interval_rows(metrics: Mapping[str, Any]) -> list[dict[str, str]]:
    calibration = metrics.get("interval_calibration")
    if not isinstance(calibration, Mapping):
        return []

    rows: list[dict[str, str]] = []
    for model, details in calibration.items():
        if not isinstance(details, Mapping):
            continue
        method = humanise(details.get("method"))
        history = details.get("history_observations", details.get("observations"))
        scale = details.get("scale_factor", details.get("calibration_factor"))
        coverage = details.get("coverage")
        rows.append(
            {
                "Model": str(model),
                "Method": method,
                "History": "Not available" if history is None else str(int(history)),
                "Scale factor": "Not available" if scale is None else format_number(scale, 3),
                "Target coverage": "Not available" if coverage is None else format_percentage(coverage, 0),
            }
        )
    return rows
