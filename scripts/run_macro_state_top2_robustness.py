from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from macropulse.macro_state.top2_robustness_service import run_macro_state_top2_robustness_audit


def main() -> None:
    result = run_macro_state_top2_robustness_audit(PROJECT_ROOT)
    row = result["rolling_frequency_comparison"].iloc[0]
    failed = result["governance_flags"].loc[~result["governance_flags"].passed]
    print("Model 1D top-two miss and rolling-frequency robustness audit complete")
    print(f"Audit ID: {result['audit_id']}")
    print(f"Model: {result['model_id']} v{result['model_version']} (development)")
    print(f"Source evidence: {result['source_evidence_stem']}")
    print("Status: retrospective research evidence only; no promotion authority")
    print("\nSource versus rolling frequency")
    print(f"  top-two coverage: {float(row.source_top2_coverage):.4f} vs {float(row.rolling_frequency_top2_coverage):.4f}")
    print(f"  soft Brier: {float(row.source_soft_brier):.6f} vs {float(row.rolling_frequency_soft_brier):.6f}")
    print(f"  Brier improvement: {float(row.soft_brier_improvement):.6f}")
    print(f"  bootstrap lower bound: {float(row.brier_bootstrap_lower):.6f}")
    print(f"\nDiagnostic conclusion: {result['conclusion']}")
    print(f"Architecture governance: {'pass' if result['architecture_pass'] else 'fail'}")
    if not failed.empty:
        print("Failed architecture checks")
        for check_id in failed.check_id.astype(str):
            print(f"  - {check_id}")
    print(f"Report: {result['report_path']}")
    print("Status: research evidence only; not candidate or production approved.")


if __name__ == "__main__":
    main()
