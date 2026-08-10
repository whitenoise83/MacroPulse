from __future__ import annotations

from datetime import date
import pandas as pd
from macropulse.evaluation.ledger import (
    OUTCOME_DEFINITION, OUTCOME_VINTAGE, TargetSpec,
    resolve_first_release_outcome,
)

class SnapshotMissingRepository:
    def query_df(self, query: str, parameters=None):
        if "FROM observations" not in query:
            raise AssertionError(f"Unexpected query: {query}")
        return pd.DataFrame([{
            "series_id": "CPIAUCSL",
            "observation_date": date(2026, 7, 1),
            "realtime_start": date(2026, 8, 12),
            "realtime_end": date(9999, 12, 31),
            "value": 100.0, "vintage_type": "initial",
            "retrieved_at": "2026-08-12T12:00:00", "source": "fred",
        }])
    def historical_snapshot(self, as_of_date, series_ids):
        assert as_of_date == date(2026, 8, 12)
        assert series_ids == ["CPIAUCSL"]
        return pd.DataFrame()

def target() -> TargetSpec:
    return TargetSpec(
        component="1B", series_id="CPIAUCSL", name="Headline CPI",
        frequency="M", transform="annualised_mom_log",
        start_date="2000-01-01",
    )

def test_first_release_contract_identity_is_frozen() -> None:
    assert OUTCOME_VINTAGE == "first_release"
    assert OUTCOME_DEFINITION == "initial_release_transformed_target"

def test_known_release_without_exact_snapshot_remains_unresolved() -> None:
    result = resolve_first_release_outcome(
        SnapshotMissingRepository(), target=target(), target_period="2026-07",
        as_of=date(2026, 8, 12),
    )
    assert result.status == "unresolved_release_snapshot_not_cached"
    assert result.release_date == date(2026, 8, 12)
    assert result.value is None
    assert result.evidence_source == "observations.initial_release_date"
    assert "refuses to substitute" in result.detail.lower()
