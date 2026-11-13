"""Catalogue digests and IndexNow pings for the daily public website refresh."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "deploy"))

import catalogue_snapshot_digests
import indexnow

ORIGIN = "https://example.com"
FAKE_KEY = "abcdef1234567890"
FIXTURE = (
    ROOT / "apps" / "public_www" / "tests" / "fixtures" / "catalogue-snapshot.json"
)
SITEMAP = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
<url><loc>{ORIGIN}/en/</loc></url>
<url><loc>{ORIGIN}/zh-HK/</loc></url>
<url><loc>{ORIGIN}/en/about/</loc></url>
<url><loc>{ORIGIN}/en/activities/</loc></url>
<url><loc>{ORIGIN}/en/activities/arts/</loc></url>
<url><loc>{ORIGIN}/en/activity/a1/</loc></url>
<url><loc>{ORIGIN}/zh-HK/activity/a1/</loc></url>
</urlset>
"""


def _snapshot() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_digests_ignore_generated_at_and_row_order() -> None:
    snapshot = _snapshot()
    later = {
        **snapshot,
        "generated_at": "2099-01-01T00:00:00+00:00",
        "items": list(reversed(snapshot["items"])),
    }

    digests = catalogue_snapshot_digests.activity_digests(snapshot)

    assert digests == catalogue_snapshot_digests.activity_digests(later)
    assert len(digests) == len({item["activity"]["id"] for item in snapshot["items"]})


def test_digests_change_only_for_the_edited_activity() -> None:
    snapshot = _snapshot()
    edited = json.loads(json.dumps(snapshot))
    edited["items"][0]["activity"]["name"] = "Renamed class"
    edited_id = edited["items"][0]["activity"]["id"]

    before = catalogue_snapshot_digests.activity_digests(snapshot)
    after = catalogue_snapshot_digests.activity_digests(edited)

    assert indexnow.changed_activity_ids(before, after) == [edited_id]


def test_digest_file_is_byte_stable(tmp_path: Path) -> None:
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    assert catalogue_snapshot_digests.main([str(FIXTURE), str(first)]) == 0
    assert catalogue_snapshot_digests.main([str(FIXTURE), str(second)]) == 0
    assert first.read_bytes() == second.read_bytes()


def test_without_previous_digests_every_sitemap_url_is_sent() -> None:
    sitemap = indexnow.sitemap_urls(SITEMAP)

    assert indexnow.urls_to_submit(ORIGIN, sitemap, None, {"a1": "x"}) == sitemap
    assert len(sitemap) == 7


def test_changed_activities_send_their_pages_and_the_catalogue_pages() -> None:
    sitemap = indexnow.sitemap_urls(SITEMAP)

    urls = indexnow.urls_to_submit(
        ORIGIN, sitemap, {"a1": "old", "gone": "x"}, {"a1": "new", "a2": "y"}
    )

    assert urls == sorted(
        [
            f"{ORIGIN}/en/",
            f"{ORIGIN}/zh-HK/",
            f"{ORIGIN}/en/activities/",
            f"{ORIGIN}/en/activities/arts/",
            f"{ORIGIN}/en/activity/a1/",
            f"{ORIGIN}/zh-HK/activity/a1/",
            f"{ORIGIN}/en/activity/a2/",
            f"{ORIGIN}/zh-HK/activity/a2/",
            f"{ORIGIN}/en/activity/gone/",
            f"{ORIGIN}/zh-HK/activity/gone/",
        ]
    )
    assert indexnow.urls_to_submit(ORIGIN, sitemap, {"a1": "x"}, {"a1": "x"}) == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("abcdef12", "abcdef12"),
        (" abcd-ef12 ", "abcd-ef12"),
        ("short", None),
        ("bad key!", None),
        ("", None),
    ],
)
def test_valid_key(raw: str, expected: str | None) -> None:
    assert indexnow.valid_key(raw) == expected


def test_write_key_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INDEXNOW_KEY", FAKE_KEY)

    assert indexnow.main(["write-key", str(tmp_path)]) == 0
    assert (tmp_path / f"{FAKE_KEY}.txt").read_text(
        encoding="utf-8"
    ) == FAKE_KEY

    monkeypatch.setenv("INDEXNOW_KEY", "not a key")
    assert indexnow.main(["write-key", str(tmp_path)]) == 1

    monkeypatch.delenv("INDEXNOW_KEY")
    assert indexnow.main(["write-key", str(tmp_path / "missing")]) == 0


def test_ping_posts_changed_urls_and_never_fails_the_deploy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "sitemap.xml").write_text(SITEMAP, encoding="utf-8")
    previous, current = tmp_path / "previous.json", tmp_path / "current.json"
    previous.write_text(json.dumps({"a1": "old"}), encoding="utf-8")
    current.write_text(json.dumps({"a1": "new"}), encoding="utf-8")
    monkeypatch.setenv("INDEXNOW_KEY", FAKE_KEY)
    monkeypatch.setenv("NEXT_PUBLIC_SITE_ORIGIN", f"{ORIGIN}/")
    sent: list[dict] = []

    def fake_submit(origin: str, key: str, urls: list[str]) -> bool:
        sent.append({"origin": origin, "key": key, "urls": urls})
        return False

    monkeypatch.setattr(indexnow, "submit", fake_submit)

    code = indexnow.main(
        ["ping", str(tmp_path), "--previous", str(previous), "--current", str(current)]
    )

    assert code == 0
    assert sent[0]["origin"] == ORIGIN
    assert f"{ORIGIN}/en/activity/a1/" in sent[0]["urls"]
    assert f"{ORIGIN}/en/about/" not in sent[0]["urls"]


def test_submit_reports_http_errors_without_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(json.loads(request.data))
        raise indexnow.urllib.error.HTTPError(
            request.full_url, 422, "Unprocessable", {}, None
        )

    monkeypatch.setattr(indexnow.urllib.request, "urlopen", fake_urlopen)

    assert indexnow.submit(ORIGIN, FAKE_KEY, [f"{ORIGIN}/en/"]) is False
    assert requests == [
        {
            "host": "example.com",
            "key": FAKE_KEY,
            "keyLocation": f"{ORIGIN}/{FAKE_KEY}.txt",
            "urlList": [f"{ORIGIN}/en/"],
        }
    ]
