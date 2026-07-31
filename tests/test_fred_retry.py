from __future__ import annotations

from dataclasses import dataclass

import pytest
import requests

from macropulse.data.fred_client import FredApiError, FredClient


@dataclass
class FakeResponse:
    status_code: int
    payload: dict | None = None
    text: str = ""
    headers: dict | None = None

    def __post_init__(self):
        self.headers = self.headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload or {}


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.headers = {}

    def get(self, *args, **kwargs):
        self.calls += 1
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def client_with(responses, max_retries=3):
    client = FredClient(
        api_key="a" * 32,
        max_retries=max_retries,
        backoff_base_seconds=0,
        backoff_cap_seconds=0,
    )
    client.session = FakeSession(responses)
    return client


def test_retries_502_then_succeeds(monkeypatch):
    monkeypatch.setattr("macropulse.data.fred_client.time.sleep", lambda _: None)
    client = client_with(
        [
            FakeResponse(502, text="bad gateway"),
            FakeResponse(502, text="bad gateway"),
            FakeResponse(200, payload={"observations": []}),
        ]
    )
    payload = client._get("series/observations", {"series_id": "CPIAUCSL"})
    assert payload == {"observations": []}
    assert client.session.calls == 3


def test_retries_connection_timeout_then_succeeds(monkeypatch):
    monkeypatch.setattr("macropulse.data.fred_client.time.sleep", lambda _: None)
    client = client_with(
        [requests.Timeout("temporary"), FakeResponse(200, payload={"ok": True})]
    )
    assert client._get("series", {"series_id": "CPIAUCSL"}) == {"ok": True}
    assert client.session.calls == 2


def test_retry_exhaustion_raises_clean_error(monkeypatch):
    monkeypatch.setattr("macropulse.data.fred_client.time.sleep", lambda _: None)
    client = client_with(
        [FakeResponse(502, text="bad gateway"), FakeResponse(502, text="bad gateway")],
        max_retries=1,
    )
    with pytest.raises(FredApiError, match="after 2 attempts"):
        client._get("series/observations", {"series_id": "CPIAUCSL"})
