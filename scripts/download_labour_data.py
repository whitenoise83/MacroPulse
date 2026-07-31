from __future__ import annotations

import argparse
import time

from macropulse.data.fred_client import FredApiError, FredClient
from macropulse.data.repository import MacroRepository
from macropulse.labour.config import get_labour_series_definitions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Model 1C labour data from FRED.")
    parser.add_argument(
        "--include-initial",
        action="store_true",
        help="Also download initial-release observations for later vintage validation.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = FredClient()
    repository = MacroRepository()
    repository.initialise()
    total = 0
    for definition in get_labour_series_definitions():
        print(f"Downloading {definition.series_id}: {definition.name}")
        try:
            metadata = client.get_series_metadata(definition.series_id)
            repository.upsert_metadata(metadata)
            latest = client.get_observations(
                definition.series_id,
                definition.start_date,
                vintage_type="latest",
            )
            total += repository.upsert_observations(latest)
            print(f"  current observations: {len(latest):,}")
            if args.include_initial:
                initial = client.get_observations(
                    definition.series_id,
                    definition.start_date,
                    vintage_type="initial",
                )
                total += repository.upsert_observations(initial)
                print(f"  initial-release observations: {len(initial):,}")
            time.sleep(0.25)
        except FredApiError as exc:
            print(f"  ERROR: {exc}")
            raise
    print(f"Finished. Inserted or refreshed {total:,} labour-data rows.")


if __name__ == "__main__":
    main()
