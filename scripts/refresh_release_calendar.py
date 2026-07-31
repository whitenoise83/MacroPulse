from __future__ import annotations

from datetime import date, timedelta
import time

import pandas as pd

from macropulse.config import get_series_definitions
from macropulse.data.fred_client import FredApiError, FredClient
from macropulse.data.repository import MacroRepository


def main() -> None:
    client = FredClient()
    repository = MacroRepository()
    repository.initialise()

    today = date.today()
    window_start = today - timedelta(days=60)
    window_end = today + timedelta(days=180)
    release_cache: dict[int, pd.DataFrame] = {}
    total = 0

    for definition in get_series_definitions():
        print(f"Release calendar for {definition.series_id}: {definition.name}")
        try:
            release = client.get_series_release(definition.series_id)
            release_id = int(release["id"])
            release_name = str(release.get("name", definition.name))
            if release_id not in release_cache:
                release_cache[release_id] = client.get_release_dates(
                    release_id, include_dates_with_no_data=True
                )
                time.sleep(0.20)
            dates = release_cache[release_id].copy()
            dates = dates.loc[
                (pd.to_datetime(dates["release_date"]).dt.date >= window_start)
                & (pd.to_datetime(dates["release_date"]).dt.date <= window_end)
            ]
            dates["series_id"] = definition.series_id
            dates["release_name"] = release_name
            dates["retrieved_at"] = pd.Timestamp.now(tz="UTC").tz_localize(None)
            dates = dates[
                [
                    "series_id",
                    "release_id",
                    "release_name",
                    "release_date",
                    "release_last_updated",
                    "retrieved_at",
                ]
            ]
            total += repository.replace_release_calendar(definition.series_id, dates)
            print(f"  release: {release_name} ({release_id})")
            print(f"  dates in tracking window: {len(dates)}")
        except FredApiError as exc:
            print(f"  WARNING: {exc}")

    print(f"Finished. Stored {total} series-release-date rows.")


if __name__ == "__main__":
    main()
