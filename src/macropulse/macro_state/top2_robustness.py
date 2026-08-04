from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any
import json
import math
import re

import numpy as np
import pandas as pd

SOURCE_ID = "source"
COMPARATOR_ID = "rolling_frequency"
DATE_NAMES = ("state_date", "forecast_date", "target_date", "month", "date")
FOLD_NAMES = ("fold_id", "fold", "rolling_fold")
ACTUAL_NAMES = (
    "actual_family",
    "realised_family",
    "realized_family",
    "target_family",
    "family_state",
    "five_family",
)
BENCHMARK_NAMES = ("benchmark_id", "benchmark", "model_id", "model_name")
DIMENSIONS = ("growth_score", "inflation_score", "labour_score")
PREDICTED_JSON_NAMES = (
    "predicted_probabilities_json",
    "probabilities_json",
    "family_probabilities_json",
    "probabilities",
)
ACTUAL_JSON_NAMES = (
    "actual_probabilities_json",
    "target_probabilities_json",
    "soft_target_probabilities_json",
)


@dataclass(frozen=True)
class AuditSettings:
    primary_comparator: str = COMPARATOR_ID
    near_miss_gap: float = 0.05
    low_confidence_max_probability: float = 0.40
    confidently_wrong_probability: float = 0.60
    bootstrap_repetitions: int = 2000
    bootstrap_block_months: int = 3
    bootstrap_confidence: float = 0.90
    random_seed: int = 13037
    reconciliation_tolerance: float = 1e-6
    prospective_shadow_start: str = "2026-04-30"


@dataclass(frozen=True)
class EvidenceBundle:
    report_dir: Path
    stem: str
    predictions: Path
    summary: Path
    fold_metrics: Path
    governance: Path | None
    prospective_shadow: Path | None


