"""S3 reads and presigned downloads for admin import files."""

from __future__ import annotations

import json
from typing import Any

from botocore.exceptions import ClientError

from app.api.admin_imports_utils import sanitize_filename, validate_object_key
from app.api.admin_request import _require_env
from app.exceptions import ValidationError
from app.services.aws_clients import get_s3_client

IMPORT_PREFIX = "admin/imports"
EXPORT_PREFIX = "admin/exports"
PRESIGN_EXPIRY_SECONDS = 900


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


def presign_import_downloads(jobs: list[Any]) -> dict[str, str]:
    """Presigned GET URLs for import files stored under the import prefix."""
    keys: list[str] = []
    for job in jobs:
        object_key = str(job.object_key)
        try:
            validate_object_key(object_key, IMPORT_PREFIX)
        except ValidationError:
            continue
        keys.append(object_key)
    if not keys:
        return {}
    client = get_s3_client()
    return {
        object_key: build_download_url(
            object_key,
            object_key.rsplit("/", 1)[-1] or "import.json",
            client,
        )
        for object_key in keys
    }


def build_download_url(
    object_key: str,
    file_name: str,
    client: Any | None = None,
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
                f'attachment; filename="{sanitize_filename(file_name)}"'
            ),
            "ResponseContentType": "application/json",
        },
        ExpiresIn=PRESIGN_EXPIRY_SECONDS,
    )
