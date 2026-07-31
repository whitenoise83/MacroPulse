from __future__ import annotations

import time

from macropulse.data.fred_client import FredApiError, FredClient
from macropulse.data.repository import MacroRepository
from macropulse.labour.config import target_definitions


def main() -> None:
    client = FredClient()
    repository = MacroRepository()
    repository.initialise()
    total = 0
    for definition in target_definitions():
        print(f"Downloading initial releases for {definition.series_id}: {definition.name}", flush=True)
        try:
            frame = client.get_observations(
                definition.series_id,
                definition.start_date,
                vintage_type="initial",
            )
            total += repository.upsert_observations(frame)
            print(f"  initial-release observations: {len(frame):,}", flush=True)
            time.sleep(0.25)
        except FredApiError as exc:
            print(f"  ERROR: {exc}", flush=True)
            raise
    print(f"Finished. Inserted or refreshed {total:,} initial-release labour rows.")


if __name__ == "__main__":
    main()
