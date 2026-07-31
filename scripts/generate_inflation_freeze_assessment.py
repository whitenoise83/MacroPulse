from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.inflation.policy import SELECTED_INTERVAL_METHOD, STABLE_POLICY
from macropulse.inflation.versioning import current_inflation_model_identity
from macropulse.settings import settings

EXPECTED_CANDIDATE_PASSES = 28
EXPECTED_OPERATIONAL_PASSES = 20
EXPECTED_TARGETS = 4
MAXIMUM_NEWS_RESIDUAL = 1e-8


def _safe_json(value: Any) -> dict[str, Any]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return {}
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _check(
    gate_name: str,
    check_name: str,
    passed: bool,
    observed_value: Any,
    threshold: str,
    details: Any | None = None,
) -> dict[str, Any]:
    return {
        "gate_name": gate_name,
        "check_name": check_name,
        "status": "pass" if passed else "fail",
        "observed_value": str(observed_value),
        "threshold": threshold,
        "details_json": json.dumps(details or {}, sort_keys=True, default=str),
    }


def _latest_validation(
    validations: pd.DataFrame,
    validation_type: str,
    requested_id: str | None,
) -> tuple[pd.Series | None, dict[str, Any]]:
    if validations.empty:
        return None, {}
    work = validations.copy()
    work["_summary"] = work["summary_json"].map(_safe_json)
    work["_type"] = work["_summary"].map(lambda item: item.get("validation_type"))
    if requested_id:
        work = work.loc[work["validation_id"].astype(str) == requested_id]
    else:
        work = work.loc[work["_type"] == validation_type]
        if "created_at" in work.columns:
            work = work.sort_values("created_at", ascending=False)
    if work.empty:
        return None, {}
    row = work.iloc[0]
    return row, dict(row["_summary"])


