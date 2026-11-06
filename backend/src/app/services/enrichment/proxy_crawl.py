"""Crawl and image copy, running inside the out-of-VPC proxy."""

from __future__ import annotations

import hashlib
import os
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

from app.services.enrichment.constants import (
    COPYRIGHT_NOTICE,
    CRAWL_TIME_BUDGET_SECONDS,
    LEAFLET_COPYRIGHT_NOTICE,
    MAX_IMAGE_BYTES,
    MAX_PDF_BYTES,
)
from app.services.enrichment.fetch import FetchResult, crawl_site, fetch_public
from app.services.enrichment.guard import CrawlError, check_fetch_url, validate_seed_url

# Twenty pages must fit the 6 MB Lambda response with room to spare.
_PAGE_JSONLD_BLOCKS = 5

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
        if op == "leaflet":
            return {"result": store_leaflet(event)}
        return {"result": crawl_requested(event)}
    except CrawlError as exc:
        return {"error": {"code": "CrawlRefused", "message": str(exc)}}


def crawl_requested(event: Mapping[str, Any]) -> dict[str, Any]:
    seed = validate_seed_url(str(event.get("seed_url") or ""))
    max_pages = _clamp(event.get("max_pages"), 12, 1, 20)
    max_bytes = _clamp(event.get("max_page_bytes"), 1_000_000, 10_000, 2_000_000)
    budget = _clamp(
        event.get("time_budget_seconds"),
        CRAWL_TIME_BUDGET_SECONDS,
        5,
        CRAWL_TIME_BUDGET_SECONDS,
    )
    crawled = crawl_site(
        seed,
        max_pages=max_pages,
        max_page_bytes=max_bytes,
        time_budget_seconds=budget,
    )
    raw_pages = crawled.get("pages")
    page_list = raw_pages if isinstance(raw_pages, list) else []
    pages = [_public_page(page) for page in page_list if isinstance(page, dict)]
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
            "copied-at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )
    return {
        "url": f"{base}/{key}",
        "key": key,
        "copyright_notice": COPYRIGHT_NOTICE,
        "source_url": url,
    }


def store_leaflet(event: Mapping[str, Any]) -> dict[str, Any]:
    """Download one public leaflet and store it under the organization."""
    url = str(event.get("url") or "").strip()
    org_id = str(event.get("org_id") or "").strip()
    check_fetch_url(url)
    if not _uuidish(org_id):
        raise CrawlError("org_id is not valid")
    result = _follow_public(
        url,
        MAX_PDF_BYTES,
        timeout_message="The leaflet could not be read",
    )
    if result.truncated:
        raise CrawlError("The leaflet is too large")
    from app.services.enrichment.leaflet import sniff_leaflet

    sniffed = sniff_leaflet(result.body)
    if sniffed is None:
        raise CrawlError("leaflet must be a picture or a PDF")
    ext, ctype = sniffed
    limit = MAX_PDF_BYTES if ext == "pdf" else MAX_IMAGE_BYTES
    if len(result.body) > limit:
        raise CrawlError("The leaflet is too large")
    digest = hashlib.sha256(result.body).hexdigest()[:16]
    key = f"organizations/{org_id}/enrichment/leaflets/incoming/{digest}.{ext}"
    from app.services.enrichment.leaflet_objects import PENDING_TAG

    stored = _put_media(
        key,
        result.body,
        ctype,
        source_url=url,
        copyright_notice=LEAFLET_COPYRIGHT_NOTICE,
        tagging=PENDING_TAG,
    )
    return {
        "url": stored,
        "key": key,
        "content_type": ctype,
        "bytes": len(result.body),
    }


def _follow_image(url: str) -> FetchResult:
    return _follow_public(
        url,
        MAX_IMAGE_BYTES,
        timeout_message="image download timed out",
        http_message="image HTTP {status}",
        deadline_seconds=15,
    )


def _follow_public(
    url: str,
    max_bytes: int,
    *,
    timeout_message: str,
    http_message: str = "leaflet HTTP {status}",
    deadline_seconds: int = 20,
) -> FetchResult:
    current = url
    deadline = time.monotonic() + deadline_seconds
    for _ in range(4):
        check_fetch_url(current)
        try:
            result = fetch_public(current, max_bytes, timeout=10, deadline=deadline)
        except TimeoutError as exc:
            raise CrawlError(timeout_message) from exc
        if result.status in {301, 302, 303, 307, 308} and result.location:
            current = urljoin(result.url or current, result.location)
            continue
        if result.status >= 400:
            raise CrawlError(http_message.format(status=result.status))
        return result
    raise CrawlError("too many redirects")


def _put_media(
    key: str,
    body: bytes,
    content_type: str,
    *,
    source_url: str,
    copyright_notice: str,
    tagging: str | None = None,
) -> str:
    bucket = os.getenv("ORGANIZATION_MEDIA_BUCKET", "").strip()
    base = os.getenv("ORGANIZATION_MEDIA_BASE_URL", "").rstrip("/")
    if not bucket or not base:
        raise CrawlError("media bucket is not configured")
    from app.services.aws_clients import get_client

    put: dict[str, Any] = {
        "Bucket": bucket,
        "Key": key,
        "Body": body,
        "ContentType": content_type,
        "Metadata": {
            "source-url": source_url[:1024],
            "copyright": copyright_notice,
            "copied-at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }
    if tagging:
        put["Tagging"] = tagging
    get_client("s3").put_object(**put)
    return f"{base}/{key}"


def _public_page(page: dict[str, Any]) -> dict[str, Any]:
    """Drop the raw HTML. Keep the text the model and the quote check need."""
    return {
        "url": page.get("url"),
        "final_url": page.get("final_url") or page.get("url"),
        "status": page.get("status"),
        "title": page.get("title"),
        "lang": page.get("lang"),
        "text": page.get("text"),
        "jsonld": _first(page.get("jsonld"), _PAGE_JSONLD_BLOCKS),
        "jsonld_raw": _first(page.get("jsonld_raw"), _PAGE_JSONLD_BLOCKS),
        "og": page.get("og"),
        "images": page.get("images"),
        "links": page.get("links"),
        "social": page.get("social"),
        "mailtos": page.get("mailtos"),
        "tels": page.get("tels"),
    }


def _first(value: object, count: int) -> list[Any]:
    return list(value[:count]) if isinstance(value, list) else []


def _clamp(value: object, default: int, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return default
    try:
        number = int(value)
    except ValueError:
        return default
    return min(high, max(low, number))


def _uuidish(value: str) -> bool:
    parts = value.split("-")
    return len(parts) == 5 and all(part.isalnum() for part in parts)
