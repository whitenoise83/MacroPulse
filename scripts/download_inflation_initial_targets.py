from __future__ import annotations

import time

from macropulse.data.fred_client import FredApiError, FredClient
from macropulse.data.repository import MacroRepository
from macropulse.inflation.config import target_definitions


def main() -> None:
    client = FredClient()
    repository = MacroRepository()
    repository.initialise()
    total = 0
    for definition in target_definitions():
        print(f"Downloading initial releases for {definition.series_id}: {definition.name}")
        try:
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
    print(f"Finished. Inserted or refreshed {total:,} target initial-release rows.")


if __name__ == "__main__":
    main()
