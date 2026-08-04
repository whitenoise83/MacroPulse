from __future__ import annotations

from pathlib import Path
import pandas as pd

from macropulse.macro_state.top2_robustness import AuditSettings
from macropulse.macro_state.top2_robustness_service import run_macro_state_top2_robustness_audit

FAMILIES = ["expansion", "reflation", "slowdown", "contraction", "stagflation"]


def write_bundle(root: Path) -> None:
    report = root / "reports" / "macro_state_fixed_horizon_probabilistic"
    report.mkdir(parents=True)
    stem = "model1d_fixed_horizon_test"
    actual = ["expansion", "reflation", "slowdown", "contraction"]
    rows = []
    for i, family in enumerate(actual):
        for benchmark in ("source", "rolling_frequency"):
            probs = {item: 0.05 for item in FAMILIES}
            probs[family if benchmark == "source" else actual[max(0, i - 1)]] = 0.70
            probs["expansion"] += 1.0 - sum(probs.values())
            row = {
                "fold_id": f"fold_{i + 1:02d}",
                "state_date": pd.Timestamp("2024-08-31") + pd.offsets.MonthEnd(i),
                "benchmark_id": benchmark, "actual_family": family,
                "growth_score": 1.0 if family in {"expansion", "reflation"} else -1.0,
                "inflation_score": 1.0 if family in {"reflation", "stagflation"} else -1.0,
                "labour_score": -1.0 if family == "contraction" else 1.0,
            }
            row.update({f"prob__{key}": value for key, value in probs.items()})
            rows.append(row)
    pd.DataFrame(rows).to_csv(report / f"{stem}_benchmark_predictions.csv", index=False)
    pd.DataFrame([{"benchmark_id": "source"}, {"benchmark_id": "rolling_frequency"}]).to_csv(report / f"{stem}_benchmark_summary.csv", index=False)
    pd.DataFrame([
        {
            "fold_id": f"fold_{i + 1:02d}",
            "evaluation_start": pd.Timestamp("2024-08-31") + pd.offsets.MonthEnd(i),
            "evaluation_end": pd.Timestamp("2024-08-31") + pd.offsets.MonthEnd(i),
            "benchmark_id": benchmark,
            "observations": 1,
        }
        for i in range(4)
        for benchmark in ("source", "rolling_frequency")
    ]).to_csv(report / f"{stem}_benchmark_fold_metrics.csv", index=False)
    pd.DataFrame([
        {"check_id": "fixed_horizon_target_locked", "passed": True},
        {"check_id": "latest_revised_substitution_prohibited", "passed": True},
        {"check_id": "benchmark_availability_no_lookahead", "passed": True},
        {"check_id": "prospective_shadow_isolation", "passed": True},
    ]).to_csv(report / f"{stem}_governance_flags.csv", index=False)
    pd.DataFrame([{"prospective_shadow_start": "2026-04-30", "status": "preserved"}]).to_csv(report / f"{stem}_prospective_shadow.csv", index=False)


def test_pipeline_writes_report_set(tmp_path: Path) -> None:
    write_bundle(tmp_path)
    result = run_macro_state_top2_robustness_audit(tmp_path, AuditSettings(bootstrap_repetitions=100, random_seed=3))
    assert result["model_version"] == "0.3.7"
    assert result["promotion_approved"] is False
    assert result["architecture_pass"] is True
    assert Path(result["report_path"]).exists()
    for path in result["output_paths"].values():
        assert Path(path).exists()
