from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BRANCH = "model2-bvar-development"
EXPECTED_2F_CLOSURE = "c63ee4df92dd372f883feea4fc86eabae79ab358"
EXPECTED_2G_CLOSURE = "ad196fb5d9a2d0d2c9113ea94d1363573c0c3b56"
EXPECTED_2G_CI_RUN = 35754237381
EXPECTED_2G_CI_JOB = 106835847139
EXPECTED_EVIDENCE_PAYLOAD_HASH = "2f65c3dda0df6d8a501887bbf34671fe80e3292b296bce3e295d9c32fff16bf7"

EXPECTED_DELTA = {
    "MODEL2G_EVALUATION_CONTRACT.json",
    "MODEL2G_SELECTION_EVIDENCE.json",
    "docs/MODEL2G_PSEUDOREALTIME_EVALUATION.md",
    "src/macropulse/bvar/benchmarks.py",
    "src/macropulse/bvar/evaluation.py",
    "scripts/run_model2g_evaluation.py",
    "scripts/smoke_model2g_evaluation.py",
    "scripts/verify_model2g_evaluation.py",
    "scripts/verify_model2f_scenarios.py",
    "tests/test_model2g_evaluation.py",
    ".github/workflows/model2-bvar-guard.yml",
}

FROZEN_CONTENT = EXPECTED_DELTA - {
    "scripts/verify_model2g_evaluation.py",
    ".github/workflows/model2-bvar-guard.yml",
}


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def names(output: str) -> set[str]:
    return {
        line.strip().replace("\\", "/")
        for line in output.splitlines()
        if line.strip()
    }


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_payload_hash(payload: dict) -> str:
    copy = dict(payload)
    copy.pop("evidence_payload_hash", None)
    encoded = json.dumps(
        copy,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def main() -> int:
    errors: list[str] = []
    try:
        branch = git("branch", "--show-current")
        if branch and branch != EXPECTED_BRANCH:
            errors.append("Wrong branch.")

        for ancestor in (EXPECTED_2F_CLOSURE, EXPECTED_2G_CLOSURE):
            result = subprocess.run(
                ["git", "merge-base", "--is-ancestor", ancestor, "HEAD"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                errors.append("HEAD does not descend from " + ancestor)

        closure_delta = names(
            git(
                "diff",
                "--name-only",
                EXPECTED_2F_CLOSURE + ".." + EXPECTED_2G_CLOSURE,
            )
        )
        bad = sorted(closure_delta - EXPECTED_DELTA)
        missing = sorted(EXPECTED_DELTA - closure_delta)
        if bad:
            errors.append("Unexpected frozen 2G paths: " + ", ".join(bad))
        if missing:
            errors.append("Missing frozen 2G paths: " + ", ".join(missing))

        for path in sorted(FROZEN_CONTENT):
            result = subprocess.run(
                ["git", "diff", "--quiet", EXPECTED_2G_CLOSURE, "--", path],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                errors.append("Frozen 2G content changed: " + path)

        contract = json.loads(
            git(
                "show",
                EXPECTED_2G_CLOSURE + ":MODEL2G_EVALUATION_CONTRACT.json",
            )
        )
        if contract.get("workstream") != "2G":
            errors.append("Wrong frozen 2G workstream.")
        if contract.get("production_authority") != "none":
            errors.append("Frozen 2G production authority changed.")

        evidence = json.loads(
            (ROOT / "MODEL2G_SELECTION_EVIDENCE.json").read_text(
                encoding="utf-8"
            )
        )
        if evidence.get("evidence_payload_hash") != EXPECTED_EVIDENCE_PAYLOAD_HASH:
            errors.append("Frozen 2G evidence payload identity changed.")
        if canonical_payload_hash(evidence) != EXPECTED_EVIDENCE_PAYLOAD_HASH:
            errors.append("Frozen 2G evidence payload hash mismatch.")
        if evidence.get("prospective_retuning_after_freeze") is not False:
            errors.append("Frozen 2G evidence permits prospective retuning.")
        if evidence.get("automatic_switching_after_freeze") is not False:
            errors.append("Frozen 2G evidence permits automatic switching.")

        selected = evidence.get("selected_candidate", {})
        if selected.get("candidate_id") != "a69878bf644615c5":
            errors.append("Frozen selected candidate ID changed.")
        if selected.get("lags") != 2:
            errors.append("Frozen selected lag order changed.")
        if abs(float(selected.get("shrinkage", -1.0)) - 0.1) > 1e-12:
            errors.append("Frozen selected shrinkage changed.")

        implementation = evidence.get("implementation_hashes", {})
        for path, expected in implementation.items():
            file_path = ROOT / path
            if not file_path.exists():
                errors.append("2G implementation path missing: " + path)
            elif sha256_file(file_path) != expected:
                errors.append("Frozen 2G implementation hash changed: " + path)

        table = evidence.get("selection_table", [])
        if len(table) != 6:
            errors.append("Frozen 2G evidence must contain six candidates.")
        else:
            ordered = sorted(
                table,
                key=lambda row: (
                    -float(row["mean_log_predictive_density"]),
                    float(row["mean_crps"]),
                    float(row["mean_rmse"]),
                    str(row["candidate_id"]),
                ),
            )
            if [str(row["candidate_id"]) for row in table] != [
                str(row["candidate_id"]) for row in ordered
            ]:
                errors.append("Frozen 2G selection ordering changed.")
            selected_rows = [
                row for row in table if bool(row.get("selected"))
            ]
            if len(selected_rows) != 1 or int(selected_rows[0]["rank"]) != 1:
                errors.append("Frozen 2G selected-row identity invalid.")
            for row in table:
                if int(row.get("minimum_cell_n", 0)) < 8:
                    errors.append("Frozen 2G evidence below minimum cell count.")
                for key in (
                    "mean_log_predictive_density",
                    "mean_crps",
                    "mean_rmse",
                ):
                    if not math.isfinite(float(row[key])):
                        errors.append("Frozen 2G metric non-finite: " + key)

        workflow = (
            ROOT / ".github" / "workflows" / "model2-bvar-guard.yml"
        ).read_text(encoding="utf-8")
        for token in (
            "python scripts/verify_model2g_evaluation.py",
            "tests/test_model2g_evaluation.py",
        ):
            if token not in workflow:
                errors.append("Current CI lost frozen 2G gate: " + token)

    except Exception as exc:
        errors.append(str(exc))

    if errors:
        print("Model 2G frozen pseudo-real-time evaluation verification: FAIL")
        for error in errors:
            print("- " + error)
        return 1

    print("Model 2G frozen pseudo-real-time evaluation verification: PASS")
    print("2F closure: " + EXPECTED_2F_CLOSURE[:7])
    print("2G closure: " + EXPECTED_2G_CLOSURE[:7])
    print("2G closure CI run: " + str(EXPECTED_2G_CI_RUN))
    print("2G closure CI job: " + str(EXPECTED_2G_CI_JOB))
    print("Frozen delta paths: 11")
    print("Descendant-safe verification: PASS")
    print("Selected candidate: p=2 lambda=0.1 id=a69878bf644615c5")
    print("Prospective retuning/switching: prohibited")
    print("Production authority: none")
    print("Next: Model 2H permitted on descendants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