def _report_exists(path_value: Any) -> bool:
    if path_value is None:
        return False
    text = str(path_value).strip()
    return bool(text) and Path(text).is_file()


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "No checks."
    columns = ["gate_name", "check_name", "status", "observed_value", "threshold"]
    lines = [
        "| Gate | Check | Status | Observed | Threshold |",
        "|---|---|---:|---:|---:|",
    ]
    for row in frame[columns].itertuples(index=False):
        values = [str(value).replace("|", "\\|") for value in row]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def assess_freeze_readiness(
    repository: MacroRepository,
    candidate_validation_id: str | None = None,
    operational_validation_id: str | None = None,
) -> dict[str, Any]:
    validations = repository.query_df(
        "SELECT * FROM inflation_validation_runs ORDER BY created_at DESC"
    )
    candidate, candidate_summary = _latest_validation(
        validations, "candidate_policy", candidate_validation_id
    )
    operational, operational_summary = _latest_validation(
        validations, "governed_live_operational", operational_validation_id
    )

    checks: list[dict[str, Any]] = []

    candidate_exists = candidate is not None
    checks.append(
        _check(
            "Candidate evidence",
            "Passing Model 1B candidate validation is available",
            candidate_exists
            and str(candidate["status"]) == "pass"
            and int(candidate["passed_checks"]) == EXPECTED_CANDIDATE_PASSES
            and int(candidate["failed_checks"]) == 0
            and int(candidate["warnings"]) == 0,
            (
                f"{candidate['status']} / {int(candidate['passed_checks'])} passed / "
                f"{int(candidate['failed_checks'])} failed / {int(candidate['warnings'])} warnings"
                if candidate_exists
                else "missing"
            ),
            f"pass / {EXPECTED_CANDIDATE_PASSES} passed / 0 failed / 0 warnings",
        )
    )
    candidate_policy_ok = (
        candidate_summary.get("point_policy") == "stable_candidate"
        and candidate_summary.get("shadow_policy") == "adaptive_shadow_only"
        and candidate_summary.get("interval_method") == SELECTED_INTERVAL_METHOD
    )
    checks.append(
        _check(
            "Candidate evidence",
            "Candidate validation records the approved point, shadow, and interval policies",
            candidate_exists and candidate_policy_ok,
            {
                "point_policy": candidate_summary.get("point_policy"),
                "shadow_policy": candidate_summary.get("shadow_policy"),
                "interval_method": candidate_summary.get("interval_method"),
            },
            "stable candidate / adaptive shadow only / exp_weighted_q80",
        )
    )

    operational_exists = operational is not None
    checks.append(
        _check(
            "Live governance",
            "Passing governed-live operational validation is available",
            operational_exists
            and str(operational["status"]) == "pass"
            and int(operational["passed_checks"]) == EXPECTED_OPERATIONAL_PASSES
            and int(operational["failed_checks"]) == 0
            and int(operational["warnings"]) == 0,
            (
                f"{operational['status']} / {int(operational['passed_checks'])} passed / "
                f"{int(operational['failed_checks'])} failed / {int(operational['warnings'])} warnings"
                if operational_exists
                else "missing"
            ),
            f"pass / {EXPECTED_OPERATIONAL_PASSES} passed / 0 failed / 0 warnings",
        )
    )

    live_run_id = str(operational_summary.get("live_run_id") or "")
    live_runs = repository.query_df(
        "SELECT * FROM inflation_live_runs WHERE run_id = ?", [live_run_id]
    ) if live_run_id else pd.DataFrame()
    live_exists = not live_runs.empty
    live = live_runs.iloc[0] if live_exists else None
    checks.append(
        _check(
            "Live governance",
            "Operational validation resolves to a successful persisted live run",
            live_exists and str(live["status"]) == "success",
            str(live["status"]) if live_exists else "missing",
            "success",
            {"live_run_id": live_run_id},
        )
    )

    candidate_id = str(candidate["validation_id"]) if candidate_exists else ""
    linked_candidate = str(live["candidate_validation_id"]) if live_exists else ""
    checks.append(
        _check(
            "Governance linkage",
            "Governed live run is linked to the passing candidate validation",
            bool(candidate_id) and linked_candidate == candidate_id,
            linked_candidate or "missing",
            candidate_id or "passing candidate validation ID",
        )
    )

    forecasts = repository.query_df(
        "SELECT * FROM inflation_live_forecasts WHERE run_id = ? ORDER BY target_series",
        [live_run_id],
    ) if live_run_id else pd.DataFrame()
    target_count = int(forecasts["target_series"].nunique()) if not forecasts.empty else 0
    duplicate_count = int(forecasts.duplicated(["target_series"]).sum()) if not forecasts.empty else 0
    checks.append(
        _check(
            "Live governance",
            "Governed run contains exactly one headline for each inflation target",
            target_count == EXPECTED_TARGETS and duplicate_count == 0,
            f"{target_count} targets; {duplicate_count} duplicates",
            f"{EXPECTED_TARGETS} targets; 0 duplicates",
        )
    )

    policy_violations: list[dict[str, str]] = []
    for row in forecasts.itertuples(index=False):
        expected = STABLE_POLICY.get(str(row.target_series), {}).get(str(row.forecast_stage))
        if expected != str(row.stable_model_name):
            policy_violations.append(
                {
                    "target_series": str(row.target_series),
                    "forecast_stage": str(row.forecast_stage),
                    "observed": str(row.stable_model_name),
                    "expected": str(expected),
                }
            )
    checks.append(
        _check(
            "Policy governance",
            "Live headlines follow the validated stable target-stage map",
            target_count == EXPECTED_TARGETS and not policy_violations,
            len(policy_violations),
            "0 violations",
            policy_violations,
        )
    )

    interval_violations = 0
    shadow_missing = 0
    if not forecasts.empty:
        interval_violations = int(
            (forecasts["interval_method"].astype(str) != SELECTED_INTERVAL_METHOD).sum()
        )
        shadow_missing = int(
            (
                forecasts["shadow_model_name"].isna()
                | forecasts["shadow_point_forecast"].isna()
            ).sum()
        )
    checks.append(
        _check(
            "Uncertainty calibration",
            "All governed intervals use the validated prior-only method",
            target_count == EXPECTED_TARGETS and interval_violations == 0,
            interval_violations,
            f"0 methods other than {SELECTED_INTERVAL_METHOD}",
        )
    )
    checks.append(
        _check(
            "Challenger governance",
            "Adaptive forecasts remain separate shadow outputs",
            target_count == EXPECTED_TARGETS and shadow_missing == 0,
            shadow_missing,
            "0 missing shadow outputs",
        )
    )

    news = repository.query_df(
        "SELECT * FROM inflation_news_runs WHERE current_run_id = ? ORDER BY target_series",
        [live_run_id],
    ) if live_run_id else pd.DataFrame()
    successful_news = news.loc[news["status"].astype(str) == "success"].copy() if not news.empty else pd.DataFrame()
    news_targets = int(successful_news["target_series"].nunique()) if not successful_news.empty else 0
    residual = float(
        pd.to_numeric(successful_news["residual_interaction"], errors="coerce").abs().max()
    ) if not successful_news.empty else float("inf")
    previous_ids = sorted(
        set(successful_news["previous_run_id"].dropna().astype(str))
    ) if not successful_news.empty else []
    checks.append(
        _check(
            "News decomposition",
            "Comparable news decomposition exists for all four governed headlines",
            news_targets == EXPECTED_TARGETS and len(previous_ids) >= 1,
            f"{news_targets} targets; {len(previous_ids)} previous run IDs",
            f"{EXPECTED_TARGETS} targets and at least 1 previous run",
            {"previous_run_ids": previous_ids},
        )
    )
    checks.append(
        _check(
            "News decomposition",
            "Inflation news decomposition reconciles arithmetically",
            np.isfinite(residual) and residual <= MAXIMUM_NEWS_RESIDUAL,
            residual,
            f"<= {MAXIMUM_NEWS_RESIDUAL:g}",
        )
    )

    hash_fields = [
        "config_hash",
        "code_hash",
        "information_set_hash",
        "model_state_hash",
        "governance_signature",
    ]
    invalid_hashes = []
    if live_exists:
        invalid_hashes = [
            field
            for field in hash_fields
            if not isinstance(live.get(field), str) or len(str(live.get(field))) != 64
        ]
    else:
        invalid_hashes = hash_fields
    checks.append(
        _check(
            "Reproducibility",
            "Governed live run contains complete SHA-256 provenance controls",
            not invalid_hashes,
            len(invalid_hashes),
            "0 invalid hashes",
            invalid_hashes,
        )
    )

    candidate_report_ok = candidate_exists and _report_exists(candidate["report_path"])
    operational_report_ok = operational_exists and _report_exists(operational["report_path"])
    checks.append(
        _check(
            "Documentation",
            "Candidate and operational validation reports are preserved",
            bool(candidate_report_ok and operational_report_ok),
            {
                "candidate_report": bool(candidate_report_ok),
                "operational_report": bool(operational_report_ok),
            },
            "both reports exist",
        )
    )

    model_card = settings.project_root / "docs" / "model1b_model_card_draft.md"
    checks.append(
        _check(
            "Documentation",
            "Model 1B model card is present",
            model_card.is_file(),
            str(model_card),
            "file exists",
        )
    )

    checks_frame = pd.DataFrame(checks)
    failures = int((checks_frame["status"] == "fail").sum())
    warnings = int((checks_frame["status"] == "warning").sum())
    passed = int((checks_frame["status"] == "pass").sum())
    readiness = "ready_for_model_owner_signoff" if failures == 0 and warnings == 0 else "not_ready"

    return {
        "readiness": readiness,
        "checks": checks_frame,
        "passed": passed,
        "failed": failures,
        "warnings": warnings,
        "candidate_validation_id": candidate_id,
        "operational_validation_id": str(operational["validation_id"]) if operational_exists else "",
        "live_run_id": live_run_id,
        "backtest_id": str(live["backtest_id"]) if live_exists else "",
        "live_model_version": str(live["model_version"]) if live_exists else "",
    }


