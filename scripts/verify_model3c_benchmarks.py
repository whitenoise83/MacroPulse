from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BRANCH = "model3-output-gap-development"
MODEL2_TAG = "model2-bvar-v1.0.2"
MODEL2_COMMIT = "cda24988e772cd2b96be612b7d455c54a06f44fa"
MODEL3B_COMMIT = "5849b89367defdef68c0676fdcd1d2f7182bd873"
EXPECTED_DELTA = {
    "MODEL3C_BENCHMARK_CONTRACT.json",
    "docs/MODEL3C_BENCHMARK_CONTRACT.md",
    "src/macropulse/slack/benchmarks.py",
    "scripts/verify_model3c_benchmarks.py",
    "tests/test_model3c_contract.py",
    "tests/test_model3c_benchmarks.py",
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
        errors.append("Wrong branch: " + branch)

    # chr(94) avoids Windows cmd.exe caret escaping when this file is patched or inspected inline.
    peeled = git("rev-parse", MODEL2_TAG + chr(94) + "{commit}")
    if peeled != MODEL2_COMMIT:
        errors.append("Immutable Model 2 tag does not resolve to expected commit.")

    for ancestor, label in ((MODEL2_COMMIT, "Model 2"), (MODEL3B_COMMIT, "Model 3B")):
        try:
            subprocess.check_call(
                ["git", "merge-base", "--is-ancestor", ancestor, "HEAD"],
                cwd=ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            errors.append("HEAD does not descend from " + label + " boundary.")

    committed = set(filter(None, git("diff", "--name-only", MODEL3B_COMMIT + "..HEAD").splitlines()))
    staged = set(filter(None, git("diff", "--cached", "--name-only").splitlines()))
    working = set(filter(None, git("diff", "--name-only").splitlines()))
    untracked = set(filter(None, git("ls-files", "--others", "--exclude-standard").splitlines()))
    governed_untracked = {
        p for p in untracked
        if not any(p.startswith(prefix) for prefix in IGNORED_UNTRACKED_PREFIXES)
    }
    delta = committed | staged | working | governed_untracked
    if sorted(delta - EXPECTED_DELTA):
        errors.append("Unexpected 3C delta paths: " + ", ".join(sorted(delta - EXPECTED_DELTA)))
    if sorted(EXPECTED_DELTA - delta):
        errors.append("Missing 3C delta paths: " + ", ".join(sorted(EXPECTED_DELTA - delta)))

    c = json.loads((ROOT / "MODEL3C_BENCHMARK_CONTRACT.json").read_text())
    if c.get("model3b_base_commit") != MODEL3B_COMMIT:
        errors.append("Wrong Model 3B predecessor.")
    families = c.get("benchmark_families", {})
    expected = {
        "deterministic_linear_trend", "hp_filter",
        "one_sided_hp_filter", "hamilton_regression"
    }
    if set(families) != expected:
        errors.append("Unexpected benchmark-family set.")
    if families.get("hp_filter", {}).get("role") != "diagnostic_benchmark":
        errors.append("Conventional HP must remain diagnostic.")
    if families.get("one_sided_hp_filter", {}).get("uses_only_information_through_origin") is not True:
        errors.append("One-sided HP must be origin-safe.")
    h = families.get("hamilton_regression", {})
    if h.get("horizon_quarters") != 8 or h.get("lags") != 4:
        errors.append("Hamilton benchmark must use h=8 and p=4.")

    g = c.get("governance", {})
    for key in (
        "production_winner_frozen", "automatic_selection_allowed",
        "automatic_promotion_allowed", "model1_integration_allowed",
        "model2_forecast_integration_allowed", "multivariate_slack_estimation_allowed",
        "state_space_core_estimation_allowed", "predecessor_modification_allowed",
        "database_writes_allowed",
    ):
        if g.get(key) is not False:
            errors.append("Governance flag must be false: " + key)

    if errors:
        print("Model 3C benchmark verification: FAIL")
        for error in errors:
            print("- " + error)
        return 1

    print("Model 3C benchmark verification: PASS")
    print("Model 3B base: " + MODEL3B_COMMIT[:7])
    print("Immutable Model 2 base: " + MODEL2_COMMIT[:7])
    print("3C delta paths: 6")
    print("Benchmarks: linear trend, HP diagnostic, one-sided HP, Hamilton h=8 p=4")
    print("Production winner: none")
    print("Next authorized workstream: 3D state-space potential output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
