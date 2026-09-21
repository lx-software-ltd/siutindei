"""Admin bulk import/export handlers for JSON files."""

from __future__ import annotations

import json
import os
from typing import Any, Mapping
from uuid import UUID

from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from app.api.admin_auth import _is_admin, _set_session_audit_context
from app.api.admin_imports_export import (
    build_export_payload,
    export_file_name,
    load_export_organizations,
)
from app.api.admin_imports_importer import process_import_payload
from app.api.admin_imports_jobs import (
    find_import_job_by_id,
    find_import_job_by_key,
    serialize_import_job,
    store_import_job,
)
from app.api.admin_imports_utils import (
    build_object_key,
    sanitize_filename,
    validate_object_key,
)
from app.api.admin_request import _parse_body, _query_param, _require_env
from app.db.engine import get_engine
from app.exceptions import NotFoundError, ValidationError
from app.services.aws_clients import get_s3_client
from app.utils import json_response
from app.utils.logging import get_logger

logger = get_logger(__name__)

IMPORT_PREFIX = "admin/imports"
EXPORT_PREFIX = "admin/exports"
PRESIGN_EXPIRY_SECONDS = 900


def _handle_admin_imports(
    event: Mapping[str, Any],
    method: str,
    resource_id: str | None,
) -> dict[str, Any]:
    """Dispatch admin import/export routes."""
    if method == "POST" and resource_id == "presign":
        return _handle_import_presign(event)
    if method == "POST" and resource_id is None:
        return _handle_import_process(event)
    if method == "GET" and resource_id == "export":
        return _handle_export(event)
    if method == "GET" and resource_id:
        return _handle_get_import_job(event, resource_id)
    return json_response(404, {"error": "Not found"}, event=event)


def _handle_import_presign(event: Mapping[str, Any]) -> dict[str, Any]:
    """Generate a presigned URL for importing JSON data."""
    body = _parse_body(event)
    if not isinstance(body, dict):
        raise ValidationError("Request body must be an object")
    file_name = body.get("file_name")
    content_type = body.get("content_type")
    if not file_name:
        raise ValidationError("file_name is required", field="file_name")
    if not content_type:
        raise ValidationError("content_type is required", field="content_type")
    file_name = str(file_name).strip()
    content_type = str(content_type).strip().lower()
    if not file_name.lower().endswith(".json"):
        raise ValidationError(
            "file_name must end with .json",
            field="file_name",
        )
    if not content_type.startswith("application/json"):
        raise ValidationError(
            "content_type must be application/json",
            field="content_type",
        )

    bucket = _require_env("ADMIN_IMPORT_EXPORT_BUCKET")
    object_key = build_object_key(IMPORT_PREFIX, file_name)
    client = get_s3_client()
    upload_url = client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": bucket,
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=PRESIGN_EXPIRY_SECONDS,
    )

    return json_response(
        200,
        {
            "upload_url": upload_url,
            "object_key": object_key,
            "expires_in": PRESIGN_EXPIRY_SECONDS,
        },
        event=event,
    )


