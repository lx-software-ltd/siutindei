#!/usr/bin/env python3
"""Fail if a live public-site bundle still names a removed path.

Reads ``PUBLIC_WWW_SITE_ORIGIN``. When that variable is unset, the check
prints that it was skipped and exits 0. Otherwise it downloads the origin,
the locale search pages, and the JavaScript chunks those pages and the
Next.js ``_buildManifest.js`` list. It exits 1 if a bundle contains
``/v1/activities/search`` or ``/www/``.

Fetches stay on https and on the origin host. A redirect to any other
scheme or host is refused. Each response is capped. The script only reads
HTTP. It does not call AWS.
"""

from __future__ import annotations

import os
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

ORIGIN_ENV = "PUBLIC_WWW_SITE_ORIGIN"
REMOVED_PATHS = ("/v1/activities/search", "/www/")
# The public site exports these two locales. The search client is a
# code-split chunk of these pages, not of the root page.
SEARCH_PAGE_PATHS = ("/en/search/", "/zh-HK/search/")
TIMEOUT_SECONDS = 20
MAX_BYTES = 5_000_000
_JS_PATH = re.compile(r"(?:/_next/static/|static/)[^\"'\\)\s<>]+\.js")
_MANIFEST_PATH = re.compile(r"/_next/static/[^\"'\\s<>]+/_buildManifest\.js")


class ScriptSources(HTMLParser):
    """Collect script src URLs from an HTML document."""

    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "script":
            return
        values = dict(attrs)
        src = values.get("src")
        if not src:
            return
        path = src.split("?", 1)[0]
        if path.endswith(".js"):
            self.sources.append(src)


class HttpsOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse a redirect that leaves https or the origin host."""

    def __init__(self, origin_host: str) -> None:
        super().__init__()
        self._origin_host = origin_host

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        parsed = urlsplit(newurl)
        if parsed.scheme != "https":
            raise ValueError(f"refusing a redirect that is not https: {newurl}")
        if parsed.hostname != self._origin_host:
            raise ValueError(
                f"refusing a redirect whose host is not the origin host: {newurl}"
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def bundle_offenders(bundle: str) -> tuple[str, ...]:
    """Return removed paths that appear in a bundle string."""
    return tuple(path for path in REMOVED_PATHS if path in bundle)


def script_urls(html: str) -> list[str]:
    """Return JavaScript bundle URLs referenced by HTML."""
    parser = ScriptSources()
    parser.feed(html)
    return parser.sources


def _https_url(url: str) -> str:
    """Reject any scheme other than https, including file."""
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError(f"refusing a URL that is not https: {url}")
    return url


def allowed_url(url: str, origin_host: str) -> str:
    """Return ``url`` when it is https on the origin host."""
    checked = _https_url(url)
    if urlsplit(checked).hostname != origin_host:
        raise ValueError(
            f"refusing a URL whose host is not the origin host {origin_host}: {url}"
        )
    return checked


def chunk_urls(text: str, origin: str) -> list[str]:
    """Return absolute chunk URLs named by HTML or a build manifest."""
    found: list[str] = []
    for path in _JS_PATH.findall(text):
        if path.startswith("static/"):
            path = "/_next/" + path
        found.append(urljoin(origin, path))
    return found


def manifest_urls(html: str, origin: str) -> list[str]:
    """Return ``_buildManifest.js`` URLs named by a page."""
    return [urljoin(origin, path) for path in _MANIFEST_PATH.findall(html)]


def _pages(origin: str) -> list[str]:
    root = origin if origin.endswith("/") else f"{origin}/"
    return [origin, *[urljoin(root, path) for path in SEARCH_PAGE_PATHS]]


def _open_request(
    request: urllib.request.Request,
    timeout: int,
    origin_host: str,
) -> object:
    opener = urllib.request.build_opener(HttpsOnlyRedirectHandler(origin_host))
    return opener.open(request, timeout=timeout)


def _read_url(url: str, origin_host: str) -> str:
    request = urllib.request.Request(
        allowed_url(url, origin_host),
        headers={"User-Agent": "siutindei-bundle-check"},
    )
    # The URL is https and on the origin host. The opener refuses any other redirect.
    # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
    with _open_request(request, TIMEOUT_SECONDS, origin_host) as response:  # nosec B310
        payload = response.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise ValueError(f"response exceeded {MAX_BYTES} bytes: {url}")
    return payload.decode("utf-8", errors="replace")


def _scan(url: str, text: str, failed: list[str]) -> None:
    found = bundle_offenders(text)
    if found:
        failed.append(f"check failed: {url} contains {', '.join(found)}")


def check_origin(origin: str) -> int:
    """Download the origin, search pages, and manifest chunks."""
    try:
        host = urlsplit(_https_url(origin)).hostname or ""
    except ValueError as exc:
        print(f"check failed: could not read {origin}: {exc}", file=sys.stderr)
        return 1
    pages: list[str] = []
    bundles: list[str] = []
    manifests: list[str] = []
    try:
        for page in _pages(origin):
            html = _read_url(page, host)
            pages.append(page)
            bundles.extend(urljoin(page, src) for src in script_urls(html))
            bundles.extend(chunk_urls(html, origin))
            manifests.extend(manifest_urls(html, origin))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"check failed: could not read {origin}: {exc}", file=sys.stderr)
        return 1
    seen: set[str] = set()
    failed: list[str] = []
    try:
        for manifest in manifests:
            if manifest in seen:
                continue
            seen.add(manifest)
            text = _read_url(manifest, host)
            _scan(manifest, text, failed)
            bundles.extend(chunk_urls(text, origin))
        unique_bundles = []
        for url in bundles:
            if url in seen:
                continue
            seen.add(url)
            unique_bundles.append(url)
        if not unique_bundles and not manifests:
            print(f"check failed: no JavaScript bundle in {origin}", file=sys.stderr)
            return 1
        for url in unique_bundles:
            text = _read_url(url, host)
            _scan(url, text, failed)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"check failed: could not read {origin}: {exc}", file=sys.stderr)
        return 1
    for line in failed:
        print(line, file=sys.stderr)
    if failed:
        return 1
    print(f"check ok: {len(seen)} bundle(s) at {origin} across {len(pages)} page(s)")
    return 0


def main() -> int:
    origin = os.environ.get(ORIGIN_ENV, "").strip()
    if not origin:
        print(f"check skipped: {ORIGIN_ENV} is unset")
        return 0
    return check_origin(origin)


if __name__ == "__main__":
    sys.exit(main())
