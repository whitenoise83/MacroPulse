from __future__ import annotations

import hashlib
from pathlib import Path


EXACT_PATHS = (
    ".github/workflows/phase2-platform-guard.yml",
    "MACROPULSE_PHASE2_PLAN.md",
    "PHASE2_BOUNDARY.json",
    "PHASE2_PLATFORM_CONTRACT.json",
    "PHASE2_RELEASE.json",
    "README_PHASE2_v1.0.0.md",
    "VALIDATION_PHASE2_v1.0.0.txt",
    "docs/PHASE2_ARCHITECTURE.md",
    "docs/PHASE2B_STATUS_CONTRACT.md",
    "docs/PHASE2C_ORCHESTRATION_CONTRACT.md",
    "docs/PHASE2D_SNAPSHOT_CONTRACT.md",
    "docs/PHASE2E_DASHBOARD_CONTRACT.md",
    "docs/PHASE2_OPERATIONAL_RUNBOOK.md",
    "scripts/report_platform_status.py",
    "scripts/run_platform_operations.py",
    "scripts/export_macro_snapshot.py",
    "scripts/verify_phase2_platform.py",
    "scripts/verify_phase2_release.py",
    "src/macropulse/platform/__init__.py",
    "src/macropulse/platform/status.py",
    "src/macropulse/platform/orchestration.py",
    "src/macropulse/platform/snapshot.py",
    "src/macropulse/platform/dashboard.py",
    "ui/platform_dashboard.py",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def release_scope(root: Path) -> list[Path]:
    paths = [root / relative for relative in EXACT_PATHS]
    paths.extend(sorted((root / "tests").glob("test_phase2_*.py")))
    unique = sorted(
        {path.resolve() for path in paths},
        key=lambda path: path.relative_to(root.resolve()).as_posix(),
    )
    return unique


def write_manifest(root: Path) -> Path:
    missing = [
        path.relative_to(root).as_posix()
        for path in release_scope(root)
        if not path.is_file()
    ]
    if missing:
        raise RuntimeError(
            "Cannot create Phase II release manifest; files missing:\n"
            + "\n".join(missing)
        )

    lines = [
        f"{sha256(path)}  {path.relative_to(root).as_posix()}"
        for path in release_scope(root)
    ]
    manifest = root / "MANIFEST_PHASE2_v1.0.0.txt"
    manifest.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest
