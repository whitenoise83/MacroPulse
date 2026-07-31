from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

from macropulse.settings import settings


@dataclass(frozen=True)
class LabourSeriesDefinition:
    series_id: str
    name: str
    frequency: str
    role: str
    transform: str
    unit: str
    display_decimals: int
    source: str
    start_date: str
    monthly_aggregation: str = "last"


def load_labour_registry() -> dict[str, Any]:
    with settings.labour_registry_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict) or "targets" not in config or "features" not in config:
        raise ValueError(
            "config/labour_series_registry.yml must contain targets and features mappings."
        )
    return config


def get_labour_series_definitions() -> list[LabourSeriesDefinition]:
    registry = load_labour_registry()
    definitions: list[LabourSeriesDefinition] = []
    for role_key, role in [("targets", "target"), ("features", "feature")]:
        for series_id, values in registry[role_key].items():
            definitions.append(
                LabourSeriesDefinition(
                    series_id=str(series_id),
                    name=str(values["name"]),
                    frequency=str(values["frequency"]),
                    role=role,
                    transform=str(values["transform"]),
                    unit=str(values.get("unit", "index units")),
                    display_decimals=int(values.get("display_decimals", 2)),
                    source=str(values.get("source", "FRED")),
                    start_date=str(values.get("start_date", "1985-01-01")),
                    monthly_aggregation=str(values.get("monthly_aggregation", "last")),
                )
            )
    return definitions


def target_definitions() -> list[LabourSeriesDefinition]:
    return [item for item in get_labour_series_definitions() if item.role == "target"]


def feature_definitions() -> list[LabourSeriesDefinition]:
    return [item for item in get_labour_series_definitions() if item.role == "feature"]


def get_labour_model_config() -> dict[str, Any]:
    return dict(load_labour_registry().get("model", {}))
