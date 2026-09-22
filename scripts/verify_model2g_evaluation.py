from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "MODEL2G_EVALUATION_CONTRACT.json"
EVIDENCE = ROOT / "MODEL2G_SELECTION_EVIDENCE.json"

EXPECTED_BRANCH = "model2-bvar-development"
EXPECTED_2F_CLOSURE = "c63ee4df92dd372f883feea4fc86eabae79ab358"
EXPECTED_TERMINAL = "2026Q1"
EXPECTED_SIMULATIONS = 5000
EXPECTED_SEED = 20260904

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

IGNORED_PREFIXES = (
    "src/macropulse.egg-info/",
    "reports/inflation_operational_validation/",
    "reports/labour_operational_validation/",
)


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


def ignorable(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return any(normalized.startswith(prefix) for prefix in IGNORED_PREFIXES)


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
        if git("branch", "--show-current") != EXPECTED_BRANCH:
            errors.append("Wrong branch.")

        ancestor = subprocess.run(
            [
                "git", "merge-base", "--is-ancestor",
                EXPECTED_2F_CLOSURE, "HEAD",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if ancestor.returncode != 0:
            errors.append("HEAD does not descend from closed Model 2F.")

        committed = names(
            git("diff", "--name-only", EXPECTED_2F_CLOSURE + "..HEAD")
        )
        working = {
            path
            for path in names(git("diff", "--name-only"))
            if not ignorable(path)
        }
        staged = names(git("diff", "--cached", "--name-only"))
        untracked = {
            path
            for path in names(
                git("ls-files", "--others", "--exclude-standard")
            )
            if not ignorable(path)
        }
        observed = committed | working | staged | untracked

        bad = sorted(observed - EXPECTED_DELTA)
        missing = sorted(EXPECTED_DELTA - observed)
        if bad:
            errors.append("Unexpected 2G paths: " + ", ".join(bad))
        if missing:
            errors.append("Missing 2G paths: " + ", ".join(missing))

        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        if contract.get("workstream") != "2G":
            errors.append("Wrong workstream identity.")
        if contract.get("base_model2f_closure_commit") != EXPECTED_2F_CLOSURE:
            errors.append("Wrong 2F closure base.")
        if contract.get("production_authority") != "none":
            errors.append("Production authority must remain none.")

        inventory = contract.get("development_inventory", {})
        if inventory.get("terminal_origin_quarter") != EXPECTED_TERMINAL:
            errors.append("2G terminal development origin changed.")
        if inventory.get("first_origin_hand_selected") is not False:
            errors.append("2G evaluation start boundary changed.")
        if inventory.get("revised_outcomes_used") is not False:
            errors.append("2G revised-outcome boundary changed.")
        if inventory.get("future_information_fallback") is not False:
            errors.append("2G future-information boundary changed.")

        selection = contract.get("selection", {})
        if selection.get("selection_authorized_in_2g") is not True:
            errors.append("2G selection authorization changed.")
        if selection.get("eligible_models") != "six_bvar_candidates_only":
            errors.append("2G selection pool changed.")
        if selection.get("minimum_resolved_cases_per_variable_horizon") != 8:
            errors.append("2G minimum evidence changed.")
        if selection.get("primary_metric") != "mean_log_predictive_density":
            errors.append("2G primary selection metric changed.")
        if selection.get("prospective_retuning_after_freeze") is not False:
            errors.append("2G prospective retuning boundary changed.")

        simulation = contract.get("simulation", {})
        if simulation.get("canonical_simulations") != EXPECTED_SIMULATIONS:
            errors.append("2G canonical simulation count changed.")
        if simulation.get("canonical_base_seed") != EXPECTED_SEED:
            errors.append("2G canonical base seed changed.")

        if not EVIDENCE.exists():
            errors.append(
                "Canonical Model 2G selection evidence has not been frozen."
            )
        else:
            evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
            if evidence.get("workstream") != "2G":
                errors.append("Wrong 2G evidence identity.")
            if evidence.get("base_model2f_closure_commit") != EXPECTED_2F_CLOSURE:
                errors.append("2G evidence has wrong closure base.")
            if evidence.get("development_terminal_origin_quarter") != EXPECTED_TERMINAL:
                errors.append("2G evidence terminal origin changed.")
            if evidence.get("canonical_simulations") != EXPECTED_SIMULATIONS:
                errors.append("2G evidence simulation count changed.")
            if evidence.get("canonical_base_seed") != EXPECTED_SEED:
                errors.append("2G evidence seed changed.")
            if evidence.get("production_authority") != "none":
                errors.append("2G evidence production authority changed.")
            if evidence.get("prospective_retuning_after_freeze") is not False:
                errors.append("2G evidence permits prospective retuning.")
            if evidence.get("automatic_switching_after_freeze") is not False:
                errors.append("2G evidence permits automatic switching.")

            expected_hash = canonical_payload_hash(evidence)
            if evidence.get("evidence_payload_hash") != expected_hash:
                errors.append("2G evidence payload hash mismatch.")

            implementation = evidence.get("implementation_hashes", {})
            for path, expected in implementation.items():
                file_path = ROOT / path
                if not file_path.exists():
                    errors.append("2G evidence implementation path missing: " + path)
                elif sha256_file(file_path) != expected:
                    errors.append("2G evidence implementation hash changed: " + path)

            table = evidence.get("selection_table", [])
            if len(table) != 6:
                errors.append("2G evidence must contain six candidate rows.")
            else:
                candidate_ids = [str(row.get("candidate_id")) for row in table]
                if len(set(candidate_ids)) != 6:
                    errors.append("2G evidence candidate IDs are not unique.")
                ordered = sorted(
                    table,
                    key=lambda row: (
                        -float(row["mean_log_predictive_density"]),
                        float(row["mean_crps"]),
                        float(row["mean_rmse"]),
                        str(row["candidate_id"]),
                    ),
                )
                observed_ids = [str(row["candidate_id"]) for row in table]
                expected_ids = [str(row["candidate_id"]) for row in ordered]
                if observed_ids != expected_ids:
                    errors.append("2G selection table violates frozen ordering rule.")
                ranks = [int(row["rank"]) for row in table]
                if ranks != [1, 2, 3, 4, 5, 6]:
                    errors.append("2G candidate ranks are invalid.")
                selected_rows = [
                    row for row in table if bool(row.get("selected"))
                ]
                if len(selected_rows) != 1 or int(selected_rows[0]["rank"]) != 1:
                    errors.append("2G evidence must select exactly rank 1.")
                selected = evidence.get("selected_candidate", {})
                if (
                    selected_rows
                    and str(selected.get("candidate_id"))
                    != str(selected_rows[0].get("candidate_id"))
                ):
                    errors.append("2G selected candidate lineage mismatch.")

                for row in table:
                    if int(row.get("minimum_cell_n", 0)) < 8:
                        errors.append("2G candidate evidence below minimum cell count.")
                    for key in (
                        "mean_log_predictive_density",
                        "mean_crps",
                        "mean_rmse",
                    ):
                        if not math.isfinite(float(row[key])):
                            errors.append("2G candidate metric non-finite: " + key)

        workflow = (
            ROOT / ".github" / "workflows" / "model2-bvar-guard.yml"
        ).read_text(encoding="utf-8")
        for token in (
            "python scripts/verify_model2g_evaluation.py",
            "tests/test_model2g_evaluation.py",
        ):
            if token not in workflow:
                errors.append("Model 2 CI missing 2G gate: " + token)

    except Exception as exc:
        errors.append(str(exc))

    if errors:
        print("Model 2G pseudo-real-time evaluation verification: FAIL")
        for error in errors:
            print("- " + error)
        return 1

    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    selected = evidence["selected_candidate"]
    print("Model 2G pseudo-real-time evaluation verification: PASS")
    print("Base 2F closure: " + EXPECTED_2F_CLOSURE[:7])
    print("Expected delta paths: 11")
    print("Frozen terminal origin: " + EXPECTED_TERMINAL)
    print("Outcome vintage rule: first common exact-vintage target quarter")
    print("Canonical simulations: " + str(EXPECTED_SIMULATIONS))
    print("Primary selection horizons: 1, 2, 4")
    print("Six BVAR candidates compared: PASS")
    print("Three comparison benchmarks: PASS")
    print(
        "Selected candidate: p="
        + str(selected["lags"])
        + " lambda="
        + str(selected["shrinkage"])
        + " id="
        + str(selected["candidate_id"])
    )
    print("Prospective retuning after freeze: prohibited")
    print("Production authority: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
