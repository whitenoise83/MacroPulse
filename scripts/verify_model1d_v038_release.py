from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST_MODEL1D_v0.3.8.txt"
RELEASE = ROOT / "MODEL1D_v0.3.8_RELEASE.json"

OPERATIONAL_TAG = "model1d-v0.3.8-prospective-shadow-operational"
OPERATIONAL_COMMIT = "6e1ff2a"
RESEARCH_RELEASE_TAG = "model1d-v0.3.8-research-release"
RESEARCH_RELEASE_COMMIT = "f3ae8f1"

MANIFEST_PATTERN = re.compile(r"^([0-9a-f]{64})  (.+)$")

FROZEN_OPERATIONAL_PATHS = (
    "config/macro_state_governance.yml",
    "scripts/report_macro_state_shadow_status.py",
    "scripts/resolve_macro_state_shadow_outcomes.py",
    "scripts/run_macro_state_prospective_shadow.py",
    "scripts/run_macro_state_shadow_operations.py",
    "src/macropulse/macro_state/prospective_shadow.py",
    "src/macropulse/macro_state/prospective_shadow_service.py",
    "src/macropulse/macro_state/shadow_outcomes.py",
    "src/macropulse/macro_state/shadow_outcomes_service.py",
    "src/macropulse/operations/model1d_shadow_monitoring.py",
    "src/macropulse/operations/model1d_shadow_operations.py",
    "ui/macro_state_shadow.py",
)

PROHIBITED_TRACKED_PREFIXES = (
    "data/macropulse.duckdb",
    "data/backups/",
    "reports/macro_state_shadow_monitoring/",
)


class VerificationError(RuntimeError):
    """Raised when the frozen release contract is violated."""


def canonical_text_bytes(path: Path) -> bytes:
    raw = path.read_bytes()
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_text_bytes(path)).hexdigest()


def parse_manifest(path: Path = MANIFEST) -> list[tuple[str, str]]:
    if not path.is_file():
        raise VerificationError(f"Missing release manifest: {path.relative_to(ROOT)}")

    entries: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = MANIFEST_PATTERN.fullmatch(line.strip())
        if match:
            entries.append((match.group(1), match.group(2)))

    if not entries:
        raise VerificationError("Release manifest contains no SHA-256 file entries.")
    return entries


def verify_manifest_hashes() -> list[str]:
    checked: list[str] = []
    for expected, relative_name in parse_manifest():
        path = ROOT / relative_name
        if not path.is_file():
            raise VerificationError(f"Manifest file is missing: {relative_name}")
        actual = canonical_sha256(path)
        if actual != expected:
            raise VerificationError(
                f"Manifest hash mismatch for {relative_name}: "
                f"expected {expected}, got {actual}"
            )
        checked.append(relative_name)
    return checked


def load_release() -> dict[str, object]:
    if not RELEASE.is_file():
        raise VerificationError("Missing MODEL1D_v0.3.8_RELEASE.json")
    payload = json.loads(RELEASE.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise VerificationError("Release metadata must be a JSON object.")
    return payload


def verify_release_boundary() -> None:
    release = load_release()
    expected = {
        "model_id": "US_MACRO_STATE_1D",
        "version": "0.3.8",
        "lifecycle_status": "development",
        "evidence_type": "prospective_shadow",
        "release_status": "prospective_shadow_operational_research_only",
        "promotion_authority": "none",
        "promotion_approved": False,
        "switching_approved": False,
        "blending_approved": False,
        "source_replacement_approved": False,
        "formal_comparison_permitted_at_freeze": False,
        "current_conclusion": "insufficient_prospective_evidence",
        "minimum_complete_target_months": 12,
        "operational_commit": OPERATIONAL_COMMIT,
        "operational_tag": OPERATIONAL_TAG,
    }
    for key, expected_value in expected.items():
        actual = release.get(key)
        if actual != expected_value:
            raise VerificationError(
                f"Release boundary mismatch for {key}: "
                f"expected {expected_value!r}, got {actual!r}"
            )


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def resolved_commit(ref: str) -> str:
    result = git("rev-parse", f"{ref}^{{commit}}")
    return result.stdout.strip()


def verify_tag(tag: str, expected_commit_prefix: str) -> None:
    expected = resolved_commit(expected_commit_prefix)
    actual = resolved_commit(tag)
    if actual != expected:
        raise VerificationError(
            f"Tag {tag} points to {actual[:12]}, expected {expected[:12]}."
        )


def verify_frozen_operational_paths() -> None:
    result = git(
        "diff",
        "--quiet",
        OPERATIONAL_TAG,
        "--",
        *FROZEN_OPERATIONAL_PATHS,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise VerificationError(
            "Unable to compare frozen operational paths:\n"
            + result.stderr.strip()
        )
    if result.returncode == 1:
        changed = git(
            "diff",
            "--name-only",
            OPERATIONAL_TAG,
            "--",
            *FROZEN_OPERATIONAL_PATHS,
        ).stdout.strip()
        raise VerificationError(
            "Frozen operational files differ from the operational tag:\n"
            + changed
        )


def tracked_files() -> Iterable[str]:
    output = git("ls-files").stdout
    for line in output.splitlines():
        clean = line.strip().replace("\\", "/")
        if clean:
            yield clean


def verify_no_database_artifacts_tracked() -> None:
    violations: list[str] = []
    for tracked in tracked_files():
        for prefix in PROHIBITED_TRACKED_PREFIXES:
            if tracked == prefix or tracked.startswith(prefix):
                violations.append(tracked)
                break
    if violations:
        raise VerificationError(
            "Local database or monitoring artifacts are tracked:\n"
            + "\n".join(sorted(violations))
        )


def verify_repository(require_tags: bool) -> list[str]:
    checked = verify_manifest_hashes()
    verify_release_boundary()
    verify_no_database_artifacts_tracked()

    if require_tags:
        verify_tag(OPERATIONAL_TAG, OPERATIONAL_COMMIT)
        verify_tag(RESEARCH_RELEASE_TAG, RESEARCH_RELEASE_COMMIT)
        verify_frozen_operational_paths()

    return checked


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify the frozen Model 1D v0.3.8 research-release boundary."
    )
    parser.add_argument(
        "--require-tags",
        action="store_true",
        help="Also verify published tags and frozen operational paths.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        checked = verify_repository(require_tags=args.require_tags)
    except (VerificationError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"Model 1D v0.3.8 release verification: FAIL", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1

    print("Model 1D v0.3.8 release verification: PASS")
    print(f"Manifest files verified: {len(checked)}")
    print("Research boundary: PASS")
    print("Tracked database artifacts: none")
    if args.require_tags:
        print(f"Operational tag: {OPERATIONAL_TAG} -> {OPERATIONAL_COMMIT}")
        print(f"Research tag: {RESEARCH_RELEASE_TAG} -> {RESEARCH_RELEASE_COMMIT}")
        print("Frozen operational paths: unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
