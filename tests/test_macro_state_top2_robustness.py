from __future__ import annotations

import pandas as pd

from macropulse.macro_state.top2_robustness import (
    AuditSettings,
    add_rank_diagnostics,
    bootstrap_table,
    paired_monthly_scores,
    build_monthly_attribution,
    fold_metrics,
    prepare_predictions,
)

FAMILIES = ["expansion", "reflation", "slowdown", "contraction", "stagflation"]


def sample_predictions() -> pd.DataFrame:
    actual = ["expansion", "expansion", "reflation", "slowdown", "slowdown", "contraction", "stagflation", "expansion"]
    rows = []
    for i, family in enumerate(actual):
        date = pd.Timestamp("2024-08-31") + pd.offsets.MonthEnd(i)
        for benchmark in ("source", "rolling_frequency"):
            probs = {item: 0.05 for item in FAMILIES}
            if benchmark == "source":
                if i in {2, 6}:
                    wrong = [item for item in FAMILIES if item != family]
                    probs[wrong[0]] = 0.50
                    probs[wrong[1]] = 0.25
                    probs[family] = 0.10
                else:
                    probs[family] = 0.55
            else:
                probs[actual[max(0, i - 1)]] = 0.60
            probs["expansion"] += 1.0 - sum(probs.values())
            row = {
                "fold_id": f"fold_{1 + i // 4:02d}", "state_date": date,
                "benchmark_id": benchmark, "actual_family": family,
                "growth_score": 1.0 if family in {"expansion", "reflation"} else -1.0,
                "inflation_score": 1.0 if family in {"reflation", "stagflation"} else -1.0,
                "labour_score": -1.0 if family in {"contraction", "stagflation"} else 1.0,
            }
            row.update({f"prob__{key}": value for key, value in probs.items()})
            rows.append(row)
    return pd.DataFrame(rows)


def test_rank_and_miss_attribution() -> None:
    prepared, families, columns = prepare_predictions(sample_predictions())
    ranked = add_rank_diagnostics(prepared, families, columns)
    monthly, taxonomy, signatures = build_monthly_attribution(ranked, families, columns, AuditSettings(bootstrap_repetitions=100))
    assert len(monthly) == 8
    assert monthly.source_top2_hit.dtype == bool
    assert (~monthly.source_top2_hit).any()
    assert not taxonomy.empty
    assert signatures


def test_fold_metrics_and_bootstrap_are_finite() -> None:
    prepared, families, columns = prepare_predictions(sample_predictions())
    ranked = add_rank_diagnostics(prepared, families, columns)
    monthly, _, _ = build_monthly_attribution(ranked, families, columns, AuditSettings(bootstrap_repetitions=100))
    folds = fold_metrics(monthly)
    paired = paired_monthly_scores(monthly)
    boot = bootstrap_table(paired, AuditSettings(bootstrap_repetitions=100, random_seed=7))
    assert len(folds) == 2
    assert set(boot.metric) == {"soft_brier_improvement", "soft_log_loss_improvement"}
    assert boot[["mean", "lower", "upper"]].notna().all().all()



def test_v036_json_schema_and_fold_reconstruction() -> None:
    families = [
        "adverse_supply",
        "benign_expansion",
        "contraction",
        "inflationary_expansion",
        "mixed",
    ]
    dates = pd.date_range("2022-08-31", periods=6, freq="ME")
    rows = []
    for index, date in enumerate(dates):
        actual = families[index % len(families)]
        actual_probs = {family: 0.0 for family in families}
        actual_probs[actual] = 1.0
        for benchmark in ("source", "rolling_frequency"):
            predicted = {family: 0.05 for family in families}
            predicted[actual if benchmark == "source" else families[0]] = 0.80
            total = sum(predicted.values())
            predicted = {key: value / total for key, value in predicted.items()}
            rows.append(
                {
                    "state_date": date,
                    "benchmark_id": benchmark,
                    "actual_family": actual,
                    "actual_probabilities_json": __import__("json").dumps(actual_probs),
                    "predicted_family": max(predicted, key=predicted.get),
                    "predicted_probabilities_json": __import__("json").dumps(predicted),
                    "predicted_top_probability": max(predicted.values()),
                }
            )
    fold_rows = []
    for fold_id, start, end in (
        ("fold_01", dates[0], dates[3]),
        ("fold_02", dates[2], dates[5]),
    ):
        for benchmark in ("source", "rolling_frequency"):
            fold_rows.append(
                {
                    "fold_id": fold_id,
                    "evaluation_start": start,
                    "evaluation_end": end,
                    "benchmark_id": benchmark,
                    "observations": 4,
                }
            )
    prepared, parsed_families, columns = prepare_predictions(
        pd.DataFrame(rows),
        pd.DataFrame(fold_rows),
    )
    assert parsed_families == families
    assert "predicted_top" not in parsed_families
    assert columns["fold"] == "fold_id"
    assert columns["actual_family"] == "actual_family"
    assert len(prepared) == 16
    assert prepared.groupby(["fold_id", "benchmark_id"]).size().eq(4).all()
