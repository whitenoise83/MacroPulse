from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from macropulse.data.repository import MacroRepository
from macropulse.platform.orchestration import (
    PlatformOperationError,
    build_dry_run_plan,
    execute_platform_operations,
    serialise_operation_error,
    serialise_operation_result,
)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "MacroPulse Phase 2C guarded orchestration for governed Models "
            "1A-1C with an explicit Model 1D eligibility gate."
        )
    )
    parser.add_argument(
        "--as-of",
        type=_parse_date,
        default=date.today(),
        help="Operational cutoff in YYYY-MM-DD form. Defaults to today.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Execute mutating upstream commands. Without this flag the command "
            "is a read-only dry run."
        ),
    )
    parser.add_argument(
        "--run-model1d",
        action="store_true",
        help=(
            "Permit the orchestrator to invoke the existing governed Model 1D "
            "monthly operation only when its explicit eligibility gate permits. "
            "Existing monthly predictions are never recreated."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the deterministic operation result as JSON.",
    )
    return parser


def _print_human(result: dict) -> None:
    print("MacroPulse Phase 2C governed orchestration")
    print(f"Mode: {result['mode']}")
    print(f"As of: {result['as_of']}")
    print()

    if result["mode"] == "dry_run":
        print("Planned steps:")
        for step in result["steps"]:
            component = f" [{step['component']}]" if step.get("component") else ""
            print(f"  {step['step']}{component}: {step['action']}")
    else:
        print("Executed steps:")
        for outcome in result["outcomes"]:
            component = f" [{outcome.component}]" if outcome.component else ""
            print(f"  {outcome.step}{component}: {outcome.status}")

    print()
    gate = result["model1d_gate"]
    print(f"Model 1D gate: {gate['action']}")
    print(f"Model 1D state month: {gate['state_date']}")
    if gate.get("existing_shadow_run_id"):
        print(f"Existing Model 1D run: {gate['existing_shadow_run_id']}")
    print(f"Unresolved due Model 1D runs: {gate['unresolved_due_runs']}")

    readiness = result["status"]["readiness"].iloc[0]
    print()
    print(
        "Production sources ready: "
        + ("yes" if readiness["production_sources_ready"] else "no")
    )
    print(
        "Model 1D shadow valid: "
        + ("yes" if readiness["model1d_shadow_valid"] else "no")
    )
    print(
        "Platform ready for downstream: "
        + ("yes" if readiness["platform_ready_for_downstream"] else "no")
    )


def main() -> int:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parents[1]
    repository = MacroRepository()

    try:
        if args.execute:
            result = execute_platform_operations(
                repository,
                as_of=args.as_of,
                project_root=root,
                include_model1d=args.run_model1d,
            )
        else:
            result = build_dry_run_plan(
                repository,
                as_of=args.as_of,
                project_root=root,
                include_model1d=args.run_model1d,
            )
    except PlatformOperationError as exc:
        if args.json:
            print(json.dumps(serialise_operation_error(exc), indent=2, sort_keys=True))
        else:
            print(f"BLOCKED: {exc}")
            if exc.outcomes:
                last = exc.outcomes[-1]
                if last.stdout:
                    print()
                    print(last.stdout.rstrip())
                if last.stderr:
                    print()
                    print(last.stderr.rstrip())
        return 2

    if args.json:
        print(json.dumps(serialise_operation_result(result), indent=2, sort_keys=True))
    else:
        _print_human(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
