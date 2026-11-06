"""Publish and delete leaflet objects in the media bucket.

Pending files live under ``incoming/`` or ``rasters/`` and carry the
``leaflet-pending`` tag. A picture becomes public only when its proposal
is applied. Rasters and unused uploads are deleted.
"""

from __future__ import annotations

import os
from typing import Any
from uuid import UUID

from botocore.exceptions import ClientError

from app.services.enrichment.leaflet import leaflet_prefix, valid_leaflet_key
from app.utils.logging import get_logger

logger = get_logger(__name__)

PENDING_TAG = "leaflet-pending=1"
PENDING_TAG_XML = (
    "<Tagging><TagSet><Tag><Key>leaflet-pending</Key>"
    "<Value>1</Value></Tag></TagSet></Tagging>"
)
_INCOMING = "incoming/"
_RASTERS = "rasters/"


def presign_post(key: str, content_type: str, max_bytes: int) -> dict[str, str | dict]:
    """Presigned POST. The policy rejects an empty or oversized body."""
    from app.services.aws_clients import get_s3_client

    signed = get_s3_client().generate_presigned_post(
        Bucket=_bucket(),
        Key=key,
        Fields={"Content-Type": content_type, "tagging": PENDING_TAG_XML},
        Conditions=[
            {"Content-Type": content_type},
            {"tagging": PENDING_TAG_XML},
            ["content-length-range", 1, max_bytes],
        ],
        ExpiresIn=900,
    )
    fields = signed.get("fields") if isinstance(signed, dict) else None
    upload_fields = (
        {str(name): str(value) for name, value in fields.items()}
        if isinstance(fields, dict)
        else {}
    )
    url = signed.get("url") if isinstance(signed, dict) else ""
    return {"upload_url": str(url or ""), "upload_fields": upload_fields}


def presign_leaflet_get(key: str) -> str:
    """Short-lived read URL for the vision model. The object stays private."""
    from app.services.aws_clients import get_s3_client

    return str(
        get_s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": _bucket(), "Key": key},
            ExpiresIn=900,
        )
    )


def publish_leaflet(org_id: UUID | str, key: str) -> str | None:
    """Public URL for a leaflet. An incoming object is copied out first."""
    if not valid_leaflet_key(org_id, key):
        return None
    base = os.getenv("ORGANIZATION_MEDIA_BASE_URL", "").rstrip("/")
    if not base:
        return None
    marker = f"{leaflet_prefix(org_id)}{_INCOMING}"
    if not key.startswith(marker):
        return f"{base}/{key}"
    public_key = f"{leaflet_prefix(org_id)}{key[len(marker) :]}"
    _copy_public(key, public_key)
    _delete_key(key)
    return f"{base}/{public_key}"


def discard_request(org_id: UUID | str, raw: object) -> None:
    """Delete uploaded keys when a run never starts."""
    discard_keys(org_id, _object_keys(raw))


def discard_keys(org_id: UUID | str, keys: list[str]) -> None:
    for key in keys:
        if _deletable(org_id, key):
            _delete_key(key)


def release_leaflet_run(run: Any) -> None:
    """Delete pending files for a run that will not be applied."""
    discard_keys(run.org_id, [key for key in _keys_on_run(run) if _pending(key)])


def release_rasters(org_id: UUID | str, pages: list[Any]) -> None:
    discard_keys(org_id, [key for key in _page_keys(pages) if f"/{_RASTERS}" in key])


def release_finished_leaflet(run: Any) -> None:
    """Drop rasters and incoming files that are not a picture proposal."""
    keep = {
        str(media.get("object_key") or "")
        for page in list(run.pages or [])
        if isinstance(page, dict)
        for media in [page.get("leaflet_media")]
        if isinstance(media, dict)
    }
    drop = [
        key
        for key in _keys_on_run(run)
        if f"/{_RASTERS}" in key or (f"/{_INCOMING}" in key and key not in keep)
    ]
    discard_keys(run.org_id, drop)


def _copy_public(source: str, public_key: str) -> None:
    from app.services.aws_clients import get_s3_client

    bucket = _bucket()
    client = get_s3_client()
    client.copy_object(
        Bucket=bucket,
        Key=public_key,
        CopySource={"Bucket": bucket, "Key": source},
        MetadataDirective="COPY",
        TaggingDirective="COPY",
    )
    try:
        client.delete_object_tagging(Bucket=bucket, Key=public_key)
    except ClientError:
        logger.info("Leaflet publish left the pending tag", extra={"key": public_key})


def _delete_key(key: str) -> None:
    from app.services.aws_clients import get_s3_client

    try:
        get_s3_client().delete_object(Bucket=_bucket(), Key=key)
    except ClientError:
        logger.info("Leaflet object was not deleted", extra={"key": key})


def _bucket() -> str:
    from app.exceptions import ValidationError

    value = os.getenv("ORGANIZATION_MEDIA_BUCKET", "").strip()
    if not value:
        raise ValidationError("media bucket is not configured", field="leaflet")
    return value


def _deletable(org_id: UUID | str, key: str) -> bool:
    if valid_leaflet_key(org_id, key):
        return True
    prefix = f"{leaflet_prefix(org_id)}{_RASTERS}"
    if not key.startswith(prefix):
        return False
    name = key[len(prefix) :]
    return bool(name) and "/" not in name and ".." not in name


def _pending(key: str) -> bool:
    return f"/{_INCOMING}" in key or f"/{_RASTERS}" in key


def _keys_on_run(run: Any) -> list[str]:
    keys = _page_keys(list(run.pages or []))
    for item in list(run.leaflet_items or []):
        if isinstance(item, dict) and isinstance(item.get("key"), str):
            keys.append(item["key"])
    return keys


def _page_keys(pages: list[Any]) -> list[str]:
    keys: list[str] = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        keys.extend(
            key for key in page.get("vision_keys") or [] if isinstance(key, str) and key
        )
        media = page.get("leaflet_media")
        if isinstance(media, dict) and isinstance(media.get("object_key"), str):
            keys.append(media["object_key"])
    return keys


def _object_keys(raw: object) -> list[str]:
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict) and isinstance(raw.get("items"), list):
        items = list(raw["items"])
    elif isinstance(raw, dict):
        items = [raw]
    else:
        return []
    return [
        item["object_key"]
        for item in items
        if isinstance(item, dict) and isinstance(item.get("object_key"), str)
    ]
