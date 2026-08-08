from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from macropulse.platform.orchestration import (
    CommandOutcome,
    PlatformOperationError,
    execute_platform_operations,
)
from test_phase2_platform_orchestration import FakeRepository, make_status, write_boundary


TODAY = date.today()


class RecordingRunner:
    def __init__(self, *, fail_component: str | None = None) -> None:
        self.fail_component = fail_component
        self.calls: list[tuple[tuple[str, ...], str, str | None]] = []

    def __call__(self, args, cwd, step, component):
        command = tuple(args)
        self.calls.append((command, step, component))
        failed = (
            self.fail_component is not None
            and step == "run_governed_model"
            and component == self.fail_component
        )
        return CommandOutcome(
            step=step,
            component=component,
            command=command,
            returncode=1 if failed else 0,
            status="failed" if failed else "success",
            stdout="",
            stderr="synthetic failure" if failed else "",
        )


def test_execute_is_idempotent_when_already_fresh(tmp_path: Path) -> None:
    write_boundary(tmp_path)
    runner = RecordingRunner()
    status = make_status(cutoff=TODAY)
    result = execute_platform_operations(
        FakeRepository(existing_month=True),
        as_of=TODAY,
        project_root=tmp_path,
        include_model1d=True,
        status_provider=lambda repository, as_of, root: status,
        command_runner=runner,
    )
    assert [c for c in runner.calls if c[1] == "run_governed_model"] == []
    assert result["model1d_gate"]["action"] == "skip_existing_month"
    assert result["model1d_execution"] == "skip_existing_month"


def test_failed_component_stops_downstream_execution(tmp_path: Path) -> None:
    write_boundary(tmp_path)
    runner = RecordingRunner(fail_component="1B")
    stale = make_status(
        ready_1a=True,
        ready_1b=False,
        ready_1c=False,
        cutoff=TODAY,
    )
    with pytest.raises(PlatformOperationError, match="Downstream operations were stopped"):
        execute_platform_operations(
            FakeRepository(existing_month=True),
            as_of=TODAY,
            project_root=tmp_path,
            include_model1d=True,
            status_provider=lambda repository, as_of, root: stale,
            command_runner=runner,
        )
    assert any(step == "run_governed_model" and comp == "1B" for _, step, comp in runner.calls)
    assert not any(step == "run_governed_model" and comp == "1C" for _, step, comp in runner.calls)
    assert not any(step == "model1d_monthly_operation" for _, step, _ in runner.calls)


def test_historical_execute_fails_before_commands(tmp_path: Path) -> None:
    write_boundary(tmp_path)
    runner = RecordingRunner()
    historical = date(2020, 1, 1)
    with pytest.raises(PlatformOperationError, match="historical"):
        execute_platform_operations(
            FakeRepository(existing_month=True),
            as_of=historical,
            project_root=tmp_path,
            include_model1d=False,
            status_provider=lambda repository, as_of, root: make_status(cutoff=historical),
            command_runner=runner,
        )
    assert runner.calls == []