def _first(frame: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    lookup = {str(column).lower(): str(column) for column in frame.columns}
    return next(
        (lookup[name.lower()] for name in names if name.lower() in lookup),
        None,
    )


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_latest_bundle(project_root: Path) -> EvidenceBundle:
    report_dir = (
        Path(project_root)
        / "reports"
        / "macro_state_fixed_horizon_probabilistic"
    )
    candidates = sorted(
        report_dir.glob("model1d_fixed_horizon_*_benchmark_predictions.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(
            f"No v0.3.6 benchmark predictions found under {report_dir}"
        )

    predictions = candidates[0]
    stem = predictions.name.removesuffix("_benchmark_predictions.csv")
    summary = report_dir / f"{stem}_benchmark_summary.csv"
    fold_metrics = report_dir / f"{stem}_benchmark_fold_metrics.csv"
    if not summary.exists():
        raise FileNotFoundError(f"Missing v0.3.6 benchmark summary: {summary}")
    if not fold_metrics.exists():
        raise FileNotFoundError(
            f"Missing v0.3.6 benchmark fold metrics: {fold_metrics}"
        )

    governance = report_dir / f"{stem}_governance_flags.csv"
    shadow = report_dir / f"{stem}_prospective_shadow.csv"
    return EvidenceBundle(
        report_dir=report_dir,
        stem=stem,
        predictions=predictions,
        summary=summary,
        fold_metrics=fold_metrics,
        governance=governance if governance.exists() else None,
        prospective_shadow=shadow if shadow.exists() else None,
    )


def _json_map(value: Any) -> dict[str, float]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return {}
    if isinstance(value, dict):
        raw = value
    else:
        try:
            raw = json.loads(str(value))
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
    if not isinstance(raw, dict):
        return {}

    output: dict[str, float] = {}
    for key, item in raw.items():
        try:
            output[str(key)] = float(item)
        except (TypeError, ValueError):
            continue
    return output


def _prob_family(column: str) -> str | None:
    lower = column.lower()
    excluded = {
        "actual_probability",
        "mean_actual_probability",
        "probability",
        "predicted_top_probability",
        "top_probability",
        "top1_probability",
        "top2_probability",
        "top3_probability",
        "max_probability",
    }
    if lower in excluded or lower.endswith("_top_probability"):
        return None
    patterns = (
        r"^(?:prob|p|probability|family_probability)__(.+)$",
        r"^(?:prob|p|probability|family_probability)_(.+)$",
        r"^(.+)__(?:prob|probability)$",
        r"^(.+)_(?:prob|probability)$",
    )
    for pattern in patterns:
        match = re.match(pattern, lower)
        if match:
            return match.group(1).strip("_")
    return None


def _target_family(column: str) -> str | None:
    lower = column.lower()
    patterns = (
        r"^(?:target_prob|target_probability|soft_target|actual_prob)__(.+)$",
        r"^(?:target_prob|target_probability|soft_target|actual_prob)_(.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, lower)
        if match:
            return match.group(1).strip("_")
    return None


def _parse_prediction_probabilities(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str]]:
    """Parse probability vectors, prioritising the canonical v0.3.6 JSON."""
    json_column = _first(frame, PREDICTED_JSON_NAMES)
    if json_column:
        parsed = frame[json_column].map(_json_map)
        families = sorted({family for item in parsed for family in item})
        if not families:
            raise ValueError(
                f"The probability JSON column {json_column!r} contains no families."
            )
        output = frame.copy()
        for family in families:
            output[f"prob__{family}"] = parsed.map(
                lambda item, family=family: item.get(family, 0.0)
            )
        return output, families

    mapping = {
        str(column): _prob_family(str(column))
        for column in frame.columns
    }
    mapping = {
        column: family
        for column, family in mapping.items()
        if family is not None
    }
    if mapping:
        output = frame.rename(
            columns={
                column: f"prob__{family}"
                for column, family in mapping.items()
            }
        )
        return output, sorted(set(mapping.values()))

    family_column = _first(
        frame,
        ("family", "state_family", "predicted_family"),
    )
    value_column = _first(
        frame,
        ("probability", "predicted_probability"),
    )
    benchmark = _first(frame, BENCHMARK_NAMES)
    date = _first(frame, DATE_NAMES)
    fold = _first(frame, FOLD_NAMES)
    actual = _first(frame, ACTUAL_NAMES)
    if not all((family_column, value_column, benchmark, date, actual)):
        raise ValueError(
            "Cannot identify the prediction probability layout. "
            f"Columns: {list(frame.columns)}"
        )

    index = [benchmark, date, actual] + ([fold] if fold else [])
    carry = [column for column in DIMENSIONS if column in frame.columns]
    base = frame[index + carry].drop_duplicates(index)
    pivot = frame.pivot_table(
        index=index,
        columns=family_column,
        values=value_column,
        aggfunc="first",
    ).reset_index()
    families = [str(column) for column in pivot.columns if str(column) not in index]
    pivot = pivot.rename(
        columns={family: f"prob__{family}" for family in families}
    )
    return base.merge(pivot, on=index, how="inner"), sorted(families)


def _parse_actual_probabilities(
    frame: pd.DataFrame,
    families: list[str],
    actual_column: str,
) -> pd.DataFrame:
    output = frame.copy()
    json_column = _first(output, ACTUAL_JSON_NAMES)
    if json_column:
        parsed = output[json_column].map(_json_map)
        for family in families:
            output[f"target__{family}"] = parsed.map(
                lambda item, family=family: item.get(family, 0.0)
            )
        return output

    target_map = {
        str(column): _target_family(str(column))
        for column in output.columns
    }
    target_map = {
        column: family
        for column, family in target_map.items()
        if family is not None
    }
    if target_map:
        for family in families:
            source = next(
                (
                    column
                    for column, mapped_family in target_map.items()
                    if mapped_family == family
                ),
                None,
            )
            output[f"target__{family}"] = (
                pd.to_numeric(output[source], errors="coerce").fillna(0.0)
                if source
                else 0.0
            )
        return output

    for family in families:
        output[f"target__{family}"] = (
            output[actual_column].astype(str) == family
        ).astype(float)
    return output


def _fold_windows(fold_metric_rows: pd.DataFrame) -> pd.DataFrame:
    required = {"fold_id", "evaluation_start", "evaluation_end"}
    missing = required.difference(fold_metric_rows.columns)
    if missing:
        raise ValueError(
            "The v0.3.6 fold-metrics file lacks: " + ", ".join(sorted(missing))
        )

    windows = fold_metric_rows[
        ["fold_id", "evaluation_start", "evaluation_end"]
    ].drop_duplicates()
    windows["evaluation_start"] = pd.to_datetime(
        windows["evaluation_start"], errors="coerce"
    )
    windows["evaluation_end"] = pd.to_datetime(
        windows["evaluation_end"], errors="coerce"
    )
    if windows[["evaluation_start", "evaluation_end"]].isna().any().any():
        raise ValueError("Invalid dates in the v0.3.6 fold-metrics file.")
    if windows["fold_id"].duplicated().any():
        raise ValueError("A fold_id maps to more than one evaluation window.")
    return windows.sort_values("fold_id").reset_index(drop=True)


def expand_predictions_to_folds(
    frame: pd.DataFrame,
    fold_metric_rows: pd.DataFrame,
    columns: dict[str, str],
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Reconstruct the seven overlapping v0.3.6 fold-month samples."""
    existing_fold = _first(frame, FOLD_NAMES)
    if existing_fold and existing_fold != "_fold_id":
        updated = dict(columns)
        updated["fold"] = existing_fold
        return frame, updated

    windows = _fold_windows(fold_metric_rows)
    date_column = columns["date"]
    left = frame.copy()
    left["_join_key"] = 1
    right = windows.copy()
    right["_join_key"] = 1
    expanded = left.merge(right, on="_join_key", how="inner").drop(
        columns="_join_key"
    )
    expanded = expanded.loc[
        expanded[date_column].between(
            expanded["evaluation_start"],
            expanded["evaluation_end"],
            inclusive="both",
        )
    ].copy()

    benchmark_column = columns["benchmark"]
    expected_rows = fold_metric_rows[
        ["fold_id", "benchmark_id", "observations"]
    ].copy()
    expected_rows["observations"] = pd.to_numeric(
        expected_rows["observations"], errors="raise"
    ).astype(int)
    actual_rows = (
        expanded.groupby(["fold_id", benchmark_column])
        .size()
        .rename("actual_observations")
        .reset_index()
        .rename(columns={benchmark_column: "benchmark_id"})
    )
    validation = expected_rows.merge(
        actual_rows,
        on=["fold_id", "benchmark_id"],
        how="left",
    )
    validation["actual_observations"] = validation[
        "actual_observations"
    ].fillna(0).astype(int)
    bad = validation.loc[
        validation["observations"] != validation["actual_observations"]
    ]
    if not bad.empty:
        raise ValueError(
            "Fold reconstruction does not match v0.3.6 observations:\n"
            + bad.to_string(index=False)
        )

    updated = dict(columns)
    updated["fold"] = "fold_id"
    return expanded, updated


def prepare_predictions(
    raw: pd.DataFrame,
    fold_metric_rows: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, list[str], dict[str, str]]:
    frame, families = _parse_prediction_probabilities(raw.copy())

    benchmark = _first(frame, BENCHMARK_NAMES)
    date = _first(frame, DATE_NAMES)
    actual = _first(frame, ACTUAL_NAMES)
    if not benchmark or not date or not actual:
        raise ValueError(
            "Required benchmark/date/actual-family fields are missing. "
            f"Columns: {list(frame.columns)}"
        )

    frame[date] = pd.to_datetime(frame[date], errors="coerce")
    if frame[date].isna().any():
        raise ValueError("Invalid state dates in benchmark predictions.")

    probability_columns = [f"prob__{family}" for family in families]
    frame[probability_columns] = (
        frame[probability_columns]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0.0)
        .clip(lower=0.0)
    )
    totals = frame[probability_columns].sum(axis=1)
    if (totals <= 0).any():
        raise ValueError("A prediction row has zero probability mass.")
    frame[probability_columns] = frame[probability_columns].div(totals, axis=0)

    frame = _parse_actual_probabilities(frame, families, actual)
    target_columns = [f"target__{family}" for family in families]
    frame[target_columns] = (
        frame[target_columns]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0.0)
        .clip(lower=0.0)
    )
    target_totals = frame[target_columns].sum(axis=1)
    if (target_totals <= 0).any():
        raise ValueError("An actual-probability row has zero probability mass.")
    frame[target_columns] = frame[target_columns].div(target_totals, axis=0)

    fold = _first(frame, FOLD_NAMES)
    columns = {
        "benchmark": benchmark,
        "date": date,
        "fold": fold or "_fold_id",
        "actual": actual,
        "actual_family": actual,
    }
    if fold_metric_rows is not None:
        frame, columns = expand_predictions_to_folds(
            frame,
            fold_metric_rows,
            columns,
        )
    elif fold is None:
        frame["_fold_id"] = "fold_all"

    return frame, families, columns


def add_rank_diagnostics(
    frame: pd.DataFrame,
    families: list[str],
    columns: dict[str, str],
) -> pd.DataFrame:
    output = frame.copy()
    records: list[dict[str, Any]] = []
    for _, row in output.iterrows():
        pairs = sorted(
            (
                (family, float(row[f"prob__{family}"]))
                for family in families
            ),
            key=lambda item: (-item[1], item[0]),
        )
        actual = str(row[columns["actual"]])
        ranks = {
            family: index + 1
            for index, (family, _) in enumerate(pairs)
        }
        probabilities = dict(pairs)
        vector = np.array(
            [probabilities[family] for family in families],
            dtype=float,
        )
        entropy = float(
            -(vector * np.log(np.clip(vector, 1e-15, 1.0))).sum()
        )
        padded = pairs + [("", np.nan)] * max(0, 3 - len(pairs))
        rank = int(ranks.get(actual, len(families) + 1))
        records.append(
            {
                "predicted_family": padded[0][0],
                "actual_family_rank": rank,
                "actual_family_probability": float(
                    probabilities.get(actual, 0.0)
                ),
                "top1_probability": float(padded[0][1]),
                "top2_probability": float(padded[1][1]),
                "top3_probability": float(padded[2][1]),
                "second_third_probability_gap": float(
                    padded[1][1] - padded[2][1]
                ),
                "entropy": entropy,
                "normalised_entropy": (
                    entropy / math.log(len(families))
                    if len(families) > 1
                    else 0.0
                ),
                "top1_hit": rank == 1,
                "top2_hit": rank <= 2,
                "top3_hit": rank <= 3,
            }
        )
    diagnostics = pd.DataFrame(records)

    # The canonical v0.3.6 file already contains a convenience
    # ``predicted_family`` column.  The diagnostic recomputes that field from
    # ``predicted_probabilities_json``.  Keeping both creates duplicate column
    # names; pandas then returns a DataFrame rather than a Series when the
    # column is selected, which corrupts downstream classification metrics.
    #
    # The JSON probability vector is the governed source of truth, so replace
    # any pre-existing diagnostic columns with the recomputed values.
    overlapping = [
        column for column in diagnostics.columns if column in output.columns
    ]
    if overlapping:
        output = output.drop(columns=overlapping)

    combined = pd.concat(
        [output.reset_index(drop=True), diagnostics.reset_index(drop=True)],
        axis=1,
    )
    if combined.columns.duplicated().any():
        duplicates = sorted(
            set(combined.columns[combined.columns.duplicated()].tolist())
        )
        raise ValueError(
            "Duplicate columns remain after rank diagnostics: "
            + ", ".join(duplicates)
        )
    return combined


def _score(frame: pd.DataFrame, families: list[str]) -> pd.DataFrame:
    output = frame.copy()
    probabilities = output[
        [f"prob__{family}" for family in families]
    ].to_numpy(float)
    targets = output[
        [f"target__{family}" for family in families]
    ].to_numpy(float)
    output["soft_brier"] = ((probabilities - targets) ** 2).sum(axis=1)
    # Match the governed v0.3.6 scoring implementation exactly.
    # This is important for persistence-style benchmarks that can assign
    # genuine zero probability to the realised family.
    output["soft_log_loss"] = -(
        targets * np.log(np.maximum(probabilities, 1e-12))
    ).sum(axis=1)
    return output


def _sign(value: Any) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    if not np.isfinite(number) or abs(number) < 1e-12:
        return 0
    return 1 if number > 0 else -1


def _signatures(
    frame: pd.DataFrame,
    actual_column: str,
) -> dict[str, dict[str, int]]:
    available = [column for column in DIMENSIONS if column in frame.columns]
    result: dict[str, dict[str, int]] = {}
    for family, group in frame.groupby(actual_column):
        result[str(family)] = {}
        for column in available:
            values = group[column].map(_sign)
            values = values[values != 0]
            result[str(family)][column] = (
                int(values.mode().iloc[0]) if not values.empty else 0
            )
    return result


def _transition_context(monthly: pd.DataFrame) -> pd.DataFrame:
    unique = monthly[["state_date", "actual_family"]].drop_duplicates()
    conflicts = unique.groupby("state_date")["actual_family"].nunique()
    if (conflicts > 1).any():
        raise ValueError("Actual family is inconsistent across overlapping folds.")
    unique = unique.drop_duplicates("state_date").sort_values("state_date")
    unique["previous_actual_family"] = unique["actual_family"].shift(1)
    unique["next_actual_family"] = unique["actual_family"].shift(-1)
    unique["transition_month"] = (
        unique["previous_actual_family"].notna()
        & (unique["actual_family"] != unique["previous_actual_family"])
    )
    unique["one_month_before_transition"] = (
        unique["next_actual_family"].notna()
        & (unique["actual_family"] != unique["next_actual_family"])
    )
    unique["one_month_after_transition"] = unique[
        "transition_month"
    ].shift(1).eq(True)
    return monthly.merge(
        unique[
            [
                "state_date",
                "previous_actual_family",
                "next_actual_family",
                "transition_month",
                "one_month_before_transition",
                "one_month_after_transition",
            ]
        ],
        on="state_date",
        how="left",
        validate="many_to_one",
    )


def build_monthly_attribution(
    ranked: pd.DataFrame,
    families: list[str],
    columns: dict[str, str],
    settings: AuditSettings,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict[str, int]]]:
    source = _score(
        ranked.loc[
            ranked[columns["benchmark"]].astype(str) == SOURCE_ID
        ].copy(),
        families,
    )
    rolling = _score(
        ranked.loc[
            ranked[columns["benchmark"]].astype(str)
            == settings.primary_comparator
        ].copy(),
        families,
    )
    if source.empty or rolling.empty:
        raise ValueError("Both source and rolling_frequency rows are required.")

    key = [columns["fold"], columns["date"]]
    if source.duplicated(key).any() or rolling.duplicated(key).any():
        raise ValueError(
            "Source/comparator rows must be unique by fold and date."
        )

    source_rename = {
        columns["fold"]: "fold_id",
        columns["date"]: "state_date",
        columns["actual"]: "actual_family",
        "predicted_family": "source_predicted_family",
        "actual_family_rank": "source_actual_family_rank",
        "actual_family_probability": "source_actual_family_probability",
        "top1_probability": "source_top1_probability",
        "top2_probability": "source_top2_probability",
        "top3_probability": "source_top3_probability",
        "second_third_probability_gap": "source_second_third_probability_gap",
        "entropy": "source_entropy",
        "normalised_entropy": "source_normalised_entropy",
        "top1_hit": "source_top1_hit",
        "top2_hit": "source_top2_hit",
        "top3_hit": "source_top3_hit",
        "soft_brier": "source_soft_brier",
        "soft_log_loss": "source_soft_log_loss",
    }
    source_columns = [
        column for column in source_rename if column in source.columns
    ] + [column for column in DIMENSIONS if column in source.columns]
    left = source[source_columns].rename(columns=source_rename)

    rolling_rename = {
        columns["fold"]: "fold_id",
        columns["date"]: "state_date",
        "predicted_family": "rolling_frequency_predicted_family",
        "actual_family_rank": "rolling_frequency_actual_family_rank",
        "actual_family_probability": "rolling_frequency_actual_family_probability",
        "top1_hit": "rolling_frequency_top1_hit",
        "top2_hit": "rolling_frequency_top2_hit",
        "top3_hit": "rolling_frequency_top3_hit",
        "soft_brier": "rolling_frequency_soft_brier",
        "soft_log_loss": "rolling_frequency_soft_log_loss",
    }
    right = rolling[
        [column for column in rolling_rename if column in rolling.columns]
    ].rename(columns=rolling_rename)

    monthly = left.merge(
        right,
        on=["fold_id", "state_date"],
        validate="one_to_one",
    ).sort_values(["fold_id", "state_date"])
    monthly = _transition_context(monthly)

    signatures = _signatures(source, columns["actual"])

    def adjacent(row: pd.Series) -> Any:
        actual = signatures.get(str(row.actual_family))
        predicted = signatures.get(str(row.source_predicted_family))
        if not actual or not predicted:
            return np.nan
        common = set(actual) & set(predicted)
        if not common:
            return np.nan
        return sum(actual[column] != predicted[column] for column in common) <= 1

    monthly["adjacent_family_miss"] = monthly.apply(adjacent, axis=1)

    def depth(row: pd.Series) -> str:
        if bool(row.source_top2_hit):
            return "top2_hit"
        if (
            int(row.source_actual_family_rank) == 3
            and float(row.source_second_third_probability_gap)
            <= settings.near_miss_gap
        ):
            return "rank_three_near_miss"
        if int(row.source_actual_family_rank) == 3:
            return "rank_three_miss"
        return "rank_four_or_five_deep_miss"

    monthly["miss_depth"] = monthly.apply(depth, axis=1)
    monthly["state_context"] = np.where(
        monthly.transition_month,
        "transition_month",
        "stable_state_month",
    )
    monthly["confidence_context"] = np.select(
        [
            (~monthly.source_top2_hit)
            & (
                monthly.source_top1_probability
                >= settings.confidently_wrong_probability
            ),
            monthly.source_top1_probability
            <= settings.low_confidence_max_probability,
        ],
        ["confidently_wrong", "low_confidence"],
        default="moderate_confidence",
    )
    monthly["adjacency_context"] = np.where(
        monthly.source_top2_hit,
        "not_applicable",
        monthly.adjacent_family_miss.map(
            {
                True: "adjacent_family_miss",
                False: "non_adjacent_family_miss",
            }
        ).fillna("adjacency_unavailable"),
    )

    def attribution(row: pd.Series) -> str:
        actual = signatures.get(str(row.actual_family))
        predicted = signatures.get(str(row.source_predicted_family))
        available = [column for column in DIMENSIONS if column in monthly.columns]
        if not actual or not predicted or not available:
            return "unavailable_from_frozen_v036_evidence"
        drivers = [
            column.removesuffix("_score")
            for column in available
            if _sign(row[column]) != 0
            and predicted.get(column) == _sign(row[column])
            and actual.get(column) != _sign(row[column])
        ]
        if not drivers:
            drivers = [
                column.removesuffix("_score")
                for column in available
                if actual.get(column) != predicted.get(column)
            ]
        return (
            "+".join(sorted(set(drivers)))
            if drivers
            else "interaction_or_uncertainty"
        )

    monthly["dimension_attribution"] = monthly.apply(attribution, axis=1)
    monthly["dimension_disagreement"] = ~monthly.dimension_attribution.isin(
        [
            "interaction_or_uncertainty",
            "unavailable_from_frozen_v036_evidence",
        ]
    )
    monthly["source_brier_improvement"] = (
        monthly.rolling_frequency_soft_brier - monthly.source_soft_brier
    )
    monthly["source_log_loss_improvement"] = (
        monthly.rolling_frequency_soft_log_loss
        - monthly.source_soft_log_loss
    )

    misses = monthly.loc[~monthly.source_top2_hit]
    if misses.empty:
        taxonomy = pd.DataFrame()
    else:
        taxonomy = (
            misses.groupby(
                [
                    "miss_depth",
                    "state_context",
                    "confidence_context",
                    "adjacency_context",
                    "dimension_attribution",
                ],
                dropna=False,
            )
            .agg(
                months=("state_date", "size"),
                mean_actual_probability=(
                    "source_actual_family_probability",
                    "mean",
                ),
                mean_second_third_gap=(
                    "source_second_third_probability_gap",
                    "mean",
                ),
                mean_brier_improvement=(
                    "source_brier_improvement",
                    "mean",
                ),
            )
            .reset_index()
        )
    return monthly, taxonomy, signatures


def rank_diagnostics(monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for model in ("source", "rolling_frequency"):
        rank_column = f"{model}_actual_family_rank"
        probability_column = f"{model}_actual_family_probability"
        for rank, group in monthly.groupby(rank_column):
            rows.append(
                {
                    "model": model,
                    "actual_family_rank": int(rank),
                    "fold_months": len(group),
                    "share": len(group) / len(monthly),
                    "mean_actual_family_probability": group[
                        probability_column
                    ].mean(),
                }
            )
        rows.append(
            {
                "model": model,
                "actual_family_rank": 0,
                "fold_months": len(monthly),
                "share": 1.0,
                "top1_coverage": monthly[f"{model}_top1_hit"].mean(),
                "top2_coverage": monthly[f"{model}_top2_hit"].mean(),
                "top3_coverage": monthly[f"{model}_top3_hit"].mean(),
                "mean_actual_family_probability": monthly[
                    probability_column
                ].mean(),
            }
        )
    return pd.DataFrame(rows)


def transition_diagnostics(monthly: pd.DataFrame) -> pd.DataFrame:
    segments = {
        "stable_state_month": ~monthly.transition_month,
        "transition_month": monthly.transition_month,
        "one_month_before_transition": monthly.one_month_before_transition,
        "one_month_after_transition": monthly.one_month_after_transition,
    }
    rows: list[dict[str, Any]] = []
    for name, mask in segments.items():
        group = monthly.loc[mask]
        if not group.empty:
            rows.append(
                {
                    "segment": name,
                    "fold_months": len(group),
                    "source_top2_coverage": group.source_top2_hit.mean(),
                    "rolling_frequency_top2_coverage": group.rolling_frequency_top2_hit.mean(),
                    "source_mean_brier": group.source_soft_brier.mean(),
                    "rolling_frequency_mean_brier": group.rolling_frequency_soft_brier.mean(),
                    "mean_source_brier_improvement": group.source_brier_improvement.mean(),
                }
            )
    return pd.DataFrame(rows)


def dimension_attribution(monthly: pd.DataFrame) -> pd.DataFrame:
    misses = monthly.loc[~monthly.source_top2_hit]
    if misses.empty:
        return pd.DataFrame(
            columns=[
                "dimension_attribution",
                "fold_months",
                "share_of_top2_misses",
            ]
        )
    output = (
        misses.groupby("dimension_attribution")
        .agg(
            fold_months=("state_date", "size"),
            mean_actual_probability=(
                "source_actual_family_probability",
                "mean",
            ),
            mean_brier_improvement=("source_brier_improvement", "mean"),
        )
        .reset_index()
    )
    output["share_of_top2_misses"] = output.fold_months / len(misses)
    return output.sort_values("fold_months", ascending=False)


def _one_dimensional_labels(
    values: pd.Series | pd.DataFrame,
    name: str,
) -> np.ndarray:
    """Return one positional label per row.

    Duplicate column names can cause pandas selection to return a DataFrame.
    Identical duplicate columns are collapsed defensively; conflicting columns
    fail loudly rather than being converted to unhashable Python lists.
    """

    array = values.astype(str).to_numpy(copy=False)
    if array.ndim == 1:
        return array
    if array.ndim != 2 or array.shape[1] == 0:
        raise ValueError(
            f"{name} labels must be one- or two-dimensional; "
            f"observed shape={array.shape}"
        )

    first = array[:, 0]
    if array.shape[1] > 1:
        conflicts = np.any(array != first[:, None], axis=1)
        if conflicts.any():
            raise ValueError(
                f"{name} contains conflicting duplicate label columns in "
                f"{int(conflicts.sum())} rows."
            )
    return first


def _paired_label_arrays(
    actual: pd.Series | pd.DataFrame,
    predicted: pd.Series | pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
    """Return positional label arrays without pandas index alignment."""

    actual_values = _one_dimensional_labels(actual, "actual")
    predicted_values = _one_dimensional_labels(predicted, "predicted")
    if actual_values.shape[0] != predicted_values.shape[0]:
        raise ValueError(
            "Actual and predicted labels have different lengths: "
            f"{actual_values.shape[0]} != {predicted_values.shape[0]}"
        )
    return actual_values, predicted_values


def _balanced_accuracy(actual: pd.Series, predicted: pd.Series) -> float:
    actual_values, predicted_values = _paired_label_arrays(actual, predicted)
    recalls: list[float] = []
    for family in sorted(set(actual_values.tolist())):
        mask = actual_values == family
        recalls.append(float(np.mean(predicted_values[mask] == family)))
    return float(np.mean(recalls)) if recalls else float("nan")


def _macro_f1(actual: pd.Series, predicted: pd.Series) -> float:
    actual_values, predicted_values = _paired_label_arrays(actual, predicted)
    labels = sorted(
        set(actual_values.tolist()) | set(predicted_values.tolist())
    )
    scores: list[float] = []
    for label in labels:
        actual_positive = actual_values == label
        predicted_positive = predicted_values == label
        true_positive = int(np.sum(actual_positive & predicted_positive))
        false_positive = int(np.sum(~actual_positive & predicted_positive))
        false_negative = int(np.sum(actual_positive & ~predicted_positive))
        denominator = 2 * true_positive + false_positive + false_negative
        scores.append(
            0.0 if denominator == 0 else 2 * true_positive / denominator
        )
    return float(np.mean(scores)) if scores else float("nan")


def fold_metrics(monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for fold, group in monthly.groupby("fold_id"):
        actual = group.actual_family.astype(str)
        source_predicted = group.source_predicted_family.astype(str)
        rolling_predicted = group.rolling_frequency_predicted_family.astype(str)
        rows.append(
            {
                "fold_id": fold,
                "months": len(group),
                "source_family_accuracy": group.source_top1_hit.mean(),
                "rolling_frequency_family_accuracy": group.rolling_frequency_top1_hit.mean(),
                "source_family_balanced_accuracy": _balanced_accuracy(
                    actual, source_predicted
                ),
                "rolling_frequency_family_balanced_accuracy": _balanced_accuracy(
                    actual, rolling_predicted
                ),
                "source_family_macro_f1": _macro_f1(actual, source_predicted),
                "rolling_frequency_family_macro_f1": _macro_f1(
                    actual, rolling_predicted
                ),
                "source_top2_coverage": group.source_top2_hit.mean(),
                "rolling_frequency_top2_coverage": group.rolling_frequency_top2_hit.mean(),
                "source_mean_actual_probability": group.source_actual_family_probability.mean(),
                "rolling_frequency_mean_actual_probability": group.rolling_frequency_actual_family_probability.mean(),
                "source_soft_brier": group.source_soft_brier.mean(),
                "rolling_frequency_soft_brier": group.rolling_frequency_soft_brier.mean(),
                "source_brier_improvement": group.source_brier_improvement.mean(),
                "source_soft_log_loss": group.source_soft_log_loss.mean(),
                "rolling_frequency_soft_log_loss": group.rolling_frequency_soft_log_loss.mean(),
                "source_log_loss_improvement": group.source_log_loss_improvement.mean(),
            }
        )
    return pd.DataFrame(rows).sort_values("fold_id").reset_index(drop=True)


def paired_monthly_scores(monthly: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "state_date",
        "source_soft_brier",
        "rolling_frequency_soft_brier",
        "source_brier_improvement",
        "source_soft_log_loss",
        "rolling_frequency_soft_log_loss",
        "source_log_loss_improvement",
    ]
    unique = monthly[columns].drop_duplicates()
    conflicts = unique.groupby("state_date").size()
    if (conflicts > 1).any():
        raise ValueError(
            "Paired monthly scores differ across overlapping folds."
        )
    return unique.drop_duplicates("state_date").sort_values("state_date")


def _bootstrap(values: np.ndarray, settings: AuditSettings) -> dict[str, float]:
    clean = np.asarray(values, float)
    clean = clean[np.isfinite(clean)]
    count = len(clean)
    if count == 0:
        return {"mean": np.nan, "lower": np.nan, "upper": np.nan}

    rng = np.random.default_rng(settings.random_seed)
    block = max(1, min(settings.bootstrap_block_months, count))
    blocks = math.ceil(count / block)
    offsets = np.arange(block)
    draws = []
    for _ in range(settings.bootstrap_repetitions):
        starts = rng.integers(0, count, blocks)
        indices = np.concatenate(
            [((start + offsets) % count) for start in starts]
        )[:count]
        draws.append(clean[indices].mean())
    alpha = 1.0 - settings.bootstrap_confidence
    return {
        "mean": float(clean.mean()),
        "lower": float(np.quantile(draws, alpha / 2.0)),
        "upper": float(np.quantile(draws, 1.0 - alpha / 2.0)),
    }


def bootstrap_table(
    paired: pd.DataFrame,
    settings: AuditSettings,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "metric": "soft_brier_improvement",
                **_bootstrap(
                    paired.source_brier_improvement.to_numpy(),
                    settings,
                ),
            },
            {
                "metric": "soft_log_loss_improvement",
                **_bootstrap(
                    paired.source_log_loss_improvement.to_numpy(),
                    settings,
                ),
            },
        ]
    )


def comparison_table(
    folds: pd.DataFrame,
    paired: pd.DataFrame,
    bootstrap: pd.DataFrame,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "comparison": "source_vs_rolling_frequency",
                "unique_months": len(paired),
                "folds": len(folds),
                "source_family_accuracy": folds.source_family_accuracy.mean(),
                "rolling_frequency_family_accuracy": folds.rolling_frequency_family_accuracy.mean(),
                "source_family_balanced_accuracy": folds.source_family_balanced_accuracy.mean(),
                "rolling_frequency_family_balanced_accuracy": folds.rolling_frequency_family_balanced_accuracy.mean(),
                "source_family_macro_f1": folds.source_family_macro_f1.mean(),
                "rolling_frequency_family_macro_f1": folds.rolling_frequency_family_macro_f1.mean(),
                "source_top2_coverage": folds.source_top2_coverage.mean(),
                "rolling_frequency_top2_coverage": folds.rolling_frequency_top2_coverage.mean(),
                "source_mean_actual_probability": folds.source_mean_actual_probability.mean(),
                "rolling_frequency_mean_actual_probability": folds.rolling_frequency_mean_actual_probability.mean(),
                "source_soft_brier": folds.source_soft_brier.mean(),
                "rolling_frequency_soft_brier": folds.rolling_frequency_soft_brier.mean(),
                "soft_brier_improvement": folds.source_brier_improvement.mean(),
                "source_soft_log_loss": folds.source_soft_log_loss.mean(),
                "rolling_frequency_soft_log_loss": folds.rolling_frequency_soft_log_loss.mean(),
                "soft_log_loss_improvement": folds.source_log_loss_improvement.mean(),
                "source_brier_fold_win_rate": (
                    folds.source_brier_improvement > 0
                ).mean(),
                "source_log_loss_fold_win_rate": (
                    folds.source_log_loss_improvement > 0
                ).mean(),
                "paired_monthly_brier_improvement": paired.source_brier_improvement.mean(),
                "paired_monthly_log_loss_improvement": paired.source_log_loss_improvement.mean(),
                "brier_bootstrap_lower": bootstrap.loc[
                    bootstrap.metric == "soft_brier_improvement", "lower"
                ].iloc[0],
                "log_loss_bootstrap_lower": bootstrap.loc[
                    bootstrap.metric == "soft_log_loss_improvement", "lower"
                ].iloc[0],
            }
        ]
    )


def _gate(
    governance: pd.DataFrame | None,
    check_id: str,
) -> bool | None:
    if governance is None or not {"check_id", "passed"}.issubset(
        governance.columns
    ):
        return None
    rows = governance.loc[governance.check_id.astype(str) == check_id]
    if rows.empty:
        return None
    return str(rows.iloc[0].passed).lower() in {"true", "1", "yes"}


def _expected(
    summary: pd.DataFrame,
    benchmark: str,
    column: str,
) -> float | None:
    benchmark_column = _first(summary, BENCHMARK_NAMES)
    if not benchmark_column or column not in summary.columns:
        return None
    rows = summary.loc[summary[benchmark_column].astype(str) == benchmark]
    if rows.empty:
        return None
    value = pd.to_numeric(rows.iloc[0][column], errors="coerce")
    return None if pd.isna(value) else float(value)


def governance_table(
    bundle: EvidenceBundle,
    monthly: pd.DataFrame,
    comparison: pd.DataFrame,
    summary: pd.DataFrame,
    v036_governance: pd.DataFrame | None,
    settings: AuditSettings,
) -> pd.DataFrame:
    row = comparison.iloc[0]
    checks: list[tuple[str, bool, Any]] = [
        (
            "v036_source_evidence_read_only",
            True,
            bundle.predictions.name,
        ),
        (
            "fixed_horizon_target_locked",
            _gate(v036_governance, "fixed_horizon_target_locked") is True,
            _gate(v036_governance, "fixed_horizon_target_locked"),
        ),
        (
            "latest_revised_substitution_prohibited",
            _gate(
                v036_governance,
                "latest_revised_substitution_prohibited",
            )
            is True,
            _gate(
                v036_governance,
                "latest_revised_substitution_prohibited",
            ),
        ),
        (
            "rolling_frequency_no_lookahead",
            _gate(
                v036_governance,
                "benchmark_availability_no_lookahead",
            )
            is True,
            _gate(
                v036_governance,
                "benchmark_availability_no_lookahead",
            ),
        ),
        (
            "every_top2_miss_classified",
            monthly.loc[
                ~monthly.source_top2_hit,
                "miss_depth",
            ].notna().all(),
            int((~monthly.source_top2_hit).sum()),
        ),
        (
            "every_audit_row_unique",
            not monthly.duplicated(["fold_id", "state_date"]).any(),
            len(monthly),
        ),
        ("retrospective_report_only", True, "report_only"),
        (
            "prospective_shadow_preserved",
            _gate(v036_governance, "prospective_shadow_isolation") is True,
            _gate(v036_governance, "prospective_shadow_isolation"),
        ),
    ]

    reconciliations = [
        (
            "source_brier_reconciles_v036",
            "source_soft_brier",
            SOURCE_ID,
            "mean_soft_brier",
        ),
        (
            "rolling_brier_reconciles_v036",
            "rolling_frequency_soft_brier",
            settings.primary_comparator,
            "mean_soft_brier",
        ),
        (
            "source_log_loss_reconciles_v036",
            "source_soft_log_loss",
            SOURCE_ID,
            "mean_soft_log_loss",
        ),
        (
            "rolling_log_loss_reconciles_v036",
            "rolling_frequency_soft_log_loss",
            settings.primary_comparator,
            "mean_soft_log_loss",
        ),
        (
            "source_top2_reconciles_v036",
            "source_top2_coverage",
            SOURCE_ID,
            "mean_top2_coverage",
        ),
        (
            "rolling_top2_reconciles_v036",
            "rolling_frequency_top2_coverage",
            settings.primary_comparator,
            "mean_top2_coverage",
        ),
    ]
    dimension_columns_present = [
        column for column in DIMENSIONS if column in monthly.columns
    ]
    misses = monthly.loc[~monthly.source_top2_hit]
    if len(dimension_columns_present) == len(DIMENSIONS):
        dimension_check_id = "dimension_attribution_completed"
        dimension_passed = (
            misses.dimension_attribution
            .ne("unavailable_from_frozen_v036_evidence")
            .all()
        )
        dimension_observed = {
            "available_columns": dimension_columns_present,
            "classified_misses": int(len(misses)),
        }
    else:
        dimension_check_id = "dimension_attribution_unavailable_documented"
        dimension_passed = (
            misses.dimension_attribution
            .eq("unavailable_from_frozen_v036_evidence")
            .all()
        )
        dimension_observed = {
            "available_columns": dimension_columns_present,
            "missing_columns": [
                column
                for column in DIMENSIONS
                if column not in dimension_columns_present
            ],
            "documented_unavailable_misses": int(
                misses.dimension_attribution
                .eq("unavailable_from_frozen_v036_evidence")
                .sum()
            ),
            "total_top2_misses": int(len(misses)),
            "reason": (
                "The frozen v0.3.6 benchmark predictions contain no monthly "
                "growth, inflation, or labour score fields. The only located "
                "score evidence is an undated three-row aggregate "
                "vintage-agreement table and cannot be joined causally."
            ),
        }
    checks.append(
        (
            dimension_check_id,
            bool(dimension_passed),
            dimension_observed,
        )
    )

    for check_id, observed_column, benchmark, expected_column in reconciliations:
        expected = _expected(summary, benchmark, expected_column)
        observed = float(row[observed_column])
        passed = (
            True
            if expected is None
            else abs(observed - expected) <= settings.reconciliation_tolerance
        )
        checks.append(
            (
                check_id,
                passed,
                {
                    "observed": observed,
                    "expected": expected,
                    "absolute_difference": (
                        None if expected is None else abs(observed - expected)
                    ),
                },
            )
        )
    return pd.DataFrame(
        [
            {
                "check_id": check_id,
                "passed": bool(passed),
                "observed": observed,
            }
            for check_id, passed, observed in checks
        ]
    )


def conclusion(comparison: pd.DataFrame) -> str:
    row = comparison.iloc[0]
    if (
        row.soft_brier_improvement > 0
        and row.soft_log_loss_improvement > 0
        and row.brier_bootstrap_lower > 0
        and row.log_loss_bootstrap_lower > 0
        and row.source_brier_fold_win_rate >= 0.60
    ):
        return "source advantage over rolling frequency appears robust"
    if row.soft_brier_improvement > 0 or row.soft_log_loss_improvement > 0:
        return "source advantage is statistically inconclusive"
    return "rolling frequency is not materially inferior"


def run_analysis(
    bundle: EvidenceBundle,
    settings: AuditSettings | None = None,
) -> dict[str, Any]:
    settings = settings or AuditSettings()
    raw = pd.read_csv(bundle.predictions)
    summary = pd.read_csv(bundle.summary)
    v036_fold_metrics = pd.read_csv(bundle.fold_metrics)
    v036_governance = (
        pd.read_csv(bundle.governance) if bundle.governance else None
    )

    prepared, families, columns = prepare_predictions(
        raw,
        v036_fold_metrics,
    )
    ranked = add_rank_diagnostics(prepared, families, columns)
    monthly, taxonomy, signatures = build_monthly_attribution(
        ranked,
        families,
        columns,
        settings,
    )
    ranks = rank_diagnostics(monthly)
    transitions = transition_diagnostics(monthly)
    dimensions = dimension_attribution(monthly)
    folds = fold_metrics(monthly)
    paired = paired_monthly_scores(monthly)
    bootstrap = bootstrap_table(paired, settings)
    comparison = comparison_table(folds, paired, bootstrap)
    governance = governance_table(
        bundle,
        monthly,
        comparison,
        summary,
        v036_governance,
        settings,
    )
    shadow = (
        pd.read_csv(bundle.prospective_shadow)
        if bundle.prospective_shadow
        else pd.DataFrame(
            [
                {
                    "prospective_shadow_start": settings.prospective_shadow_start,
                    "status": "preserved_from_v0.3.6",
                }
            ]
        )
    )
    return {
        "families": families,
        "monthly_attribution": monthly,
        "miss_taxonomy": taxonomy,
        "rank_diagnostics": ranks,
        "transition_diagnostics": transitions,
        "dimension_attribution": dimensions,
        "rolling_frequency_comparison": comparison,
        "fold_metrics": folds,
        "paired_monthly_scores": paired,
        "bootstrap": bootstrap,
        "prospective_shadow": shadow,
        "governance_flags": governance,
        "family_signatures": signatures,
        "conclusion": conclusion(comparison),
        "architecture_pass": bool(governance.passed.all()),
        "input_sha256": {
            "benchmark_predictions": sha256_file(bundle.predictions),
            "benchmark_summary": sha256_file(bundle.summary),
            "benchmark_fold_metrics": sha256_file(bundle.fold_metrics),
        },
    }
