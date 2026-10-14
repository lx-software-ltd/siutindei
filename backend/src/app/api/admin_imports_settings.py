"""Import Settings routes and post-import Data quality."""

from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.api.admin_auth import _get_user_sub, _is_admin
from app.api.admin_imports_jobs import find_import_job_by_id
from app.api.admin_request import _parse_body
from app.db.engine import get_engine
from app.exceptions import ValidationError
from app.services.import_data_quality import (
    load_settings as load_import_data_quality_settings,
    run_import_data_quality,
    save_settings as save_import_data_quality_settings,
)
from app.utils import json_response
from app.utils.logging import get_logger

logger = get_logger(__name__)


def handle_import_post(event: Mapping[str, Any]) -> dict[str, Any]:
    """Save Import Settings or process an uploaded file."""
    body = _parse_body(event)
    if isinstance(body, dict) and "data_quality" in body and not body.get("object_key"):
        if not _is_admin(event):
            raise ValidationError("object_key is required", field="object_key")
        payload = save_import_data_quality_settings(body)
        return json_response(200, payload, event=event)
    from app.api.admin_imports import _handle_import_process

    return _handle_import_process(event)


def handle_get_import_settings(event: Mapping[str, Any]) -> dict[str, Any]:
    """Return which Data quality checks run after a live import."""
    return json_response(200, load_import_data_quality_settings(), event=event)


def attach_import_data_quality(
    event: Mapping[str, Any],
    body: dict[str, Any],
    import_job_id: Any,
) -> None:
    """Run ticked Data quality checks after a live import commits."""
    try:
        quality = run_import_data_quality(
            results=body.get("results"),
            requested_by=_get_user_sub(event),
        )
    except Exception:
        logger.exception("Import data-quality run failed")
        quality = {
            "ran": [],
            "skipped": ["duplicates", "names", "locations", "categories"],
            "errors": [{"check": "all", "error": "failed"}],
        }
    if not quality.get("ran") and not quality.get("errors"):
        return
    summary = body.setdefault("summary", {})
    if isinstance(summary, dict):
        summary["data_quality"] = quality
    if import_job_id is None:
        return
    try:
        with Session(get_engine()) as session:
            job = find_import_job_by_id(session, import_job_id)
            if job is None:
                return
            stored = dict(job.summary or {})
            stored["data_quality"] = quality
            job.summary = stored
            session.commit()
    except Exception:
        logger.exception("Import data-quality summary was not saved")
