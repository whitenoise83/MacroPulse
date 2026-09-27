from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BRANCH = "model3-output-gap-development"
MODEL2_TAG = "model2-bvar-v1.0.2"
MODEL2_COMMIT = "cda24988e772cd2b96be612b7d455c54a06f44fa"
MODEL3A_COMMIT = "6f45208103a5ac1a900317a33c0038d56920ffbb"
EXPECTED_DELTA = {
    "MODEL3B_DATA_VINTAGE_CONTRACT.json",
    "docs/MODEL3B_REAL_TIME_DATA_CONTRACT.md",
    "src/macropulse/slack/__init__.py",
    "src/macropulse/slack/data.py",
    "src/macropulse/slack/vintages.py",
    "scripts/verify_model3b_data.py",
    "tests/test_model3b_contract.py",
    "tests/test_model3b_data.py",
    "tests/test_model3b_vintages.py",
}
IGNORED_UNTRACKED_PREFIXES = (
    "reports/inflation_operational_validation/",
    "reports/labour_operational_validation/",
    "reports/decision_intelligence_snapshots/",
    "data/backups/",
    "src/macropulse.egg-info/",
)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> int:
    errors = []

    branch = git("branch", "--show-current")
    if branch and branch != EXPECTED_BRANCH:
        errors.append(f"Wrong branch: {branch}")

    if git("rev-parse", f"{MODEL2_TAG}" + chr(94) + "{commit}") != MODEL2_COMMIT:
        errors.append("Immutable Model 2 tag does not resolve to expected commit.")

    try:
        subprocess.check_call(
            ["git", "merge-base", "--is-ancestor", MODEL2_COMMIT, "HEAD"], cwd=ROOT
        )
    except subprocess.CalledProcessError:
        errors.append("HEAD does not descend from immutable Model 2 base.")

    try:
        subprocess.check_call(
            ["git", "merge-base", "--is-ancestor", MODEL3A_COMMIT, "HEAD"], cwd=ROOT
        )
    except subprocess.CalledProcessError:
        errors.append("HEAD does not descend from Model 3A closure.")

    committed = set(filter(None, git("diff", "--name-only", MODEL3A_COMMIT + "..HEAD").splitlines()))
    staged = set(filter(None, git("diff", "--cached", "--name-only").splitlines()))
    working = set(filter(None, git("diff", "--name-only").splitlines()))
    untracked = set(filter(None, git("ls-files", "--others", "--exclude-standard").splitlines()))
    governed_untracked = {
        p for p in untracked
        if not any(p.startswith(prefix) for prefix in IGNORED_UNTRACKED_PREFIXES)
    }
    delta = committed | staged | working | governed_untracked

    unexpected = sorted(delta - EXPECTED_DELTA)
    missing = sorted(EXPECTED_DELTA - delta)
    if unexpected:
        errors.append("Unexpected 3B delta paths: " + ", ".join(unexpected))
    if missing:
        errors.append("Missing 3B delta paths: " + ", ".join(missing))

    boundary = json.loads((ROOT / "MODEL3B_DATA_VINTAGE_CONTRACT.json").read_text())
    if boundary.get("model3a_base_commit") != MODEL3A_COMMIT:
        errors.append("Wrong Model 3A base commit in 3B contract.")
    if boundary.get("model2_base_commit") != MODEL2_COMMIT:
        errors.append("Wrong Model 2 base commit in 3B contract.")
    if boundary.get("required_series") != ["GDPC1", "UNRATE", "PCEPILFE"]:
        errors.append("Unexpected required-series contract.")

    vintage = boundary.get("vintage_contract", {})
    required_true = (
        "exact_vintage_or_governed_availability_evidence_required",
        "information_set_cutoff_required",
        "source_snapshot_hash_required",
        "deterministic_information_set_id_required",
        "no_look_ahead_required",
        "publication_lags_must_be_respected",
        "left_censored_first_state_not_admissible",
    )
    for key in required_true:
        if vintage.get(key) is not True:
            errors.append("Vintage contract must fail closed: " + key)
    if vintage.get("current_revised_history_may_not_masquerade_as_real_time") is not False:
        errors.append("Revised-history masquerade must be prohibited.")

    governance = boundary.get("governance", {})
    for key in (
        "estimation_allowed",
        "production_writes_allowed",
        "predecessor_modification_allowed",
        "generative_ai_in_governed_core_allowed",
        "automatic_promotion_allowed",
    ):
        if governance.get(key) is not False:
            errors.append("Governance flag must be false: " + key)

    if errors:
        print("Model 3B data/vintage verification: FAIL")
        for error in errors:
            print("- " + error)
        return 1

    print("Model 3B data/vintage verification: PASS")
    print("Model 3A base: " + MODEL3A_COMMIT[:7])
    print("Immutable Model 2 base: " + MODEL2_COMMIT[:7])
    print("3B delta paths: 9")
    print("Required series: GDPC1, UNRATE, PCEPILFE")
    print("Estimation authority: none")
    print("Next authorized workstream: 3C univariate trend/filter benchmarks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
