from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from macropulse.governance.versioning import git_commit
from macropulse.settings import settings


@dataclass(frozen=True)
class LabourModelIdentity:
    model_id: str
    display_name: str
    model_version: str
    lifecycle_status: str
    config_hash: str
    code_hash: str
    git_commit: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def labour_configuration_hash() -> str:
    payload = {}
    for path in [settings.labour_registry_path, settings.labour_governance_path]:
        payload[path.name] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return hashlib.sha256(_canonical(payload)).hexdigest()


def labour_code_hash(project_root: Path | None = None) -> str:
    root = project_root or settings.project_root
    paths = [
        root / "src" / "macropulse" / "labour",
        root / "scripts" / "download_labour_data.py",
        root / "scripts" / "run_labour_nowcast.py",
        root / "scripts" / "run_labour_backtest.py",
        root / "scripts" / "download_labour_initial_targets.py",
        root / "scripts" / "run_labour_vintage_backtest.py",
        root / "scripts" / "run_labour_validation.py",
        root / "ui" / "labour_nowcast.py",
        root / "ui" / "labour_backtesting.py",
        settings.labour_registry_path,
        settings.labour_governance_path,
    ]
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(item for item in path.rglob("*.py") if item.is_file()))
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda item: item.as_posix()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def current_labour_model_identity() -> LabourModelIdentity:
    config = yaml.safe_load(settings.labour_governance_path.read_text(encoding="utf-8"))["model"]
    return LabourModelIdentity(
        model_id=str(config["model_id"]),
        display_name=str(config["display_name"]),
        model_version=str(config["version"]),
        lifecycle_status=str(config.get("lifecycle_status", "development")),
        config_hash=labour_configuration_hash(),
        code_hash=labour_code_hash(),
        git_commit=git_commit(),
    )
