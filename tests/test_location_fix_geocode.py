"""Nominatim queries stay inside Hong Kong without a country filter."""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import pytest
from app.services.aws_proxy import AwsProxyError
from app.services.location_fix_geocode import (
    AddressLookupFailed,
    geocode_address,
    lookup_address,
)


def _headers(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.location_fix_geocode._get_nominatim_headers",
        lambda: {"User-Agent": "test", "Referer": "https://example.com"},
    )


def test_lookup_drops_the_country_filter_and_appends_hong_kong(monkeypatch) -> None:
    _headers(monkeypatch)
    seen: dict[str, str] = {}

    def fake_invoke(_method, url, **_kwargs):
        seen["url"] = url
        return {
            "status": 200,
            "body": json.dumps(
                [
                    {
                        "lat": "22.28",
                        "lon": "114.15",
                        "place_rank": 30,
                        "type": "house",
                        "display_name": "8 Harbour Road, Hong Kong",
                    }
                ]
            ),
        }

    monkeypatch.setattr("app.services.location_fix_geocode.http_invoke", fake_invoke)
    found = lookup_address("8 Harbour Road")
    assert found is not None
    assert found["place_rank"] == 30
    query = parse_qs(urlparse(seen["url"]).query)
    assert "countrycodes" not in query
    assert query["q"] == ["8 Harbour Road, Hong Kong"]
    assert geocode_address("8 Harbour Road") == (22.28, 114.15)


def test_lookup_rejects_a_hit_outside_hong_kong(monkeypatch) -> None:
    _headers(monkeypatch)

    def fake_invoke(*_args, **_kwargs):
        return {
            "status": 200,
            "body": json.dumps([{"lat": "39.9", "lon": "116.4", "place_rank": 30}]),
        }

    monkeypatch.setattr("app.services.location_fix_geocode.http_invoke", fake_invoke)
    assert lookup_address("8 Harbour Road") is None


def test_lookup_keeps_an_address_that_already_names_hong_kong(monkeypatch) -> None:
    _headers(monkeypatch)
    seen: dict[str, str] = {}

    def fake_invoke(_method, url, **_kwargs):
        seen["url"] = url
        return {"status": 200, "body": "[]"}

    monkeypatch.setattr("app.services.location_fix_geocode.http_invoke", fake_invoke)
    assert lookup_address("8 Harbour Road, Hong Kong") is None
    query = parse_qs(urlparse(seen["url"]).query)
    assert query["q"] == ["8 Harbour Road, Hong Kong"]


def test_transport_failure_is_not_a_miss(monkeypatch) -> None:
    _headers(monkeypatch)

    def fake_invoke(*_args, **_kwargs):
        raise AwsProxyError("Timeout", "timed out")

    monkeypatch.setattr("app.services.location_fix_geocode.http_invoke", fake_invoke)
    with pytest.raises(AddressLookupFailed):
        lookup_address("8 Harbour Road")
    assert geocode_address("8 Harbour Road") is None


def test_bad_status_is_not_a_miss(monkeypatch) -> None:
    _headers(monkeypatch)

    def fake_invoke(*_args, **_kwargs):
        return {"status": 429, "body": ""}

    monkeypatch.setattr("app.services.location_fix_geocode.http_invoke", fake_invoke)
    with pytest.raises(AddressLookupFailed):
        lookup_address("8 Harbour Road")
