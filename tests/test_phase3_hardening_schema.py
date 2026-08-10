from __future__ import annotations

from macropulse.evaluation.decision import DECISION_INTELLIGENCE_SCHEMA_VERSION
from macropulse.evaluation.ledger import (
    EVALUATION_COLUMNS,
    OUTCOME_DEFINITION,
    OUTCOME_VINTAGE,
    SIGNED_ERROR_CONVENTION,
)
from macropulse.evaluation.performance import PERFORMANCE_SCHEMA_VERSION
from macropulse.evaluation.revisions import REVISION_SCHEMA_VERSION

EXPECTED_EVALUATION_COLUMNS = [
    "evaluation_id", "forecast_identity", "evaluation_as_of", "component",
    "model_id", "model_version", "run_id", "information_cutoff", "data_as_of",
    "target_series", "target_name", "target_period", "forecast_stage",
    "forecast_model_name", "forecast_value", "lower_80", "upper_80",
    "interval_width", "estimated_release_date", "outcome_definition",
    "outcome_vintage", "outcome_evidence_source", "outcome_release_date",
    "outcome_value", "evaluation_status", "status_detail",
    "no_look_ahead_pass", "lead_days", "signed_error", "absolute_error",
    "squared_error", "interval_covered",
]

def test_phase3_evaluation_schema_is_explicit_and_stable() -> None:
    assert EVALUATION_COLUMNS == EXPECTED_EVALUATION_COLUMNS
    assert OUTCOME_VINTAGE == "first_release"
    assert OUTCOME_DEFINITION == "initial_release_transformed_target"
    assert SIGNED_ERROR_CONVENTION == "forecast_minus_outcome"

def test_phase3_public_semantic_schemas_are_v1() -> None:
    assert PERFORMANCE_SCHEMA_VERSION == "1.0.0"
    assert REVISION_SCHEMA_VERSION == "1.0.0"
    assert DECISION_INTELLIGENCE_SCHEMA_VERSION == "1.0.0"
