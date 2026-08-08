from __future__ import annotations

import calendar
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable, Sequence

import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.platform.status import (
    PRODUCTION_COMPONENTS,
    collect_platform_status,
    component_specs,
    serialise_platform_status,
)


EXPECTED_IDENTITIES = {
    "1A": ("US_GDP_NOWCAST_1A", "1.0.0", "production"),
    "1B": ("US_INFLATION_NOWCAST_1B", "1.0.0", "production"),
    "1C": ("US_LABOUR_NOWCAST_1C", "1.0.0", "production"),
    "1D": ("US_MACRO_STATE_1D", "0.3.8", "development"),
}

DOWNLOAD_COMMANDS = {
    "1A": ("scripts/download_fred_data.py", "--skip-initial"),
    "1B": ("scripts/download_inflation_data.py",),
    "1C": ("scripts/download_labour_data.py",),
}

MODEL_COMMANDS = {
    "1A": ("scripts/run_baseline_nowcast.py",),
    "1B": ("scripts/run_inflation_nowcast.py",),
    "1C": ("scripts/run_labour_nowcast.py",),
}


@dataclass(frozen=True)
class CommandOutcome:
    step: str
    component: str | None
    command: tuple[str, ...]
    returncode: int
    status: str
    stdout: str
    stderr: str


class PlatformOperationError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        outcomes: list[CommandOutcome] | None = None,
        status: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.outcomes = outcomes or []
        self.status = status


StatusProvider = Callable[[MacroRepository, date, Path], dict[str, Any]]


def _month_end(value: date) -> date:
    return date(value.year, value.month, calendar.monthrange(value.year, value.month)[1])


def validate_platform_boundary(project_root: Path) -> None:
    specs = component_specs(project_root)
    for component, expected in EXPECTED_IDENTITIES.items():
        spec = specs.get(component)
        if spec is None:
            raise PlatformOperationError(
                f"Phase II boundary is missing component {component}."
            )
        actual = (spec.model_id, spec.model_version, spec.lifecycle_status)
        if actual != expected:
            raise PlatformOperationError(
                "Unknown or changed governed identity for "
                f"{component}: expected {expected}, found {actual}. "
                "Orchestration fails closed."
            )


def _default_status_provider(
    repository: MacroRepository,
    as_of: date,
    project_root: Path,
) -> dict[str, Any]:
    return collect_platform_status(
        repository,
        as_of=as_of,
        project_root=project_root,
    )


