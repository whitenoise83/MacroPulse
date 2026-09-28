from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def tracked_files() -> set[str]:
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return {x.strip().replace("\\", "/") for x in completed.stdout.splitlines() if x.strip()}


def test_package_version_is_consistent() -> None:
    import tomllib
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project_version = pyproject["project"]["version"]
    init_text = (ROOT / "src/macropulse/__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    assert match
    assert match.group(1) == project_version == "1.13.0"


def test_pyproject_declares_runtime_dependencies() -> None:
    import tomllib
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    deps = "\n".join(pyproject["project"]["dependencies"]).lower()
    for name in (
        "duckdb", "numpy", "pandas", "pyarrow", "python-dotenv", "pyyaml",
        "requests", "scikit-learn", "statsmodels", "streamlit",
        "matplotlib", "scipy", "tabulate",
    ):
        assert name in deps


def test_proprietary_license_and_commercial_notice_exist() -> None:
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    commercial = (ROOT / "COMMERCIAL_LICENSING.md").read_text(encoding="utf-8")
    assert "PROPRIETARY SOFTWARE" in license_text
    assert "NO LICENSE OR PERMISSION IS GRANTED" in license_text
    assert "not" in commercial.lower() and "open-source" in commercial.lower()


def test_readme_mentions_current_model2_and_model3_releases() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "model2-bvar-v1.0.2" in text
    assert "model3-potential-output-v1.0.0" in text
    assert "Bayesian VAR" in text
    assert "Potential Output & Macroeconomic Slack" in text
    assert "proprietary" in text.lower()


def test_generated_and_accidental_files_are_not_tracked() -> None:
    files = tracked_files()
    assert "tatus" not in files
    assert not any(".egg-info/" in p for p in files)


def test_runtime_artifacts_are_not_tracked() -> None:
    files = tracked_files()
    forbidden = [
        p for p in files
        if p.endswith(".duckdb")
        or p.endswith(".wal")
        or p.startswith("data/backups/")
        or p.startswith("reports/decision_intelligence_snapshots/")
    ]
    assert forbidden == []


def test_main_guard_covers_hardening_main_and_frozen_release_verification() -> None:
    text = (ROOT / ".github/workflows/platform-main-guard.yml").read_text(encoding="utf-8")
    assert "repository-hardening-development" in text
    assert re.search(r"(?m)^\s+- main\s*$", text)
    assert "Verify immutable Model 2 release in frozen checkout" in text
    assert "Verify immutable Model 3 release in frozen checkout" in text
    assert "core.autocrlf=false" in text


def test_main_guard_excludes_only_known_checkout_context_historical_tests() -> None:
    text = (ROOT / ".github/workflows/platform-main-guard.yml").read_text(encoding="utf-8")
    required = (
        "tests/test_model1d_v038_manifest_integrity.py::"
        "test_manifest_hashes_match_using_cross_platform_canonicalisation",
        "tests/test_model1d_v038_release_metadata.py::"
        "test_v038_release_documentation_is_present_and_consistent",
        "tests/test_model2_release_metadata.py::"
        "test_v102_release_verifier_is_tag_optional_before_creation",
        "tests/test_model3_release_metadata.py::"
        "test_release_verifier_is_tag_optional_before_creation",
    )
    for node in required:
        assert node in text


def test_line_ending_policy_exists() -> None:
    text = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "* text=auto eol=lf" in text
    assert "*.cmd text eol=crlf" in text
