#!/usr/bin/env python3
"""Tell IndexNow search engines (Bing, Yandex, Naver, Seznam) which public
website pages changed after a production deploy.

Subcommands:

  write-key OUT_DIR
      Write OUT_DIR/<key>.txt so engines can verify the key. Does nothing
      when INDEXNOW_KEY is unset.

  ping OUT_DIR [--previous DIGESTS --current DIGESTS]
      Submit URLs from OUT_DIR/sitemap.xml. With both digest files (from
      catalogue_snapshot_digests.py) only the pages of activities that were
      added, changed, or removed are sent, plus the home and activities
      pages. Without them every sitemap URL is sent.

Env: INDEXNOW_KEY, and NEXT_PUBLIC_SITE_ORIGIN for ``ping``.

The key is public by design: engines fetch it from the site. Pinging never
fails a deploy; problems are reported as warnings.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

ENDPOINT = "https://api.indexnow.org/indexnow"
KEY_PATTERN = re.compile(r"^[A-Za-z0-9-]{8,128}$")
LOCALES = ("en", "zh-HK")
MAX_URLS_PER_REQUEST = 10_000
SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
CATALOGUE_PATH = re.compile(r"^/(en|zh-HK)/(activities/([^/]+/)?)?$")


def valid_key(raw: str | None) -> str | None:
    key = (raw or "").strip()
    return key if KEY_PATTERN.fullmatch(key) else None


def sitemap_urls(xml: str) -> list[str]:
    root = ElementTree.fromstring(xml)
    return [loc.text.strip() for loc in root.iter(f"{SITEMAP_NS}loc") if loc.text]


def changed_activity_ids(
    previous: dict[str, str], current: dict[str, str]
) -> list[str]:
    ids = set(previous) | set(current)
    return sorted(
        activity_id
        for activity_id in ids
        if previous.get(activity_id) != current.get(activity_id)
    )


def urls_to_submit(
    origin: str,
    sitemap: list[str],
    previous: dict[str, str] | None,
    current: dict[str, str] | None,
) -> list[str]:
    if previous is None or current is None:
        return sitemap
    changed = changed_activity_ids(previous, current)
    if not changed:
        return []
    activity_urls = [
        f"{origin}/{locale}/activity/{activity_id}/"
        for activity_id in changed
        for locale in LOCALES
    ]
    catalogue_urls = [
        url for url in sitemap if CATALOGUE_PATH.fullmatch(urlsplit(url).path)
    ]
    return sorted(set(activity_urls) | set(catalogue_urls))


def submit(
    origin: str,
    key: str,
    urls: list[str],
    *,
    endpoint: str = ENDPOINT,
    timeout: float = 20.0,
) -> bool:
    host = urlsplit(origin).hostname or ""
    ok = True
    for start in range(0, len(urls), MAX_URLS_PER_REQUEST):
        batch = urls[start : start + MAX_URLS_PER_REQUEST]
        body = json.dumps(
            {
                "host": host,
                "key": key,
                "keyLocation": f"{origin}/{key}.txt",
                "urlList": batch,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                print(
                    f"IndexNow accepted {len(batch)} URL(s) with HTTP {response.status}."
                )
        except urllib.error.HTTPError as error:
            print(
                f"::warning::IndexNow returned HTTP {error.code} for {len(batch)} URL(s)."
            )
            ok = False
        except (urllib.error.URLError, TimeoutError) as error:
            print(f"::warning::IndexNow request failed: {error}.")
            ok = False
    return ok


def _read_digests(path: str | None) -> dict[str, str] | None:
    if not path:
        return None
    file = Path(path)
    if not file.is_file() or file.stat().st_size == 0:
        return None
    return json.loads(file.read_text(encoding="utf-8"))


def write_key(out_dir: Path) -> int:
    raw = os.environ.get("INDEXNOW_KEY", "")
    if not raw.strip():
        print("INDEXNOW_KEY is unset. No IndexNow key file written.")
        return 0
    key = valid_key(raw)
    if key is None:
        print(
            "INDEXNOW_KEY must be 8 to 128 letters, digits, or hyphens.",
            file=sys.stderr,
        )
        return 1
    (out_dir / f"{key}.txt").write_text(key, encoding="utf-8")
    print(f"Wrote IndexNow key file {key}.txt.")
    return 0


def ping(out_dir: Path, previous_path: str | None, current_path: str | None) -> int:
    key = valid_key(os.environ.get("INDEXNOW_KEY"))
    origin = os.environ.get("NEXT_PUBLIC_SITE_ORIGIN", "").strip().rstrip("/")
    if key is None or not origin:
        print("INDEXNOW_KEY or NEXT_PUBLIC_SITE_ORIGIN is unset. Skipping IndexNow.")
        return 0
    sitemap_file = out_dir / "sitemap.xml"
    if not sitemap_file.is_file():
        print(f"::warning::{sitemap_file} is missing. Skipping IndexNow.")
        return 0
    sitemap = sitemap_urls(sitemap_file.read_text(encoding="utf-8"))
    urls = urls_to_submit(
        origin, sitemap, _read_digests(previous_path), _read_digests(current_path)
    )
    if not urls:
        print("No catalogue changes to submit to IndexNow.")
        return 0
    submit(origin, key, urls)
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="IndexNow key file and ping for the public website."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    write = commands.add_parser("write-key")
    write.add_argument("out_dir", type=Path)
    send = commands.add_parser("ping")
    send.add_argument("out_dir", type=Path)
    send.add_argument("--previous")
    send.add_argument("--current")
    args = parser.parse_args(argv)
    if args.command == "write-key":
        return write_key(args.out_dir)
    return ping(args.out_dir, args.previous, args.current)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
