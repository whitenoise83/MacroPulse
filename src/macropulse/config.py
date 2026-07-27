from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

from macropulse.settings import settings


@dataclass(frozen=True)
class SeriesDefinition:
    series_id: str
    name: str
    frequency: str
    role: str
    transform: str
    source: str
    start_date: str


def load_registry() -> dict[str, Any]:
    with settings.registry_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    if not isinstance(config, dict) or "series" not in config:
        raise ValueError("config/series_registry.yml must contain a 'series' mapping.")
    return config


def get_series_definitions() -> list[SeriesDefinition]:
    registry = load_registry()
    definitions: list[SeriesDefinition] = []

    for series_id, values in registry["series"].items():
        definitions.append(
            SeriesDefinition(
                series_id=series_id,
                name=values["name"],
                frequency=values["frequency"],
                role=values["role"],
                transform=values["transform"],
                source=values.get("source", "FRED"),
                start_date=str(values.get("start_date", "1985-01-01")),
            )
        )
    return definitions
