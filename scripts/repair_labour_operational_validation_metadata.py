from __future__ import annotations

import argparse

from macropulse.data.repository import MacroRepository
from macropulse.labour.validation_repair import (
    repair_operational_validation_metadata,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Repair the known Model 1C operational-validation metadata "
            "column-order defect."
        )
    )
    parser.add_argument("--validation-id", required=True)
    args = parser.parse_args()

    repository = MacroRepository()
    repository.initialise()
    result = repair_operational_validation_metadata(
        repository, args.validation_id
    )

    print("Model 1C operational-validation metadata repair complete")
    print(f"Validation ID: {result['validation_id']}")
    print(f"Live run ID: {result['live_run_id']}")
    print(f"Status: {result['status']}")
    print("Before:")
    for key, value in result["before"].items():
        print(f"  {key}: {value}")
    print("After:")
    for key, value in result["after"].items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
