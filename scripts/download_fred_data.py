from __future__ import annotations

import argparse
import time

from macropulse.config import get_series_definitions
from macropulse.data.fred_client import FredClient, FredApiError
from macropulse.data.repository import MacroRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download MacroPulse FRED data.")
    parser.add_argument(
        "--skip-initial",
        action="store_true",
        help="Download current values only and skip initial-release observations.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = FredClient()
    repository = MacroRepository()
    repository.initialise()

    total_rows = 0
    for definition in get_series_definitions():
        print(f"Downloading {definition.series_id}: {definition.name}")

        try:
            metadata = client.get_series_metadata(definition.series_id)
            repository.upsert_metadata(metadata)

            latest = client.get_observations(
                series_id=definition.series_id,
                observation_start=definition.start_date,
                vintage_type="latest",
            )
            total_rows += repository.upsert_observations(latest)
            print(f"  current observations: {len(latest):,}")

            if not args.skip_initial:
                initial = client.get_observations(
                    series_id=definition.series_id,
                    observation_start=definition.start_date,
                    vintage_type="initial",
                )
                total_rows += repository.upsert_observations(initial)
                print(f"  initial-release observations: {len(initial):,}")

            # Be polite to the public API.
            time.sleep(0.25)

        except FredApiError as exc:
            print(f"  ERROR: {exc}")
            raise

    print(f"Finished. Inserted or refreshed {total_rows:,} observation rows.")


if __name__ == "__main__":
    main()
