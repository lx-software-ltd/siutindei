#!/usr/bin/env python3
"""Fail if a live public-site bundle still names a removed path.

Reads ``PUBLIC_WWW_SITE_ORIGIN``. When that variable is unset, the check
prints that it was skipped and exits 0. Otherwise it downloads the origin
HTML, follows each JavaScript bundle URL, and exits 1 if a bundle contains
``/v1/activities/search`` or ``/www/``.

The script only reads HTTP. It does not call AWS.
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin

ORIGIN_ENV = "PUBLIC_WWW_SITE_ORIGIN"
REMOVED_PATHS = ("/v1/activities/search", "/www/")
TIMEOUT_SECONDS = 20


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


def bundle_offenders(bundle: str) -> tuple[str, ...]:
    """Return removed paths that appear in a bundle string."""
    return tuple(path for path in REMOVED_PATHS if path in bundle)


def script_urls(html: str) -> list[str]:
    """Return JavaScript bundle URLs referenced by HTML."""
    parser = ScriptSources()
    parser.feed(html)
    return parser.sources


def _read_url(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "siutindei-bundle-check"},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", errors="replace")


def check_origin(origin: str) -> int:
    """Download the origin and fail when a bundle names a removed path."""
    try:
        html = _read_url(origin)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"check failed: could not read {origin}: {exc}", file=sys.stderr)
        return 1
    urls = [urljoin(origin, src) for src in script_urls(html)]
    if not urls:
        print(f"check failed: no JavaScript bundle in {origin}", file=sys.stderr)
        return 1
    failed = False
    for url in urls:
        try:
            bundle = _read_url(url)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            print(f"check failed: could not read {url}: {exc}", file=sys.stderr)
            return 1
        found = bundle_offenders(bundle)
        if found:
            failed = True
            print(
                f"check failed: {url} contains {', '.join(found)}",
                file=sys.stderr,
            )
    if failed:
        return 1
    print(f"check ok: {len(urls)} bundle(s) at {origin}")
    return 0


def main() -> int:
    origin = os.environ.get(ORIGIN_ENV, "").strip()
    if not origin:
        print(f"check skipped: {ORIGIN_ENV} is unset")
        return 0
    return check_origin(origin)


if __name__ == "__main__":
    sys.exit(main())
