from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Any


PROVENANCE_FIELDS = (
    "model_id", "model_name", "model_version", "forecast_stage", "forecast_date",
    "target_period", "information_set_hash", "created_at", "run_id",
)
FORBIDDEN_REAL_TIME_CLASSES = {"filtered_full_sample_parameters", "smoothed_revised"}


@dataclass(frozen=True)
class AlignmentResult:
    aligned: bool
    diagnostics: tuple[str, ...]
    model1_provenance: dict[str, Any]


def preserve_provenance(row: Mapping[str, Any], fields: Iterable[str] = PROVENANCE_FIELDS) -> dict[str, Any]:
    """Copy only provenance fields actually supplied by the governed source."""
    return {field: row[field] for field in fields if field in row}


def validate_model3_estimate_class(estimate_class: str, *, claim_strict_real_time: bool = False) -> None:
    if claim_strict_real_time and estimate_class in FORBIDDEN_REAL_TIME_CLASSES:
        raise ValueError(f"{estimate_class} may not be labelled strict real-time; 3H owns recursive endpoints.")


def align_current_state(
    model1_row: Mapping[str, Any],
    *,
    target_period: str | None = None,
    forecast_date: Any | None = None,
    information_set_hash: str | None = None,
) -> AlignmentResult:
    diagnostics: list[str] = []
    checks = (
        ("target_period", target_period),
        ("forecast_date", forecast_date),
        ("information_set_hash", information_set_hash),
    )
    for field, expected in checks:
        if expected is None:
            continue
        if field not in model1_row:
            diagnostics.append(f"missing:{field}")
        elif str(model1_row[field]) != str(expected):
            diagnostics.append(f"mismatch:{field}")
    return AlignmentResult(
        aligned=not diagnostics,
        diagnostics=tuple(diagnostics),
        model1_provenance=preserve_provenance(model1_row),
    )