def _run_python_command(
    args: Sequence[str],
    cwd: Path,
    *,
    step: str,
    component: str | None,
) -> CommandOutcome:
    command = (sys.executable, *tuple(args))
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return CommandOutcome(
        step=step,
        component=component,
        command=tuple(command),
        returncode=int(completed.returncode),
        status="success" if completed.returncode == 0 else "failed",
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _component_frame(status: dict[str, Any]) -> pd.DataFrame:
    return status["components"].copy().set_index("component", drop=False)


def _production_needing_refresh(status: dict[str, Any]) -> list[str]:
    components = _component_frame(status)
    result: list[str] = []
    for component in PRODUCTION_COMPONENTS:
        if component not in components.index:
            result.append(component)
        elif not bool(components.loc[component, "ready"]):
            result.append(component)
    return result


def _production_ready(status: dict[str, Any]) -> bool:
    readiness = status["readiness"]
    return bool(
        not readiness.empty
        and readiness.iloc[0]["production_sources_ready"]
    )


def _assert_component_refreshed(
    status: dict[str, Any],
    *,
    component: str,
    as_of: date,
) -> None:
    components = _component_frame(status)
    if component not in components.index:
        raise PlatformOperationError(
            f"{component} is missing after its governed model command.",
            status=status,
        )
    row = components.loc[component]
    if not bool(row["ready"]):
        raise PlatformOperationError(
            f"{component} remains blocked after its governed model command: "
            f"{row['freshness_state']}.",
            status=status,
        )
    cutoff = pd.Timestamp(row["information_cutoff"]).date()
    if cutoff != as_of:
        raise PlatformOperationError(
            f"{component} did not persist the requested operational cutoff. "
            f"Expected {as_of}, found {cutoff}.",
            status=status,
        )


def _existing_model1d_month(
    repository: MacroRepository,
    *,
    model_version: str,
    state_date: date,
) -> pd.DataFrame:
    return repository.query_df(
        """
        SELECT shadow_run_id, state_date, information_cutoff, status
        FROM macro_state_shadow_runs
        WHERE model_version = ?
          AND state_date = ?
        ORDER BY created_at
        """,
        [model_version, state_date],
    )


def _unresolved_model1d_due(
    repository: MacroRepository,
    *,
    model_version: str,
    as_of: date,
) -> pd.DataFrame:
    return repository.query_df(
        """
        SELECT
            r.shadow_run_id,
            r.state_date,
            r.target_expected_available_date,
            COUNT(o.benchmark_id) AS outcome_count
        FROM macro_state_shadow_runs r
        LEFT JOIN macro_state_shadow_outcomes o
          ON o.shadow_run_id = r.shadow_run_id
        WHERE r.model_version = ?
          AND r.target_expected_available_date <= ?
        GROUP BY
            r.shadow_run_id,
            r.state_date,
            r.target_expected_available_date
        HAVING COUNT(o.benchmark_id) < 2
        ORDER BY r.state_date
        """,
        [model_version, as_of],
    )


def model1d_gate(
    repository: MacroRepository,
    *,
    as_of: date,
    project_root: Path,
    production_status: dict[str, Any],
) -> dict[str, Any]:
    if not _production_ready(production_status):
        return {
            "action": "blocked_production_sources",
            "eligible": False,
            "state_date": _month_end(as_of),
            "existing_shadow_run_id": None,
            "unresolved_due_runs": 0,
        }

    version = component_specs(project_root)["1D"].model_version
    state_date = _month_end(as_of)
    existing = _existing_model1d_month(
        repository,
        model_version=version,
        state_date=state_date,
    )
    due = _unresolved_model1d_due(
        repository,
        model_version=version,
        as_of=as_of,
    )
    existing_id = (
        str(existing.iloc[0]["shadow_run_id"])
        if not existing.empty
        else None
    )
    due_count = int(len(due))

    if existing_id is not None and due_count == 0:
        action = "skip_existing_month"
        eligible = False
    elif existing_id is not None:
        action = "resolve_due_outcomes_only"
        eligible = True
    elif due_count > 0:
        action = "create_monthly_prediction_and_resolve_due_outcomes"
        eligible = True
    else:
        action = "create_monthly_prediction"
        eligible = True

    return {
        "action": action,
        "eligible": eligible,
        "state_date": state_date,
        "existing_shadow_run_id": existing_id,
        "unresolved_due_runs": due_count,
    }


def _model1d_command_for_gate(
    gate: dict[str, Any],
    as_of: date,
) -> list[str]:
    action = str(gate["action"])
    if action in {"blocked_production_sources", "skip_existing_month"}:
        return []
    command = [
        "scripts/run_macro_state_shadow_operations.py",
        "--as-of",
        as_of.isoformat(),
        "--no-report",
    ]
    if action == "resolve_due_outcomes_only":
        command.append("--skip-prediction")
    return command


def build_dry_run_plan(
    repository: MacroRepository,
    *,
    as_of: date,
    project_root: Path,
    include_model1d: bool,
    status_provider: StatusProvider = _default_status_provider,
) -> dict[str, Any]:
    validate_platform_boundary(project_root)
    if as_of > date.today():
        raise PlatformOperationError("Operational cutoff cannot be in the future.")

    status = status_provider(repository, as_of, project_root)
    needs_refresh = _production_needing_refresh(status)
    gate = model1d_gate(
        repository,
        as_of=as_of,
        project_root=project_root,
        production_status=status,
    )

    steps: list[dict[str, Any]] = [
        {
            "step": "verify_model1d_release",
            "component": "1D",
            "action": "would_run",
            "command": [
                "scripts/verify_model1d_v038_release.py",
                "--require-tags",
            ],
        },
        {
            "step": "refresh_release_calendar",
            "component": None,
            "action": "would_run",
            "command": ["scripts/refresh_release_calendar.py"],
        },
    ]

    for component in PRODUCTION_COMPONENTS:
        if component in needs_refresh:
            steps.append(
                {
                    "step": "refresh_source_data",
                    "component": component,
                    "action": "would_run",
                    "command": list(DOWNLOAD_COMMANDS[component]),
                }
            )
            model_command = list(MODEL_COMMANDS[component])
            if component in {"1B", "1C"}:
                model_command.extend(["--as-of", as_of.isoformat()])
            steps.append(
                {
                    "step": "run_governed_model",
                    "component": component,
                    "action": "would_run",
                    "command": model_command,
                }
            )
        else:
            steps.append(
                {
                    "step": "run_governed_model",
                    "component": component,
                    "action": "skip_already_fresh",
                    "command": [],
                }
            )

    if include_model1d:
        steps.append(
            {
                "step": "model1d_monthly_operation",
                "component": "1D",
                "action": gate["action"],
                "command": _model1d_command_for_gate(gate, as_of),
            }
        )
    else:
        steps.append(
            {
                "step": "model1d_monthly_operation",
                "component": "1D",
                "action": "not_requested",
                "eligible_action": gate["action"],
                "command": [],
            }
        )

    return {
        "mode": "dry_run",
        "as_of": as_of,
        "production_needing_refresh": needs_refresh,
        "model1d_gate": gate,
        "steps": steps,
        "status": status,
    }


def execute_platform_operations(
    repository: MacroRepository,
    *,
    as_of: date,
    project_root: Path,
    include_model1d: bool = False,
    status_provider: StatusProvider = _default_status_provider,
    command_runner: Callable[
        [Sequence[str], Path, str, str | None], CommandOutcome
    ] | None = None,
) -> dict[str, Any]:
    validate_platform_boundary(project_root)
    today = date.today()
    if as_of > today:
        raise PlatformOperationError("Operational cutoff cannot be in the future.")
    if as_of != today:
        raise PlatformOperationError(
            "Mutating Phase 2C operations require --as-of to equal today because "
            "the governed Model 1A entry point does not accept a historical "
            "information cutoff. Historical dates are dry-run/status only."
        )

    outcomes: list[CommandOutcome] = []

    def run(
        args: Sequence[str],
        *,
        step: str,
        component: str | None,
    ) -> CommandOutcome:
        if command_runner is None:
            outcome = _run_python_command(
                args,
                project_root,
                step=step,
                component=component,
            )
        else:
            outcome = command_runner(args, project_root, step, component)
        outcomes.append(outcome)
        if outcome.returncode != 0:
            raise PlatformOperationError(
                f"Platform operation failed at {step}"
                + (f" for {component}" if component else "")
                + ". Downstream operations were stopped.",
                outcomes=outcomes,
            )
        return outcome

    run(
        ("scripts/verify_model1d_v038_release.py", "--require-tags"),
        step="verify_model1d_release",
        component="1D",
    )
    run(
        ("scripts/refresh_release_calendar.py",),
        step="refresh_release_calendar",
        component=None,
    )

    status = status_provider(repository, as_of, project_root)
    needs_refresh = _production_needing_refresh(status)

    for component in PRODUCTION_COMPONENTS:
        if component not in needs_refresh:
            outcomes.append(
                CommandOutcome(
                    step="run_governed_model",
                    component=component,
                    command=(),
                    returncode=0,
                    status="skipped_already_fresh",
                    stdout="",
                    stderr="",
                )
            )
            continue

        run(
            DOWNLOAD_COMMANDS[component],
            step="refresh_source_data",
            component=component,
        )

        model_command = list(MODEL_COMMANDS[component])
        if component in {"1B", "1C"}:
            model_command.extend(["--as-of", as_of.isoformat()])
        run(
            tuple(model_command),
            step="run_governed_model",
            component=component,
        )

        status = status_provider(repository, as_of, project_root)
        try:
            _assert_component_refreshed(
                status,
                component=component,
                as_of=as_of,
            )
        except PlatformOperationError as exc:
            exc.outcomes = outcomes
            raise

    final_status = status_provider(repository, as_of, project_root)
    if not _production_ready(final_status):
        raise PlatformOperationError(
            "Production source models are not ready after governed operations. "
            "Model 1D was not invoked.",
            outcomes=outcomes,
            status=final_status,
        )

    gate = model1d_gate(
        repository,
        as_of=as_of,
        project_root=project_root,
        production_status=final_status,
    )

    model1d_execution = "not_requested"
    if include_model1d:
        command = _model1d_command_for_gate(gate, as_of)
        if command:
            run(
                tuple(command),
                step="model1d_monthly_operation",
                component="1D",
            )
            model1d_execution = "executed"
        else:
            model1d_execution = gate["action"]

    final_status = status_provider(repository, as_of, project_root)
    return {
        "mode": "execute",
        "as_of": as_of,
        "outcomes": outcomes,
        "production_needing_refresh": needs_refresh,
        "model1d_requested": bool(include_model1d),
        "model1d_gate": gate,
        "model1d_execution": model1d_execution,
        "status": final_status,
    }


def serialise_operation_result(result: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "mode": result["mode"],
        "as_of": str(result["as_of"]),
        "production_needing_refresh": list(
            result.get("production_needing_refresh", [])
        ),
        "model1d_gate": {
            key: (value.isoformat() if isinstance(value, date) else value)
            for key, value in result["model1d_gate"].items()
        },
    }
    if "steps" in result:
        payload["steps"] = result["steps"]
    if "model1d_requested" in result:
        payload["model1d_requested"] = result["model1d_requested"]
        payload["model1d_execution"] = result["model1d_execution"]
    if "outcomes" in result:
        payload["outcomes"] = [
            {**asdict(outcome), "command": list(outcome.command)}
            for outcome in result["outcomes"]
        ]
    payload["status"] = serialise_platform_status(result["status"])
    return payload


def serialise_operation_error(exc: PlatformOperationError) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "error": str(exc),
        "outcomes": [
            {**asdict(outcome), "command": list(outcome.command)}
            for outcome in exc.outcomes
        ],
    }
    if exc.status is not None:
        payload["status"] = serialise_platform_status(exc.status)
    return payload
