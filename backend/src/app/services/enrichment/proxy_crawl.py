"""Crawl and image copy, running inside the out-of-VPC proxy."""

from __future__ import annotations

import hashlib
import os
import time
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import urljoin

from app.services.enrichment.constants import COPYRIGHT_NOTICE, MAX_IMAGE_BYTES
from app.services.enrichment.fetch import FetchResult, crawl_site, fetch_public
from app.services.enrichment.guard import CrawlError, check_fetch_url, validate_seed_url

_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


def handle_crawl_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Proxy entry for type=crawl. Returns the proxy envelope."""
    op = str(event.get("op") or "site")
    try:
        if op == "image":
            return {"result": copy_image(event)}
        return {"result": crawl_requested(event)}
    except CrawlError as exc:
        return {"error": {"code": "CrawlRefused", "message": str(exc)}}


def crawl_requested(event: Mapping[str, Any]) -> dict[str, Any]:
    seed = validate_seed_url(str(event.get("seed_url") or ""))
    max_pages = _clamp(event.get("max_pages"), 6, 1, 8)
    max_bytes = _clamp(event.get("max_page_bytes"), 1_000_000, 10_000, 2_000_000)
    budget = _clamp(event.get("time_budget_seconds"), 20, 5, 20)
    crawled = crawl_site(
        seed,
        max_pages=max_pages,
        max_page_bytes=max_bytes,
        time_budget_seconds=budget,
    )
    pages = []
    for page in crawled.get("pages") or []:
        if isinstance(page, dict):
            pages.append(_public_page(page))
    return {
        "status": crawled.get("status"),
        "error": crawled.get("error") or "",
        "pages": pages,
        "pages_fetched": crawled.get("pages_fetched") or 0,
        "bytes_fetched": crawled.get("bytes_fetched") or 0,
    }


def copy_image(event: Mapping[str, Any]) -> dict[str, Any]:
    """Download one image and store it under the organization's prefix."""
    url = str(event.get("url") or "").strip()
    org_id = str(event.get("org_id") or "").strip()
    check_fetch_url(url)
    if not _uuidish(org_id):
        raise CrawlError("org_id is not valid")
    result = _follow_image(url)
    if result.truncated:
        raise CrawlError("image is too large")
    ctype = result.content_type.split(";", 1)[0].strip().lower()
    ext = _IMAGE_TYPES.get(ctype)
    if ext is None:
        raise CrawlError("image content type is not allowed")
    if len(result.body) > MAX_IMAGE_BYTES:
        raise CrawlError("image is too large")
    digest = hashlib.sha256(result.body).hexdigest()[:16]
    key = f"organizations/{org_id}/enrichment/{digest}.{ext}"
    bucket = os.getenv("ORGANIZATION_MEDIA_BUCKET", "").strip()
    base = os.getenv("ORGANIZATION_MEDIA_BASE_URL", "").rstrip("/")
    if not bucket or not base:
        raise CrawlError("media bucket is not configured")
    from app.services.aws_clients import get_client

    get_client("s3").put_object(
        Bucket=bucket,
        Key=key,
        Body=result.body,
        ContentType=ctype,
        Metadata={
            "source-url": url[:1024],
            "copyright": COPYRIGHT_NOTICE,
            "copied-at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )
    return {
        "url": f"{base}/{key}",
        "key": key,
        "copyright_notice": COPYRIGHT_NOTICE,
        "source_url": url,
    }


def _follow_image(url: str) -> FetchResult:
    current = url
    deadline = time.monotonic() + 15
    for _ in range(4):
        check_fetch_url(current)
        try:
            result = fetch_public(
                current, MAX_IMAGE_BYTES, timeout=10, deadline=deadline
            )
        except TimeoutError as exc:
            raise CrawlError("image download timed out") from exc
        if result.status in {301, 302, 303, 307, 308} and result.location:
            current = urljoin(result.url or current, result.location)
            continue
        if result.status >= 400:
            raise CrawlError(f"image HTTP {result.status}")
        return result
    raise CrawlError("too many redirects")


def _public_page(page: dict[str, Any]) -> dict[str, Any]:
    """Drop the raw HTML. Keep the text the model and the quote check need."""
    return {
        "url": page.get("url"),
        "final_url": page.get("final_url") or page.get("url"),
        "status": page.get("status"),
        "title": page.get("title"),
        "lang": page.get("lang"),
        "text": page.get("text"),
        "jsonld": page.get("jsonld"),
        "jsonld_raw": page.get("jsonld_raw"),
        "og": page.get("og"),
        "images": page.get("images"),
        "links": page.get("links"),
        "social": page.get("social"),
        "mailtos": page.get("mailtos"),
        "tels": page.get("tels"),
    }


def _clamp(value: object, default: int, low: int, high: int) -> int:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return min(high, max(low, number))


def _uuidish(value: str) -> bool:
    parts = value.split("-")
    return len(parts) == 5 and all(part.isalnum() for part in parts)
