from __future__ import annotations

import json
from pathlib import Path

from importlib.util import module_from_spec, spec_from_file_location


ROOT = Path(__file__).parents[1]
CONTRACT = ROOT / "PHASE2_PLATFORM_CONTRACT.json"
VERIFIER = ROOT / "scripts" / "verify_phase2_platform.py"
WORKFLOW = ROOT / ".github" / "workflows" / "phase2-platform-guard.yml"


def load_verifier():
    spec = spec_from_file_location("phase2_verifier", VERIFIER)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_platform_release_contract_identity() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert payload["contract_id"] == "MACROPULSE_PHASE2_PLATFORM"
    assert payload["platform_version"] == "1.0.0"
    assert payload["lifecycle"] == "released"
    assert payload["protected_base_commit"] == "048c1a6"

    suite = payload["model_suite"]
    assert suite["1A"]["version"] == "1.0.0"
    assert suite["1B"]["version"] == "1.0.0"
    assert suite["1C"]["version"] == "1.0.0"
    assert suite["1D"]["version"] == "0.3.8"
    assert suite["1D"]["lifecycle"] == "development"
    assert suite["1D"]["promotion_authority"] == "none"


def test_contract_validator_passes_repository_files() -> None:
    module = load_verifier()
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    errors = module.validate_contract_files(
        ROOT,
        payload,
        tracked_files=[
            "app.py",
            "src/macropulse/platform/status.py",
            "src/macropulse/platform/orchestration.py",
        ],
    )
    assert errors == []


def test_contract_validator_grandfathers_protected_base_evidence() -> None:
    module = load_verifier()
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    legacy = (
        "reports/inflation_operational_validation/"
        "model1b_live_validation_20260731_105459.md"
    )
    errors = module.validate_contract_files(
        ROOT,
        payload,
        tracked_files=[legacy],
        baseline_tracked_files=[legacy],
    )
    assert errors == []


def test_contract_validator_blocks_new_tracked_operational_artifacts() -> None:
    module = load_verifier()
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    errors = module.validate_contract_files(
        ROOT,
        payload,
        tracked_files=[
            "data/macropulse.duckdb",
            "reports/macro_snapshots/macro_snapshot_20260808.json",
            (
                "reports/inflation_operational_validation/"
                "model1b_live_validation_20260808_121610.md"
            ),
        ],
        baseline_tracked_files=[],
    )
    assert any(
        "New forbidden operational artifact" in item
        for item in errors
    )


def test_static_safety_guard_passes() -> None:
    module = load_verifier()
    assert module.validate_static_safety(ROOT) == []


def test_ci_runs_pre_and_post_boundary_verification() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count("verify_phase2_platform.py --require-model1d-tags") >= 2
    assert text.count("verify_model1d_v038_release.py --require-tags") >= 2
    assert "python -m pytest -q --disable-warnings" in text


def test_ci_clean_tree_guard_ignores_only_generated_runtime_metadata() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert ":(exclude)reports/**" in text
    assert ":(exclude)data/**" in text
    assert ":(exclude)src/macropulse.egg-info/**" in text
    assert "git diff --quiet -- ." in text
