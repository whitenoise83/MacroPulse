from __future__ import annotations

import argparse

from macropulse.labour.operational_validation import run_labour_operational_validation


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a governed Model 1C live candidate run."
    )
    parser.add_argument("--run-id", help="Governed live run ID. Defaults to the latest run.")
    args = parser.parse_args()
    result = run_labour_operational_validation(run_id=args.run_id)
    print("Model 1C governed live validation complete")
    print(f"Validation ID: {result['validation_id']}")
    print(f"Live run ID: {result['run_id']}")
    print(f"Status: {result['status']}")
    print(f"Passed: {result['passed']}")
    print(f"Failed: {result['failed']}")
    print(f"Warnings: {result['warnings']}")
    print(f"Report: {result['report_path']}")
    attention = result["checks"].loc[result["checks"]["status"] != "pass"]
    if not attention.empty:
        print()
        print("Checks requiring attention")
        print(attention.to_string(index=False))


if __name__ == "__main__":
    main()
