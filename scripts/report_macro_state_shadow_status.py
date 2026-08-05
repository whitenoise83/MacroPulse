from __future__ import annotations

import argparse
from datetime import date

from macropulse.data.repository import MacroRepository
from macropulse.operations.model1d_shadow_monitoring import run_shadow_monitoring


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report Model 1D v0.3.8 prospective-shadow operational status."
    )
    parser.add_argument(
        "--as-of",
        help="Monitoring cutoff in YYYY-MM-DD format. Defaults to today.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print status without writing report files.",
    )
    args = parser.parse_args()
    as_of = date.fromisoformat(args.as_of) if args.as_of else None

    result = run_shadow_monitoring(
        repository=MacroRepository(),
        as_of=as_of,
        write_report=not args.no_write,
    )
    readiness = result["readiness"].iloc[0]
    print("Model 1D prospective-shadow monitoring complete")
    print(f"Model version: {result['model_version']}")
    print(f"Monitoring cutoff: {result['as_of']}")
    print(f"Shadow runs: {len(result['run_status'])}")
    print(
        "Complete target months: "
        f"{int(readiness['complete_target_months'])}/"
        f"{int(readiness['minimum_complete_target_months'])}"
    )
    print(
        "Integrity: " + ("PASS" if readiness["integrity_pass"] else "FAIL")
    )
    print(
        "Comparison permitted: "
        + ("yes" if readiness["comparison_permitted"] else "no")
    )
    print(f"Conclusion status: {readiness['conclusion_status']}")
    print(f"Promotion authority: {readiness['promotion_authority']}")
    failed = result["integrity_checks"].loc[
        ~result["integrity_checks"]["passed"].astype(bool)
    ]
    if not failed.empty:
        print("Failed integrity checks:")
        for check_id in failed["check_id"].astype(str):
            print(f"- {check_id}")
    report = result["output_paths"].get("report")
    if report:
        print(f"Monitoring report: {report}")


if __name__ == "__main__":
    main()
