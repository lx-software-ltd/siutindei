"""Organization media upload helpers."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

from app.api.admin_request import _parse_body, _parse_uuid, _require_env
from app.exceptions import ValidationError
from app.services.aws_clients import get_s3_client
from app.utils import json_response


def _handle_organization_media(
    event: Mapping[str, Any],
    method: str,
    organization_id: str | None,
) -> dict[str, Any]:
    """Handle organization media uploads and deletions."""
    if not organization_id:
        raise ValidationError("organization id is required", field="id")

    org_uuid = _parse_uuid(organization_id)

    if method == "POST":
        return _handle_media_upload(event, org_uuid)
    if method == "DELETE":
        return _handle_media_delete(event, org_uuid)
    return json_response(405, {"error": "Method not allowed"}, event=event)


def _handle_media_upload(
    event: Mapping[str, Any],
    organization_id: UUID,
) -> dict[str, Any]:
    """Create a presigned URL for an organization media file."""
    body = _parse_body(event)
    if isinstance(body, dict):
        file_name = body.get("file_name")
        content_type = body.get("content_type")
    else:
        file_name = None
        content_type = None

    if not file_name:
        raise ValidationError("file_name is required", field="file_name")
    if not content_type:
        raise ValidationError("content_type is required", field="content_type")
    if not str(content_type).startswith("image/"):
        raise ValidationError(
            "content_type must be an image",
            field="content_type",
        )

    bucket = _require_env("ORGANIZATION_MEDIA_BUCKET")
    object_key = _build_media_key(str(organization_id), str(file_name))
    base_url = _media_base_url()

    client = get_s3_client()
    upload_url = client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": bucket,
            "Key": object_key,
            "ContentType": str(content_type),
        },
        ExpiresIn=900,
    )

    return json_response(
        200,
        {
            "upload_url": upload_url,
            "media_url": f"{base_url}/{object_key}",
            "object_key": object_key,
            "expires_in": 900,
        },
        event=event,
    )


def _handle_media_delete(
    event: Mapping[str, Any],
    organization_id: UUID,
) -> dict[str, Any]:
    """Delete an organization media file from S3."""
    body = _parse_body(event)
    if isinstance(body, dict):
        object_key = body.get("object_key")
        media_url = body.get("media_url")
    else:
        object_key = None
        media_url = None

    if object_key:
        key = str(object_key)
    elif media_url:
        key = _extract_media_key(str(media_url))
    else:
        raise ValidationError(
            "media_url or object_key is required",
            field="media_url",
        )

    _validate_media_key(str(organization_id), key)
    bucket = _require_env("ORGANIZATION_MEDIA_BUCKET")

    client = get_s3_client()
    client.delete_object(Bucket=bucket, Key=key)

    return json_response(204, {}, event=event)


def _build_media_key(organization_id: str, file_name: str) -> str:
    """Build an S3 object key for a media file."""
    cleaned = _sanitize_media_filename(file_name)
    base, extension = os.path.splitext(cleaned)
    trimmed_base = base[:40].strip("_") or "image"
    suffix = extension.lower() if extension else ""
    unique = uuid4().hex
    return f"organizations/{organization_id}/{unique}-{trimmed_base}{suffix}"


def _sanitize_media_filename(file_name: str) -> str:
    """Normalize user-supplied filenames."""
    trimmed = file_name.strip() or "image"
    return re.sub(r"[^A-Za-z0-9._-]", "_", trimmed)


def _media_base_url() -> str:
    """Return the base URL for organization media."""
    return _require_env("ORGANIZATION_MEDIA_BASE_URL").rstrip("/")


def _extract_media_key(media_url: str) -> str:
    """Extract an object key from a media URL."""
    base_url = _media_base_url()
    parsed_url = urlparse(media_url)
    base_parsed = urlparse(base_url)

    if parsed_url.netloc != base_parsed.netloc:
        raise ValidationError(
            "media_url is not hosted in the images bucket",
            field="media_url",
        )

    key = parsed_url.path.lstrip("/")
    if not key:
        raise ValidationError(
            "media_url must include an object key",
            field="media_url",
        )

    return key


def _validate_media_key(organization_id: str, object_key: str) -> None:
    """Ensure the object key matches the organization prefix."""
    prefix = f"organizations/{organization_id}/"
    if not object_key.startswith(prefix):
        raise ValidationError(
            "media_url does not match the organization",
            field="media_url",
        )
