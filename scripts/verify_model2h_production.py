from __future__ import annotations
import json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BRANCH = "model2-bvar-development"
EXPECTED_2G_CLOSURE = "ad196fb5d9a2d0d2c9113ea94d1363573c0c3b56"
EXPECTED_2H_CLOSURE = "df1da2bcd54cf71277eb8bfe21f6c52caad1c302"
EXPECTED_2H_CI_RUN = 35769859027
EXPECTED_2H_CI_JOB = 106888547394
EXPECTED_TAG = "model2-bvar-v1.0.0"

EXPECTED_DELTA = {
    "MODEL2H_RELEASE_CANDIDATE_CONTRACT.json",
    "docs/MODEL2H_PRODUCTION_HARDENING.md",
    "src/macropulse/bvar/production.py",
    "scripts/smoke_model2h_production.py",
    "scripts/verify_model2h_production.py",
    "scripts/verify_model2g_evaluation.py",
    "tests/test_model2h_production.py",
    ".github/workflows/model2-bvar-guard.yml",
}

# These paths are permitted to evolve operationally on descendants.
# The 2G verifier is NOT unconstrained: it is checked below against the exact
# detached-HEAD compatibility transformation permitted for v1.0.1.
FROZEN_CONTENT = EXPECTED_DELTA - {
    "scripts/verify_model2h_production.py",
    "scripts/verify_model2g_evaluation.py",
    ".github/workflows/model2-bvar-guard.yml",
}


def git(*args: str) -> str:
    c = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return c.stdout.strip()


def names(output: str) -> set[str]:
    return {
        x.strip().replace("\\", "/")
        for x in output.splitlines()
        if x.strip()
    }


def expected_detached_head_2g_verifier() -> str:
    frozen = git(
        "show",
        EXPECTED_2H_CLOSURE + ":scripts/verify_model2g_evaluation.py",
    )

    old_guard = (
        '        if git("branch", "--show-current") != EXPECTED_BRANCH:\n'
        '            errors.append("Wrong branch.")\n'
    )
    new_guard = (
        '        branch = git("branch", "--show-current")\n'
        '        if branch and branch != EXPECTED_BRANCH:\n'
        '            errors.append("Wrong branch.")\n'
    )

    if frozen.count(old_guard) != 1:
        raise RuntimeError(
            "Frozen 2G verifier branch-guard identity is unexpected."
        )

    return frozen.replace(old_guard, new_guard, 1)


def main() -> int:
    errors = []

    try:
        branch = git("branch", "--show-current")
        if branch and branch != EXPECTED_BRANCH:
            errors.append("Wrong branch.")

        for ancestor in (EXPECTED_2G_CLOSURE, EXPECTED_2H_CLOSURE):
            c = subprocess.run(
                ["git", "merge-base", "--is-ancestor", ancestor, "HEAD"],
                cwd=ROOT,
            )
            if c.returncode != 0:
                errors.append("HEAD does not descend from " + ancestor)

        delta = names(
            git(
                "diff",
                "--name-only",
                EXPECTED_2G_CLOSURE + ".." + EXPECTED_2H_CLOSURE,
            )
        )

        if delta != EXPECTED_DELTA:
            extra = sorted(delta - EXPECTED_DELTA)
            missing = sorted(EXPECTED_DELTA - delta)
            if extra:
                errors.append(
                    "Unexpected frozen 2H paths: " + ", ".join(extra)
                )
            if missing:
                errors.append(
                    "Missing frozen 2H paths: " + ", ".join(missing)
                )

        for path in sorted(FROZEN_CONTENT):
            c = subprocess.run(
                [
                    "git",
                    "diff",
                    "--quiet",
                    EXPECTED_2H_CLOSURE,
                    "--",
                    path,
                ],
                cwd=ROOT,
            )
            if c.returncode != 0:
                errors.append("Frozen 2H content changed: " + path)

        expected_2g = expected_detached_head_2g_verifier()
        current_2g = (
            ROOT / "scripts" / "verify_model2g_evaluation.py"
        ).read_text(encoding="utf-8")

        # Compare logical lines so Git-show EOF newline stripping and
        # Windows checkout newline translation cannot create a false
        # compatibility failure. Any substantive line change still
        # fails closed.
        if current_2g.splitlines() != expected_2g.splitlines():
            errors.append(
                "Model 2G compatibility change differs from the exact "
                "detached-HEAD transformation permitted by 2H."
            )

        payload = json.loads(
            git(
                "show",
                EXPECTED_2H_CLOSURE
                + ":MODEL2H_RELEASE_CANDIDATE_CONTRACT.json",
            )
        )

        if payload.get("workstream") != "2H":
            errors.append("Wrong frozen 2H workstream.")

        if payload.get("production_authority") != "none_until_release_tag":
            errors.append("Frozen 2H authority boundary changed.")

        selected = payload.get("selected_specification", {})
        if (
            selected.get("candidate_id") != "a69878bf644615c5"
            or selected.get("lags") != 2
            or abs(float(selected.get("shrinkage", -1)) - 0.1) > 1e-12
        ):
            errors.append("Frozen 2H selected specification changed.")

        if payload.get("release", {}).get("planned_tag") != EXPECTED_TAG:
            errors.append("Frozen 2H planned release tag changed.")

        workflow = (
            ROOT / ".github" / "workflows" / "model2-bvar-guard.yml"
        ).read_text(encoding="utf-8")

        for token in (
            "python scripts/verify_model2h_production.py",
            "tests/test_model2h_production.py",
        ):
            if token not in workflow:
                errors.append("Current CI lost frozen 2H gate: " + token)

    except Exception as exc:
        errors.append(str(exc))

    if errors:
        print("Model 2H frozen production hardening verification: FAIL")
        for error in errors:
            print("- " + error)
        return 1

    print("Model 2H frozen production hardening verification: PASS")
    print("2H source closure: " + EXPECTED_2H_CLOSURE[:7])
    print("2H source CI run: " + str(EXPECTED_2H_CI_RUN))
    print("2H source CI job: " + str(EXPECTED_2H_CI_JOB))
    print("Frozen delta paths: 8")
    print("Descendant-safe verification: PASS")
    print("Exact Model 2G detached-HEAD compatibility: PASS")
    print("Frozen candidate: p=2 lambda=0.1 id=a69878bf644615c5")
    print("Planned release tag: " + EXPECTED_TAG)
    print("Production authority remains tag-gated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
