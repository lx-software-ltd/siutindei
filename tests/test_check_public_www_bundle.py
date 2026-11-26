"""Matcher tests for the public website bundle check."""

from __future__ import annotations

import importlib.util
import sys
import urllib.request
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_public_www_bundle.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_public_www_bundle", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bundle_check = _load()


def test_bundle_matcher_flags_removed_paths() -> None:
    bundle = 'fetch("/v1/activities/search");const root="/www/assets"'
    assert bundle_check.bundle_offenders(bundle) == (
        "/v1/activities/search",
        "/www/",
    )


def test_bundle_matcher_accepts_the_current_search_path() -> None:
    bundle = 'fetch("/api/v1/public/activities/search")'
    assert bundle_check.bundle_offenders(bundle) == ()


def test_script_urls_find_the_bundle() -> None:
    html = (
        '<html><script src="/_next/static/chunks/main-abc.js"></script>'
        '<script src="/keep.json"></script></html>'
    )
    assert bundle_check.script_urls(html) == ["/_next/static/chunks/main-abc.js"]


def test_refuses_a_non_https_origin(monkeypatch, capsys) -> None:
    monkeypatch.setenv(bundle_check.ORIGIN_ENV, "file:///etc/passwd")

    def boom(*_args, **_kwargs):
        raise AssertionError("a non-https origin must not be opened")

    monkeypatch.setattr(bundle_check.urllib.request, "urlopen", boom)
    assert bundle_check.main() == 1
    error = capsys.readouterr().err
    assert "not https" in error
    assert "file:///etc/passwd" in error


def test_refuses_a_file_url() -> None:
    """file:// is not https, so the guard rejects it before any fetch."""
    try:
        bundle_check.allowed_url("file:///etc/passwd", "siutindei.com")
    except ValueError as exc:
        assert "not https" in str(exc)
        assert "file:///etc/passwd" in str(exc)
    else:
        raise AssertionError("file:// must be refused")


def test_refuses_an_off_host_url() -> None:
    """An https URL on another host is not fetched."""
    try:
        bundle_check.allowed_url("https://evil.example/chunk.js", "siutindei.com")
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("an off-host URL must be refused")
    assert "origin host" in message
    assert "evil.example" in message


def test_redirect_handler_refuses_http() -> None:
    """A redirect from https to http is refused without opening the target."""
    handler = bundle_check.HttpsOnlyRedirectHandler("siutindei.com")
    request = urllib.request.Request("https://siutindei.com/")
    try:
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "http://siutindei.com/en/search/",
        )
    except ValueError as exc:
        assert "not https" in str(exc)
        assert "http://siutindei.com/en/search/" in str(exc)
    else:
        raise AssertionError("an http redirect must be refused")


def test_manifest_chunk_urls_join_static_paths() -> None:
    """The Next build manifest lists chunks without the /_next prefix."""
    text = (
        'self.__BUILD_MANIFEST={" /en/search/":'
        '["static/chunks/app/search/page-abc.js"]}'
    )
    assert bundle_check.chunk_urls(text, "https://siutindei.com") == [
        "https://siutindei.com/_next/static/chunks/app/search/page-abc.js"
    ]


class _Body:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            data = self._payload
            self._payload = b""
            return data
        data = self._payload[:size]
        self._payload = self._payload[size:]
        return data

    def __enter__(self) -> _Body:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


def test_scans_search_pages_and_manifest_chunks(monkeypatch, capsys) -> None:
    """A removed path in a manifest chunk fails even when the root bundle is clean."""
    pages = {
        "https://siutindei.com/": (
            "<html><script src='/_next/static/chunks/root.js'></script>"
            "<script src='/_next/static/abc/_buildManifest.js'></script></html>"
        ),
        "https://siutindei.com/en/search/": (
            "<html><script src='/_next/static/chunks/search.js'></script></html>"
        ),
        "https://siutindei.com/zh-HK/search/": "<html></html>",
        "https://siutindei.com/_next/static/abc/_buildManifest.js": (
            'self.__BUILD_MANIFEST={"x":["static/chunks/split-search.js"]}'
        ),
        "https://siutindei.com/_next/static/chunks/root.js": "home",
        "https://siutindei.com/_next/static/chunks/search.js": (
            "fetch('/api/v1/public/activities/search')"
        ),
        "https://siutindei.com/_next/static/chunks/split-search.js": (
            "fetch('/v1/activities/search')"
        ),
    }
    opened: list[str] = []

    def open_request(request, _timeout, _origin_host):
        opened.append(request.full_url)
        body = pages.get(request.full_url)
        if body is None:
            raise AssertionError(f"unexpected fetch {request.full_url}")
        return _Body(body.encode())

    monkeypatch.setattr(bundle_check, "_open_request", open_request)
    assert bundle_check.check_origin("https://siutindei.com/") == 1
    error = capsys.readouterr().err
    assert "split-search.js" in error
    assert "/v1/activities/search" in error
    assert any(url.endswith("/en/search/") for url in opened)
    assert any(url.endswith("/zh-HK/search/") for url in opened)
    assert any(url.endswith("split-search.js") for url in opened)


def test_off_host_script_is_not_fetched(monkeypatch, capsys) -> None:
    """A script on another host fails the check and is not opened."""

    def open_request(request, _timeout, _origin_host):
        if "evil.example" in request.full_url:
            raise AssertionError("off-host URL was fetched")
        if request.full_url.rstrip("/") == "https://siutindei.com":
            html = "<html><script src='https://evil.example/chunk.js'></script></html>"
            return _Body(html.encode())
        return _Body(b"")

    monkeypatch.setattr(bundle_check, "_open_request", open_request)
    assert bundle_check.check_origin("https://siutindei.com/") == 1
    assert "evil.example" in capsys.readouterr().err


def test_skips_when_the_origin_is_unset(monkeypatch, capsys) -> None:
    monkeypatch.delenv(bundle_check.ORIGIN_ENV, raising=False)

    def boom(*_args, **_kwargs):
        raise AssertionError("the skipped check must not download")

    monkeypatch.setattr(bundle_check.urllib.request, "urlopen", boom)
    assert bundle_check.main() == 0
    output = capsys.readouterr().out
    assert "check skipped" in output
    assert bundle_check.ORIGIN_ENV in output
