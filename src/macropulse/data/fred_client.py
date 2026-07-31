from __future__ import annotations

from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
import random
import time
from typing import Any

import pandas as pd
import requests

from macropulse.settings import settings




def _parse_fred_dates(values: pd.Series) -> pd.Series:
    """Parse FRED ISO dates without pandas' out-of-bounds warning.

    ALFRED uses 9999-12-31 for an open-ended real-time interval. Keeping it
    as a native Python date preserves that meaning and remains compatible with
    DuckDB DATE columns.
    """
    text = values.astype("string")
    open_ended = text.eq("9999-12-31")
    parsed = pd.to_datetime(
        text.mask(open_ended),
        format="%Y-%m-%d",
        errors="coerce",
    ).dt.date.astype("object")
    parsed.loc[open_ended] = date.max
    return parsed

class FredApiError(RuntimeError):
    pass


class FredClient:
    BASE_URL = "https://api.stlouisfed.org/fred"

    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(
        self,
        api_key: str | None = None,
        timeout_seconds: int = 45,
        max_retries: int = 7,
        backoff_base_seconds: float = 1.5,
        backoff_cap_seconds: float = 45.0,
    ) -> None:
        self.api_key = api_key or settings.require_fred_api_key()
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, int(max_retries))
        self.backoff_base_seconds = max(0.0, float(backoff_base_seconds))
        self.backoff_cap_seconds = max(0.0, float(backoff_cap_seconds))
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "MacroPulse/1B-v0.2.0.post1 (macroeconomic research application)"}
        )

    @staticmethod
    def _retry_after_seconds(response: requests.Response) -> float | None:
        value = response.headers.get("Retry-After")
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                retry_time = parsedate_to_datetime(value)
                now = datetime.now(retry_time.tzinfo or timezone.utc)
                return max(0.0, (retry_time - now).total_seconds())
            except (TypeError, ValueError, OverflowError):
                return None

    def _retry_delay(self, attempt: int, response: requests.Response | None = None) -> float:
        if response is not None:
            retry_after = self._retry_after_seconds(response)
            if retry_after is not None:
                return min(retry_after, self.backoff_cap_seconds)
        exponential = self.backoff_base_seconds * (2 ** max(0, attempt - 1))
        jitter = random.uniform(0.0, min(1.0, self.backoff_base_seconds))
        return min(exponential + jitter, self.backoff_cap_seconds)

    def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        request_params = {
            "api_key": self.api_key,
            "file_type": "json",
            **params,
        }
        url = f"{self.BASE_URL}/{endpoint}"
        last_error: str | None = None

        for attempt in range(1, self.max_retries + 2):
            response: requests.Response | None = None
            try:
                response = self.session.get(
                    url,
                    params=request_params,
                    timeout=self.timeout_seconds,
                )
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt > self.max_retries:
                    break
                delay = self._retry_delay(attempt)
                print(
                    f"  FRED connection problem; retry {attempt}/{self.max_retries} "
                    f"in {delay:.1f}s...",
                    flush=True,
                )
                time.sleep(delay)
                continue
            except requests.RequestException as exc:
                # Non-transient request errors should fail immediately.
                raise FredApiError(f"FRED request failed: {type(exc).__name__}: {exc}") from None

            if response.status_code in self.RETRYABLE_STATUS_CODES:
                last_error = (
                    f"HTTP {response.status_code}: "
                    f"{response.text[:500]}"
                )
                if attempt > self.max_retries:
                    break
                delay = self._retry_delay(attempt, response)
                print(
                    f"  FRED transient HTTP {response.status_code}; "
                    f"retry {attempt}/{self.max_retries} in {delay:.1f}s...",
                    flush=True,
                )
                time.sleep(delay)
                continue

            try:
                response.raise_for_status()
            except requests.HTTPError:
                message = response.text[:500]
                # Do not chain the requests exception because its URL contains the API key.
                raise FredApiError(
                    f"FRED request failed with HTTP {response.status_code}: {message}"
                ) from None

            try:
                payload = response.json()
            except requests.JSONDecodeError:
                raise FredApiError(
                    f"FRED returned invalid JSON with HTTP {response.status_code}: "
                    f"{response.text[:500]}"
                ) from None
            if "error_code" in payload:
                raise FredApiError(
                    f"FRED API error {payload['error_code']}: "
                    f"{payload.get('error_message')}"
                )
            return payload

        raise FredApiError(
            f"FRED request failed after {self.max_retries + 1} attempts. "
            f"Last error: {last_error or 'unknown transient error'}"
        ) from None


    def get_series_release(self, series_id: str) -> dict[str, Any]:
        payload = self._get("series/release", {"series_id": series_id})
        releases = payload.get("releases", [])
        if not releases:
            raise FredApiError(f"No release metadata returned for FRED series {series_id}.")
        return releases[0]

    def get_release_dates(
        self,
        release_id: int,
        include_dates_with_no_data: bool = True,
    ) -> pd.DataFrame:
        payload = self._get(
            "release/dates",
            {
                "release_id": int(release_id),
                "include_release_dates_with_no_data": (
                    "true" if include_dates_with_no_data else "false"
                ),
                "sort_order": "asc",
                "limit": 10000,
            },
        )
        frame = pd.DataFrame(payload.get("release_dates", []))
        columns = ["release_id", "release_date", "release_last_updated"]
        if frame.empty:
            return pd.DataFrame(columns=columns)
        frame = frame.rename(columns={"date": "release_date"})
        frame["release_id"] = int(release_id)
        frame["release_date"] = _parse_fred_dates(frame["release_date"])
        if "release_last_updated" not in frame.columns:
            frame["release_last_updated"] = None
        return frame[columns].dropna(subset=["release_date"])

    def get_series_metadata(self, series_id: str) -> dict[str, Any]:
        payload = self._get("series", {"series_id": series_id})
        series = payload.get("seriess", [])
        if not series:
            raise FredApiError(f"No metadata returned for FRED series {series_id}.")
        return series[0]

    @staticmethod
    def _parse_observation_frame(
        observations: list[dict[str, Any]],
        series_id: str,
        vintage_type: str,
    ) -> pd.DataFrame:
        frame = pd.DataFrame(observations)
        columns = [
            "series_id",
            "observation_date",
            "realtime_start",
            "realtime_end",
            "value",
            "vintage_type",
            "retrieved_at",
            "source",
        ]
        if frame.empty:
            return pd.DataFrame(columns=columns)

        frame = frame.rename(columns={"date": "observation_date"})
        frame["series_id"] = series_id
        frame["observation_date"] = _parse_fred_dates(frame["observation_date"])
        frame["realtime_start"] = _parse_fred_dates(frame["realtime_start"])
        frame["realtime_end"] = _parse_fred_dates(frame["realtime_end"])
        frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
        frame["vintage_type"] = vintage_type
        frame["retrieved_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
        frame["source"] = "FRED"
        return frame[columns].dropna(subset=["observation_date", "value"])

    def get_observations(
        self,
        series_id: str,
        observation_start: str,
        vintage_type: str = "latest",
    ) -> pd.DataFrame:
        if vintage_type not in {"latest", "initial"}:
            raise ValueError("vintage_type must be 'latest' or 'initial'.")

        today = date.today().isoformat()
        params: dict[str, Any] = {
            "series_id": series_id,
            "observation_start": observation_start,
            "sort_order": "asc",
            "limit": 100000,
            "output_type": 1 if vintage_type == "latest" else 4,
        }

        if vintage_type == "latest":
            params["realtime_start"] = today
            params["realtime_end"] = today
        else:
            params["realtime_start"] = "1776-07-04"
            params["realtime_end"] = "9999-12-31"

        payload = self._get("series/observations", params)
        return self._parse_observation_frame(
            payload.get("observations", []),
            series_id=series_id,
            vintage_type=vintage_type,
        )

    def get_observations_as_of(
        self,
        series_id: str,
        observation_start: str,
        as_of_date: str,
    ) -> pd.DataFrame:
        """Return the series exactly as FRED reported it on a historical date."""
        params: dict[str, Any] = {
            "series_id": series_id,
            "observation_start": observation_start,
            "observation_end": as_of_date,
            "realtime_start": as_of_date,
            "realtime_end": as_of_date,
            "sort_order": "asc",
            "limit": 100000,
            "output_type": 1,
        }
        payload = self._get("series/observations", params)
        observations = self._parse_observation_frame(
            payload.get("observations", []),
            series_id=series_id,
            vintage_type="snapshot",
        )
        if observations.empty:
            return pd.DataFrame(
                columns=[
                    "series_id",
                    "as_of_date",
                    "observation_date",
                    "value",
                    "retrieved_at",
                    "source",
                ]
            )

        observations["as_of_date"] = pd.Timestamp(as_of_date).date()
        return observations[
            [
                "series_id",
                "as_of_date",
                "observation_date",
                "value",
                "retrieved_at",
                "source",
            ]
        ]
