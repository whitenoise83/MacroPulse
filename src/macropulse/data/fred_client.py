from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pandas as pd
import requests

from macropulse.settings import settings


class FredApiError(RuntimeError):
    pass


class FredClient:
    BASE_URL = "https://api.stlouisfed.org/fred"

    def __init__(self, api_key: str | None = None, timeout_seconds: int = 30) -> None:
        self.api_key = api_key or settings.require_fred_api_key()
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "MacroPulse/0.1 (macroeconomic research application)"}
        )

    def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        request_params = {
            "api_key": self.api_key,
            "file_type": "json",
            **params,
        }
        response = self.session.get(
            f"{self.BASE_URL}/{endpoint}",
            params=request_params,
            timeout=self.timeout_seconds,
        )

        try:
            response.raise_for_status()
        except requests.HTTPError:
            message = response.text[:500]
            # Do not chain the requests exception because its URL contains the API key.
            raise FredApiError(
                f"FRED request failed with HTTP {response.status_code}: {message}"
            ) from None

        payload = response.json()
        if "error_code" in payload:
            raise FredApiError(
                f"FRED API error {payload['error_code']}: {payload.get('error_message')}"
            )
        return payload

    def get_series_metadata(self, series_id: str) -> dict[str, Any]:
        payload = self._get("series", {"series_id": series_id})
        series = payload.get("seriess", [])
        if not series:
            raise FredApiError(f"No metadata returned for FRED series {series_id}.")
        return series[0]

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
            "output_type": 1 if vintage_type == "latest" else 4,
        }

        if vintage_type == "latest":
            # Current values: ask for the data known today.
            params["realtime_start"] = today
            params["realtime_end"] = today
        else:
            # Initial releases require the complete ALFRED real-time period.
            # Without these parameters, FRED defaults both dates to today and
            # output_type=4 can fail when today is not a vintage/release date.
            params["realtime_start"] = "1776-07-04"
            params["realtime_end"] = "9999-12-31"

        payload = self._get("series/observations", params)
        observations = payload.get("observations", [])
        frame = pd.DataFrame(observations)

        if frame.empty:
            return pd.DataFrame(
                columns=[
                    "series_id",
                    "observation_date",
                    "realtime_start",
                    "realtime_end",
                    "value",
                    "vintage_type",
                    "retrieved_at",
                    "source",
                ]
            )

        frame = frame.rename(columns={"date": "observation_date"})
        frame["series_id"] = series_id
        frame["observation_date"] = pd.to_datetime(
            frame["observation_date"], errors="coerce"
        ).dt.date
        frame["realtime_start"] = pd.to_datetime(
            frame["realtime_start"], errors="coerce"
        ).dt.date
        frame["realtime_end"] = pd.to_datetime(
            frame["realtime_end"], errors="coerce"
        ).dt.date
        frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
        frame["vintage_type"] = vintage_type
        frame["retrieved_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
        frame["source"] = "FRED"

        return frame[
            [
                "series_id",
                "observation_date",
                "realtime_start",
                "realtime_end",
                "value",
                "vintage_type",
                "retrieved_at",
                "source",
            ]
        ].dropna(subset=["observation_date", "value"])
