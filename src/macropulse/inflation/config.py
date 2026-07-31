from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

from macropulse.settings import settings


@dataclass(frozen=True)
class InflationSeriesDefinition:
    series_id: str
    name: str
    frequency: str
    role: str
    transform: str
    source: str
    start_date: str
    monthly_aggregation: str = "last"


def load_inflation_registry() -> dict[str, Any]:
    with settings.inflation_registry_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict) or "targets" not in config or "features" not in config:
        raise ValueError(
            "config/inflation_series_registry.yml must contain targets and features mappings."
        )
    return config


def get_inflation_series_definitions() -> list[InflationSeriesDefinition]:
    registry = load_inflation_registry()
    definitions: list[InflationSeriesDefinition] = []
    for role_key, role in [("targets", "target"), ("features", "feature")]:
        for series_id, values in registry[role_key].items():
            definitions.append(
                InflationSeriesDefinition(
                    series_id=series_id,
                    name=str(values["name"]),
                    frequency=str(values["frequency"]),
                    role=role,
                    transform=str(values["transform"]),
                    source=str(values.get("source", "FRED")),
                    start_date=str(values.get("start_date", "1985-01-01")),
                    monthly_aggregation=str(values.get("monthly_aggregation", "last")),
                )
            )
    return definitions


def get_inflation_model_config() -> dict[str, Any]:
    return dict(load_inflation_registry().get("model", {}))


def target_definitions() -> list[InflationSeriesDefinition]:
    return [item for item in get_inflation_series_definitions() if item.role == "target"]


def feature_definitions() -> list[InflationSeriesDefinition]:
    return [item for item in get_inflation_series_definitions() if item.role == "feature"]
