"""S3 reads and presigned downloads for admin import files."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from botocore.exceptions import ClientError

from app.api.admin_imports_utils import sanitize_filename, validate_object_key
from app.api.admin_request import _require_env
from app.exceptions import ValidationError
from app.services.aws_clients import get_s3_client
from app.utils.logging import get_logger

logger = get_logger(__name__)

IMPORT_PREFIX = "admin/imports"
EXPORT_PREFIX = "admin/exports"
PRESIGN_EXPIRY_SECONDS = 900
HISTORY_PRESIGN_EXPIRY_SECONDS = 3600
IMPORT_OBJECT_RETENTION = timedelta(days=7)
OBJECT_KEY_UNIQUE_PREFIX = re.compile(r"^[0-9a-f]{32}-", re.IGNORECASE)


def load_import_payload(object_key: str) -> dict[str, Any]:
    bucket = _require_env("ADMIN_IMPORT_EXPORT_BUCKET")
    client = get_s3_client()
    try:
        response = client.get_object(Bucket=bucket, Key=object_key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code == "NoSuchKey":
            raise ValidationError(
                "object_key not found",
                field="object_key",
            ) from exc
        raise
    body = response["Body"].read().decode("utf-8")
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValidationError("Import file must be valid JSON") from exc


def write_export_payload(object_key: str, payload: dict[str, Any]) -> None:
    bucket = _require_env("ADMIN_IMPORT_EXPORT_BUCKET")
    client = get_s3_client()
    body = json.dumps(payload, ensure_ascii=True, default=str).encode("utf-8")
    client.put_object(
        Bucket=bucket,
        Key=object_key,
        Body=body,
        ContentType="application/json",
    )


def import_download_filename(object_key: str) -> str:
    name = object_key.rsplit("/", 1)[-1] or "import.json"
    stripped = OBJECT_KEY_UNIQUE_PREFIX.sub("", name, count=1)
    return stripped or name


def import_object_is_available(created_at: Any) -> bool:
    when = _as_aware_datetime(created_at)
    if when is None:
        return False
    return datetime.now(UTC) - when <= IMPORT_OBJECT_RETENTION


def presign_import_downloads(jobs: list[Any]) -> dict[str, str]:
    """Presigned GET URLs for import files still in the import prefix."""
    keys: list[str] = []
    for job in jobs:
        if not import_object_is_available(getattr(job, "created_at", None)):
            continue
        object_key = str(job.object_key)
        try:
            validate_object_key(object_key, IMPORT_PREFIX)
        except ValidationError:
            continue
        keys.append(object_key)
    if not keys:
        return {}
    try:
        client = get_s3_client()
    except Exception as exc:
        logger.info(
            "Import history download URLs were not signed",
            extra={"error_type": type(exc).__name__},
        )
        return {}
    downloads: dict[str, str] = {}
    for object_key in keys:
        try:
            downloads[object_key] = build_download_url(
                object_key,
                import_download_filename(object_key),
                client,
                expires_in=HISTORY_PRESIGN_EXPIRY_SECONDS,
                content_disposition="inline",
            )
        except Exception as exc:
            logger.info(
                "Import history download URL was not signed",
                extra={"error_type": type(exc).__name__},
            )
    return downloads


def build_download_url(
    object_key: str,
    file_name: str,
    client: Any | None = None,
    *,
    expires_in: int = PRESIGN_EXPIRY_SECONDS,
    content_disposition: str = "attachment",
) -> str:
    bucket = _require_env("ADMIN_IMPORT_EXPORT_BUCKET")
    if client is None:
        client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket,
            "Key": object_key,
            "ResponseContentDisposition": (
                f'{content_disposition}; filename="{sanitize_filename(file_name)}"'
            ),
            "ResponseContentType": "application/json",
        },
        ExpiresIn=expires_in,
    )


def _as_aware_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return None