def _handle_import_process(event: Mapping[str, Any]) -> dict[str, Any]:
    """Process a JSON import from S3."""
    body = _parse_body(event)
    if not isinstance(body, dict):
        raise ValidationError("Request body must be an object")
    object_key = body.get("object_key")
    if not object_key:
        raise ValidationError("object_key is required", field="object_key")
    object_key = str(object_key).strip()
    validate_object_key(object_key, IMPORT_PREFIX)
    dry_run = _parse_dry_run(body)

    with Session(get_engine()) as session:
        existing_job = find_import_job_by_key(session, object_key)
        if existing_job is not None and not (existing_job.dry_run and not dry_run):
            return json_response(
                200,
                serialize_import_job(existing_job),
                event=event,
            )

    payload = _load_import_payload(object_key)
    if not isinstance(payload, dict):
        raise ValidationError("Import file must be a JSON object")

    file_warnings: list[str] = []
    allow_org_updates = True
    catalog_manager_id = os.getenv("BOARD_CATALOG_MANAGER_ID", "").strip() or None
    if _is_admin(event):
        catalog_manager_id = None
    with Session(get_engine()) as session:
        # Dry-run flushes fire the same audit trigger as a live import.
        # Skip session context so leftover rows cannot look like live
        # writes; persist_import_change also deletes in-txn audit rows.
        if not dry_run:
            _set_session_audit_context(session, event)
        summary, results = process_import_payload(
            session,
            payload,
            file_warnings,
            dry_run=dry_run,
            allow_org_updates=allow_org_updates,
            catalog_manager_id=catalog_manager_id,
        )
        if dry_run:
            session.rollback()
        job = store_import_job(
            session,
            object_key,
            dry_run=dry_run,
            summary=summary,
            results=results,
            file_warnings=file_warnings,
        )
        # expire_on_commit empties attributes; the session then
        # closes. Copy the response first or job.id raises
        # DetachedInstanceError and the client sees HTTP 500.
        body = {
            "id": str(job.id),
            "object_key": object_key,
            "summary": summary,
            "results": results,
            "file_warnings": file_warnings,
            "dry_run": dry_run,
        }
        session.commit()

    logger.info(
        ("Admin import dry-run completed" if dry_run else "Admin import completed"),
        extra={"summary": summary, "dry_run": dry_run},
    )

    return json_response(200, body, event=event)


def _handle_get_import_job(
    event: Mapping[str, Any],
    resource_id: str,
) -> dict[str, Any]:
    """Return a stored import job for the owner Progress card."""
    try:
        job_id = UUID(resource_id)
    except ValueError as exc:
        raise ValidationError("job_id must be a UUID", field="id") from exc
    with Session(get_engine()) as session:
        job = find_import_job_by_id(session, job_id)
        if job is None:
            raise NotFoundError("imports", resource_id)
        return json_response(200, serialize_import_job(job), event=event)


def _handle_export(event: Mapping[str, Any]) -> dict[str, Any]:
    """Export organizations and related data to JSON in S3."""
    org_name = _query_param(event, "org_name")
    org_name = org_name.strip() if org_name else None
    timezone_name = "UTC"

    with Session(get_engine()) as session:
        _set_session_audit_context(session, event)
        organizations = load_export_organizations(session, org_name)
        payload, warnings = build_export_payload(
            session,
            organizations,
            timezone_name,
        )

    file_name = export_file_name(org_name)
    object_key = build_object_key(EXPORT_PREFIX, file_name)
    _write_export_payload(object_key, payload)
    download_url = _build_download_url(object_key, file_name)

    return json_response(
        200,
        {
            "download_url": download_url,
            "object_key": object_key,
            "file_name": file_name,
            "expires_in": PRESIGN_EXPIRY_SECONDS,
            "warnings": warnings,
        },
        event=event,
    )


def _parse_dry_run(body: dict[str, Any]) -> bool:
    dry_run = body.get("dry_run", False)
    if dry_run is None:
        dry_run = False
    if not isinstance(dry_run, bool):
        raise ValidationError("dry_run must be a boolean", field="dry_run")
    return dry_run


def _load_import_payload(object_key: str) -> dict[str, Any]:
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


def _write_export_payload(object_key: str, payload: dict[str, Any]) -> None:
    bucket = _require_env("ADMIN_IMPORT_EXPORT_BUCKET")
    client = get_s3_client()
    body = json.dumps(payload, ensure_ascii=True, default=str).encode("utf-8")
    client.put_object(
        Bucket=bucket,
        Key=object_key,
        Body=body,
        ContentType="application/json",
    )


def _build_download_url(object_key: str, file_name: str) -> str:
    bucket = _require_env("ADMIN_IMPORT_EXPORT_BUCKET")
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
