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
class MacroStateIdentity:
    model_id: str
    display_name: str
    model_version: str
    lifecycle_status: str
    config_hash: str
    code_hash: str
    git_commit: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def governance_path(project_root: Path | None = None) -> Path:
    root = project_root or settings.project_root
    return root / "config" / "macro_state_governance.yml"


def load_macro_state_governance(
    project_root: Path | None = None,
) -> dict[str, Any]:
    path = governance_path(project_root)
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or "model" not in config:
        raise ValueError(
            "config/macro_state_governance.yml must contain a model mapping."
        )
    return config


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def macro_state_configuration_hash(
    project_root: Path | None = None,
) -> str:
    config = load_macro_state_governance(project_root)
    return hashlib.sha256(_canonical(config)).hexdigest()


def macro_state_code_hash(
    project_root: Path | None = None,
) -> str:
    root = project_root or settings.project_root
    paths = [
        root / "src" / "macropulse" / "macro_state",
        root / "scripts" / "run_macro_state.py",
        root / "ui" / "macro_state.py",
        root / "config" / "macro_state_governance.yml",
    ]
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(
                sorted(
                    item
                    for item in path.rglob("*.py")
                    if item.is_file() and "__pycache__" not in item.parts
                )
            )
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda item: item.as_posix()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def current_macro_state_identity(
    project_root: Path | None = None,
) -> MacroStateIdentity:
    config = load_macro_state_governance(project_root)["model"]
    return MacroStateIdentity(
        model_id=str(config["model_id"]),
        display_name=str(config["display_name"]),
        model_version=str(config["version"]),
        lifecycle_status=str(
            config.get("lifecycle_status", "development")
        ),
        config_hash=macro_state_configuration_hash(project_root),
        code_hash=macro_state_code_hash(project_root),
        git_commit=git_commit(project_root),
    )
