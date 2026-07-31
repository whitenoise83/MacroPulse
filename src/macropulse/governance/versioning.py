from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from macropulse.settings import settings


@dataclass(frozen=True)
class ModelIdentity:
    model_id: str
    display_name: str
    model_version: str
    lifecycle_status: str
    config_hash: str
    code_hash: str
    git_commit: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_governance_config() -> dict[str, Any]:
    with settings.governance_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict) or "model" not in config:
        raise ValueError("config/model_governance.yml must contain a model mapping.")
    return config


def configuration_hash() -> str:
    payload: dict[str, Any] = {}
    for path in [settings.registry_path, settings.governance_path]:
        with path.open("r", encoding="utf-8") as handle:
            payload[path.name] = yaml.safe_load(handle)
    return sha256_text(_canonical_json(payload))


def _iter_code_files(project_root: Path) -> list[Path]:
    candidates: list[Path] = []
    for relative in ["src", "scripts", "ui", "app.py", "pyproject.toml"]:
        path = project_root / relative
        if path.is_file():
            candidates.append(path)
        elif path.is_dir():
            candidates.extend(
                item
                for item in path.rglob("*")
                if item.is_file()
                and item.suffix.lower() in {".py", ".toml", ".yml", ".yaml"}
                and "__pycache__" not in item.parts
            )
    return sorted(candidates, key=lambda item: item.relative_to(project_root).as_posix())


def code_hash(project_root: Path | None = None) -> str:
    root = project_root or settings.project_root
    digest = hashlib.sha256()
    for path in _iter_code_files(root):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def git_commit(project_root: Path | None = None) -> str:
    explicit = os.getenv("MACROPULSE_GIT_COMMIT", "").strip()
    if explicit:
        return explicit
    root = project_root or settings.project_root
    try:
        process = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return process.stdout.strip()
    except Exception:
        return "unavailable"


def current_model_identity(project_root: Path | None = None) -> ModelIdentity:
    config = load_governance_config()["model"]
    computed_config_hash = configuration_hash()
    computed_code_hash = code_hash(project_root)
    if str(config.get("lifecycle_status")) == "production":
        computed_config_hash = str(config.get("approved_config_hash", computed_config_hash))
        computed_code_hash = str(config.get("approved_code_hash", computed_code_hash))
    return ModelIdentity(
        model_id=str(config["model_id"]),
        display_name=str(config["display_name"]),
        model_version=str(config["version"]),
        lifecycle_status=str(config.get("lifecycle_status", "development")),
        config_hash=computed_config_hash,
        code_hash=computed_code_hash,
        git_commit=git_commit(project_root),
    )


def information_set_hash(observations: pd.DataFrame) -> str:
    required = {"series_id", "observation_date", "value"}
    missing = required.difference(observations.columns)
    if missing:
        raise ValueError(f"Information set is missing columns: {sorted(missing)}")
    frame = observations.copy()
    frame["observation_date"] = pd.to_datetime(frame["observation_date"]).dt.strftime(
        "%Y-%m-%d"
    )
    for column in ["realtime_start", "realtime_end"]:
        if column in frame.columns:
            frame[column] = frame[column].map(
                lambda value: (
                    value.strftime("%Y-%m-%d")
                    if hasattr(value, "strftime")
                    else None
                )
            )
    columns = [
        column
        for column in [
            "series_id",
            "observation_date",
            "value",
            "realtime_start",
            "realtime_end",
        ]
        if column in frame.columns
    ]
    frame = frame[columns].sort_values(columns[:-1] if len(columns) > 1 else columns)
    records = frame.where(pd.notna(frame), None).to_dict(orient="records")
    return sha256_text(_canonical_json(records))
