from __future__ import annotations

from datetime import date
from typing import Any

from macropulse.data.repository import MacroRepository
from macropulse.labour.live import run_governed_labour_nowcast


def run_labour_nowcast_suite(
    repository: MacroRepository | None = None,
    information_cutoff: date | None = None,
    build_news: bool = True,
) -> dict[str, Any]:
    """Run the governed Model 1C live forecast suite."""
    return run_governed_labour_nowcast(
        repository=repository,
        information_cutoff=information_cutoff,
        build_news=build_news,
    )