def write_report(assessment_id: str, result: dict[str, Any]) -> Path:
    report_dir = settings.project_root / "reports" / "inflation_freeze"
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"model1b_freeze_assessment_{timestamp}.md"
    lines = [
        "# MacroPulse Model 1B Freeze Assessment",
        "",
        f"- Assessment ID: `{assessment_id}`",
        f"- Readiness: **{result['readiness']}**",
        f"- Candidate validation ID: `{result['candidate_validation_id']}`",
        f"- Operational validation ID: `{result['operational_validation_id']}`",
        f"- Governed live run ID: `{result['live_run_id']}`",
        f"- Vintage backtest ID: `{result['backtest_id']}`",
        f"- Governed live model version: `{result['live_model_version']}`",
        f"- Stable policy decisions: `{sum(len(value) for value in STABLE_POLICY.values())}`",
        f"- Interval method: `{SELECTED_INTERVAL_METHOD}`",
        "- Adaptive selector: `shadow challenger only`",
        "",
        "## Freeze checks",
        "",
        _markdown_table(result["checks"]),
        "",
        "## Conclusion",
        "",
    ]
    if result["readiness"] == "ready_for_model_owner_signoff":
        lines.append(
            "The Model 1B candidate has passing pseudo-real-time candidate evidence, "
            "a passing governed live operational validation, complete provenance hashes, "
            "a comparable four-target news decomposition, and preserved validation reports. "
            "It is ready for explicit model-owner review and signoff. This assessment does "
            "not itself promote the model to production."
        )
    else:
        lines.append(
            "The Model 1B candidate is not ready for owner signoff. Resolve the failed "
            "freeze checks and regenerate this assessment."
        )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Assess Model 1B governed candidate readiness for model-owner signoff."
    )
    parser.add_argument("--candidate-validation-id")
    parser.add_argument("--operational-validation-id")
    args = parser.parse_args()

    repository = MacroRepository()
    repository.initialise()
    result = assess_freeze_readiness(
        repository,
        candidate_validation_id=args.candidate_validation_id,
        operational_validation_id=args.operational_validation_id,
    )
    assessment_id = str(uuid.uuid4())
    report_path = write_report(assessment_id, result)

    created_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
    persisted_checks = result["checks"].copy()
    persisted_checks.insert(0, "validation_id", assessment_id)
    persisted_checks["created_at"] = created_at
    identity = current_inflation_model_identity()
    run_record = pd.DataFrame(
        [
            {
                "validation_id": assessment_id,
                "model_id": identity.model_id,
                "model_version": identity.model_version,
                "backtest_id": result["backtest_id"] or None,
                "created_at": created_at,
                "status": "pass" if result["readiness"] == "ready_for_model_owner_signoff" else "fail",
                "passed_checks": result["passed"],
                "failed_checks": result["failed"],
                "warnings": result["warnings"],
                "report_path": str(report_path),
                "summary_json": json.dumps(
                    {
                        "validation_type": "freeze_assessment",
                        "readiness": result["readiness"],
                        "candidate_validation_id": result["candidate_validation_id"],
                        "operational_validation_id": result["operational_validation_id"],
                        "live_run_id": result["live_run_id"],
                        "passed": result["passed"],
                        "failed": result["failed"],
                        "warnings": result["warnings"],
                    },
                    sort_keys=True,
                ),
                "notes": "Model 1B governed-candidate freeze assessment; not production approval.",
            }
        ]
    )
    repository.save_inflation_validation_outputs(run_record, persisted_checks)

    print("Model 1B freeze assessment complete")
    print(f"Assessment ID: {assessment_id}")
    print(f"Readiness: {result['readiness']}")
    print(f"Candidate validation ID: {result['candidate_validation_id']}")
    print(f"Operational validation ID: {result['operational_validation_id']}")
    print(f"Governed live run ID: {result['live_run_id']}")
    print(f"Passed: {result['passed']}")
    print(f"Failed: {result['failed']}")
    print(f"Warnings: {result['warnings']}")
    print(f"Report: {report_path}")
    if result["failed"]:
        print("\nChecks requiring attention")
        print(
            result["checks"].loc[result["checks"]["status"] != "pass"].to_string(index=False)
        )


if __name__ == "__main__":
    main()
