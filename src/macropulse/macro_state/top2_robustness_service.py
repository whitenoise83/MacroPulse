from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
import json

import pandas as pd

from macropulse.macro_state.top2_robustness import AuditSettings, discover_latest_bundle, run_analysis

OUTPUT_KEYS = (
    "monthly_attribution", "miss_taxonomy", "rank_diagnostics", "transition_diagnostics",
    "dimension_attribution", "rolling_frequency_comparison", "fold_metrics",
    "paired_monthly_scores", "bootstrap", "prospective_shadow", "governance_flags",
)


def _table(frame: pd.DataFrame, limit: int = 40) -> str:
    return "_No rows._" if frame.empty else frame.head(limit).to_markdown(index=False)


def _report(audit_id: str, stem: str, result: dict[str, Any], settings: AuditSettings) -> str:
    row = result["rolling_frequency_comparison"].iloc[0]
    failed = result["governance_flags"].loc[~result["governance_flags"].passed]
    failed_text = "- None" if failed.empty else "\n".join(f"- `{x}`" for x in failed.check_id.astype(str))
    return f"""# Model 1D v0.3.7 — Top-two miss and rolling-frequency robustness audit

**Audit ID:** `{audit_id}`
**Source evidence:** `{stem}`
**Status:** retrospective research evidence only
**Promotion authority:** none

## Research contract

- Frozen source: v0.3.6 source probabilities
- Primary target: `fixed_horizon_90d`
- Primary level: five-family state
- Primary comparator: `{settings.primary_comparator}`
- Latest-revised substitution: prohibited
- Prospective shadow start: `{settings.prospective_shadow_start}`

## Main comparison

- Source top-two coverage: {float(row.source_top2_coverage):.4f}
- Rolling-frequency top-two coverage: {float(row.rolling_frequency_top2_coverage):.4f}
- Source soft Brier: {float(row.source_soft_brier):.6f}
- Rolling-frequency soft Brier: {float(row.rolling_frequency_soft_brier):.6f}
- Soft-Brier improvement: {float(row.soft_brier_improvement):.6f}
- Brier bootstrap lower bound: {float(row.brier_bootstrap_lower):.6f}
- Log-loss bootstrap lower bound: {float(row.log_loss_bootstrap_lower):.6f}

## Diagnostic conclusion

**{result['conclusion']}.**

This conclusion is diagnostic only. The consumed retrospective sample cannot approve promotion.

## Architecture governance

Overall architecture result: **{'PASS' if result['architecture_pass'] else 'FAIL'}**

Failed checks:

{failed_text}

## Top-two miss taxonomy

{_table(result['miss_taxonomy'])}

## Transition diagnostics

{_table(result['transition_diagnostics'])}

## Dimension attribution

The frozen v0.3.6 benchmark-prediction evidence contains no monthly
`growth_score`, `inflation_score`, or `labour_score` fields. The only located
score evidence is an undated three-row aggregate vintage-agreement table, so it
cannot be joined causally to the fold-month observations. Dimension and
adjacency attribution are therefore explicitly recorded as unavailable rather
than inferred from revised or unrelated evidence.

{_table(result['dimension_attribution'])}

## Rolling-frequency comparison

{_table(result['rolling_frequency_comparison'])}

## Bootstrap evidence

{_table(result['bootstrap'])}

## Governance flags

{_table(result['governance_flags'])}
"""


def run_macro_state_top2_robustness_audit(repository_or_root: Any, settings: AuditSettings | None = None) -> dict[str, Any]:
    project_root = Path(getattr(repository_or_root, "project_root", repository_or_root))
    settings = settings or AuditSettings()
    bundle = discover_latest_bundle(project_root)
    result = run_analysis(bundle, settings)
    audit_id = str(uuid4())
    output_dir = project_root / "reports" / "macro_state_top2_robustness"
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_dir / f"model1d_top2_{audit_id}"

    output_paths: dict[str, str] = {}
    for key in OUTPUT_KEYS:
        path = Path(f"{prefix}_{key}.csv")
        result[key].to_csv(path, index=False)
        output_paths[key] = str(path)

    metadata = {
        "audit_id": audit_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_id": "US_MACRO_STATE_1D", "model_version": "0.3.7",
        "lifecycle_status": "development", "research_status": "retrospective_diagnostic_only",
        "source_evidence_stem": bundle.stem, "source_evidence_sha256": result["input_sha256"],
        "families": result["families"], "family_signatures": result["family_signatures"],
        "settings": asdict(settings), "architecture_pass": result["architecture_pass"],
        "conclusion": result["conclusion"], "promotion_approved": False,
        "output_paths": output_paths,
    }
    metadata_path = Path(f"{prefix}_metadata.json")
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True, default=str), encoding="utf-8")
    output_paths["metadata"] = str(metadata_path)

    report_path = Path(f"{prefix}.md")
    report_path.write_text(_report(audit_id, bundle.stem, result, settings), encoding="utf-8")
    output_paths["report"] = str(report_path)

    return {
        "audit_id": audit_id, "model_id": "US_MACRO_STATE_1D", "model_version": "0.3.7",
        "architecture_pass": result["architecture_pass"], "promotion_approved": False,
        "conclusion": result["conclusion"], "source_evidence_stem": bundle.stem,
        "report_path": str(report_path), "output_paths": output_paths,
        **{key: result[key] for key in OUTPUT_KEYS},
    }
