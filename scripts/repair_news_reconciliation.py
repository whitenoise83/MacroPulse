from __future__ import annotations

import json
from datetime import UTC, datetime
from math import isclose
from typing import Any

from macropulse.data.repository import MacroRepository


TOLERANCE = 1e-10
COMPONENTS = ("Bridge Ridge", "Dynamic Factor Model")


def _mapping_close(left: dict[str, Any], right: dict[str, Any]) -> bool:
    keys = set(left) | set(right)
    for key in keys:
        try:
            left_value = float(left.get(key, 0.0))
            right_value = float(right.get(key, 0.0))
        except (TypeError, ValueError):
            return False
        if not isclose(left_value, right_value, rel_tol=0.0, abs_tol=TOLERANCE):
            return False
    return True


def _weight_change_impact(details: dict[str, Any]) -> float:
    previous_weights = details.get("previous_weights") or {}
    current_weights = details.get("current_weights") or {}
    current_components = details.get("current_components") or {}
    return float(
        sum(
            (
                float(current_weights.get(name, 0.0))
                - float(previous_weights.get(name, 0.0))
            )
            * float(current_components.get(name, 0.0))
            for name in COMPONENTS
        )
    )


def _common_legacy_conditions(row: Any, details: dict[str, Any]) -> bool:
    raw_counts = details.get("raw_change_counts") or {}
    previous_components = details.get("previous_components") or {}
    current_components = details.get("current_components") or {}
    has_false_pair = (
        abs(float(getattr(row, "residual_interaction", 0.0) or 0.0)) > TOLERANCE
        or abs(float(getattr(row, "dfm_refit_impact", 0.0) or 0.0)) > TOLERANCE
    )
    return (
        str(row.status) == "success"
        and has_false_pair
        and not raw_counts
        and int(details.get("dfm_update_count", 0) or 0) == 0
        and int(details.get("dfm_revision_count", 0) or 0) == 0
        and _mapping_close(previous_components, current_components)
    )


def _is_legacy_no_change_artifact(row: Any, details: dict[str, Any]) -> bool:
    previous_weights = details.get("previous_weights") or {}
    current_weights = details.get("current_weights") or {}
    return (
        _common_legacy_conditions(row, details)
        and abs(float(row.total_change or 0.0)) <= TOLERANCE
        and _mapping_close(previous_weights, current_weights)
    )


def _is_legacy_weight_only_artifact(row: Any, details: dict[str, Any]) -> bool:
    previous_weights = details.get("previous_weights") or {}
    current_weights = details.get("current_weights") or {}
    if not _common_legacy_conditions(row, details):
        return False
    if _mapping_close(previous_weights, current_weights):
        return False
    expected = _weight_change_impact(details)
    return isclose(
        float(row.total_change or 0.0),
        expected,
        rel_tol=0.0,
        abs_tol=TOLERANCE,
    )


def main() -> None:
    repository = MacroRepository()
    repository.initialise()
    rows = repository.query_df(
        """
        SELECT decomposition_id, status, total_change, residual_interaction,
               dfm_refit_impact, created_at, details_json
        FROM nowcast_news_runs
        ORDER BY created_at
        """
    )

    repaired_no_change: list[str] = []
    repaired_weight_only: list[str] = []
    repaired_at = datetime.now(UTC).replace(tzinfo=None).isoformat()

    with repository.connect() as con:
        con.execute("BEGIN TRANSACTION")
        try:
            for row in rows.itertuples(index=False):
                try:
                    details = json.loads(row.details_json or "{}")
                except json.JSONDecodeError:
                    continue

                is_no_change = _is_legacy_no_change_artifact(row, details)
                is_weight_only = _is_legacy_weight_only_artifact(row, details)
                if not is_no_change and not is_weight_only:
                    continue

                previous_components = details.get("previous_components") or {}
                current_components = details.get("current_components") or {}
                if is_no_change:
                    decomposition_kind = "no_change"
                    weight_impact = 0.0
                    message = (
                        "No raw observations, component forecasts, or production "
                        "weights changed. Legacy false refit/residual pair repaired."
                    )
                    repaired_no_change.append(str(row.decomposition_id))
                else:
                    decomposition_kind = "weight_only"
                    weight_impact = _weight_change_impact(details)
                    message = (
                        "No raw observations or component forecasts changed. The "
                        "production forecast changed only because the selected model "
                        "or ensemble weights changed. Legacy false refit/residual "
                        "pair repaired."
                    )
                    repaired_weight_only.append(str(row.decomposition_id))

                details.update(
                    {
                        "decomposition_kind": decomposition_kind,
                        "dfm_fixed_parameter_updated_forecast": current_components.get(
                            "Dynamic Factor Model",
                            previous_components.get("Dynamic Factor Model"),
                        ),
                        "reconciliation_error": 0.0,
                        "message": message,
                        "repaired_by": "MacroPulse v0.6.1",
                        "repaired_at": repaired_at,
                    }
                )

                con.execute(
                    """
                    UPDATE nowcast_news_runs
                    SET bridge_data_impact = 0.0,
                        bridge_refit_impact = 0.0,
                        dfm_news_impact = 0.0,
                        dfm_revision_impact = 0.0,
                        dfm_refit_impact = 0.0,
                        weight_change_impact = ?,
                        residual_interaction = 0.0,
                        details_json = ?
                    WHERE decomposition_id = ?
                    """,
                    [weight_impact, json.dumps(details), row.decomposition_id],
                )
                con.execute(
                    "DELETE FROM nowcast_news_contributions WHERE decomposition_id = ?",
                    [row.decomposition_id],
                )
                con.execute(
                    "DELETE FROM nowcast_release_changes WHERE decomposition_id = ?",
                    [row.decomposition_id],
                )
                if is_weight_only and abs(weight_impact) > TOLERANCE:
                    con.execute(
                        """
                        INSERT INTO nowcast_news_contributions (
                            decomposition_id,
                            contribution_type,
                            model_name,
                            series_id,
                            observation_date,
                            previous_value,
                            current_value,
                            news,
                            weight,
                            impact,
                            created_at
                        ) VALUES (?, 'weight_change', 'Production Ensemble',
                                  NULL, NULL, NULL, NULL, NULL, NULL, ?, ?)
                        """,
                        [row.decomposition_id, weight_impact, row.created_at],
                    )
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise

    total = len(repaired_no_change) + len(repaired_weight_only)
    print("News reconciliation repair complete")
    print(f"Repaired records: {total}")
    print(f"  no-change records: {len(repaired_no_change)}")
    for decomposition_id in repaired_no_change:
        print(f"    {decomposition_id}")
    print(f"  weight-only records: {len(repaired_weight_only)}")
    for decomposition_id in repaired_weight_only:
        print(f"    {decomposition_id}")
    if total == 0:
        print("No legacy no-change or weight-only artefacts were found.")


if __name__ == "__main__":
    main()
