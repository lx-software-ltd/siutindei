"""Catalogue snapshot that the public website build pre-renders from.

The snapshot is every page of the public search response for the
configured area scope, so it holds exactly the fields that the public
search API already returns. It is written to a private bucket and only
rewritten when its content changes.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from botocore.exceptions import ClientError

from app.api.schemas import dump_search_response
from app.api.search import fetch_search_response
from app.api.search_page import parse_cursor
from app.db.queries import ActivitySearchFilters
from app.services.aws_clients import get_s3_client
from app.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

SNAPSHOT_SCHEMA_VERSION = 1
SNAPSHOT_PAGE_SIZE = 100
SNAPSHOT_MAX_PAGES = 100
DEFAULT_SNAPSHOT_KEY = "public-www/catalogue-snapshot.json"
_DIGEST_METADATA_KEY = "content-sha256"
_MISSING_OBJECT_CODES = frozenset({"404", "NoSuchKey", "NotFound"})


class CatalogueSnapshotError(RuntimeError):
    """The snapshot could not be built or published."""


def build_catalogue_snapshot(
    *,
    page_size: int = SNAPSHOT_PAGE_SIZE,
    max_pages: int = SNAPSHOT_MAX_PAGES,
) -> dict[str, Any]:
    """Every page of the public search for the configured area scope."""

    filters = ActivitySearchFilters(
        limit=page_size, view="full", include_incomplete=True
    )
    items: list[dict[str, Any]] = []
    area_scope: list[str] | None = None
    for page_number in range(max_pages):
        response = fetch_search_response(filters)
        payload = dump_search_response(
            response, "full", include_area_scope=page_number == 0
        )
        if page_number == 0:
            area_scope = payload.get("area_scope")
        items.extend(payload["items"])
        if response.next_cursor is None:
            return {
                "schema_version": SNAPSHOT_SCHEMA_VERSION,
                "area_scope": area_scope,
                "items": items,
            }
        filters = replace(filters, cursor=parse_cursor(response.next_cursor))
    raise CatalogueSnapshotError(
        f"Catalogue snapshot exceeded {max_pages} pages of {page_size} rows"
    )


def _serialize(document: Mapping[str, Any]) -> bytes:
    return json.dumps(
        document, default=str, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _stored_digest(s3: Any, bucket: str, key: str) -> str | None:
    try:
        head = s3.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in _MISSING_OBJECT_CODES:
            return None
        raise
    return (head.get("Metadata") or {}).get(_DIGEST_METADATA_KEY)


def publish_catalogue_snapshot(
    s3: Any,
    bucket: str,
    key: str,
    *,
    now: datetime,
) -> dict[str, Any]:
    """Write the snapshot when its content differs from the stored object."""

    snapshot = build_catalogue_snapshot()
    digest = hashlib.sha256(_serialize(snapshot)).hexdigest()
    result = {"items": len(snapshot["items"]), "digest": digest, "written": False}
    if _stored_digest(s3, bucket, key) == digest:
        logger.info("Catalogue snapshot unchanged", extra=result)
        return result

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=_serialize({**snapshot, "generated_at": now.isoformat()}),
        ContentType="application/json",
        CacheControl="no-store",
        Metadata={_DIGEST_METADATA_KEY: digest},
    )
    result["written"] = True
    logger.info("Catalogue snapshot written", extra=result)
    return result


def lambda_handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """EventBridge entrypoint. The event body is not used."""

    bucket = os.environ.get("CATALOGUE_SNAPSHOT_BUCKET", "").strip()
    if not bucket:
        raise CatalogueSnapshotError("CATALOGUE_SNAPSHOT_BUCKET is not set")
    key = os.environ.get("CATALOGUE_SNAPSHOT_KEY", "").strip() or DEFAULT_SNAPSHOT_KEY
    return publish_catalogue_snapshot(
        get_s3_client(), bucket, key, now=datetime.now(UTC)
    )
