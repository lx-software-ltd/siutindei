"""Copy organization websites out of stored import files.

Completed live imports are applied oldest first. A created or updated
row writes the website from that file. A skipped row fills the website
only while it is empty. A merged-away id fills the survivor only while
the survivor's website is empty. A deleted organization is left alone.

Every non-running job then loses the warning that said the website was
accepted but not stored. A missing file still drops that warning.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import UUID

from botocore.exceptions import ClientError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin_imports_catalog import MAX_WEBSITE_LENGTH
from app.db.models import ImportJob, Organization, OrganizationMerge
from app.services.aws_clients import get_s3_client

WEBSITE_DISCARD_WARNING = "website is accepted but not stored"
_ORG_PATH = re.compile(r"^organizations\[(\d+)\]$")
_MISSING_OBJECT_CODES = {"NoSuchKey", "404", "NotFound"}
_WRITE_STATUSES = {"created", "updated", "skipped"}


@dataclass
class WebsiteBackfillReport:
    """Counts from one backfill pass."""

    jobs_seen: int = 0
    websites_written: int = 0
    warnings_removed: int = 0
    payloads_missing: list[str] = field(default_factory=list)


def backfill_import_websites(
    session: Session,
    load_payload: Callable[[str], dict[str, Any] | None],
) -> WebsiteBackfillReport:
    """Apply stored import websites and drop the discard warning."""
    report = WebsiteBackfillReport()
    jobs = list(
        session.scalars(
            select(ImportJob)
            .where(ImportJob.status != "running")
            .order_by(ImportJob.created_at.asc(), ImportJob.id.asc())
        ).all()
    )
    report.jobs_seen = len(jobs)
    for job in jobs:
        if job.status == "completed" and not job.dry_run:
            payload = load_payload(job.object_key)
            if payload is None:
                report.payloads_missing.append(job.object_key)
            else:
                report.websites_written += _apply_payload(session, job, payload)
        report.warnings_removed += _strip_discard_warnings(job)
    return report


def load_s3_import_payload(object_key: str) -> dict[str, Any] | None:
    """Return one import JSON object, or None when it is gone."""
    bucket = os.environ.get("ADMIN_IMPORT_EXPORT_BUCKET", "").strip()
    if not bucket:
        raise RuntimeError("ADMIN_IMPORT_EXPORT_BUCKET is required")
    client = get_s3_client()
    try:
        response = client.get_object(Bucket=bucket, Key=object_key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in _MISSING_OBJECT_CODES:
            return None
        raise
    body = response["Body"].read().decode("utf-8")
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        return None
    return parsed


def _apply_payload(
    session: Session,
    job: ImportJob,
    payload: dict[str, Any],
) -> int:
    raw_orgs = payload.get("organizations")
    if not isinstance(raw_orgs, list):
        return 0
    written = 0
    for row in job.results or []:
        if not isinstance(row, dict):
            continue
        if row.get("type") != "organizations":
            continue
        status = str(row.get("status") or "")
        if status not in _WRITE_STATUSES:
            continue
        website = _website_for_row(row, raw_orgs)
        if website is None:
            continue
        org, followed_merge = _load_org(session, row.get("id"))
        if org is None:
            continue
        if status == "skipped" or followed_merge:
            if _text(org.website):
                continue
        elif _text(org.website) == website:
            continue
        org.website = website
        written += 1
    return written


def _website_for_row(
    row: dict[str, Any],
    raw_orgs: list[Any],
) -> str | None:
    path = row.get("path")
    if isinstance(path, str):
        match = _ORG_PATH.match(path)
        if match:
            index = int(match.group(1))
            if 0 <= index < len(raw_orgs):
                return _website_value(raw_orgs[index])
    key = _text(row.get("key"))
    if not key:
        return None
    matches = [
        item
        for item in raw_orgs
        if isinstance(item, dict) and _text(item.get("name")) == key
    ]
    if len(matches) == 1:
        return _website_value(matches[0])
    return None


def _load_org(
    session: Session,
    raw_id: Any,
) -> tuple[Organization | None, bool]:
    org_id = _parse_uuid(raw_id)
    if org_id is None:
        return None, False
    org = session.get(Organization, org_id)
    if org is not None:
        return org, False
    seen = {org_id}
    current = org_id
    for _ in range(5):
        merge = session.scalars(
            select(OrganizationMerge)
            .where(OrganizationMerge.merged_org_id == current)
            .order_by(OrganizationMerge.merged_at.desc())
        ).first()
        if merge is None or merge.kind == "delete" or merge.survivor_org_id is None:
            return None, False
        survivor_id = merge.survivor_org_id
        if survivor_id in seen:
            return None, False
        seen.add(survivor_id)
        survivor = session.get(Organization, survivor_id)
        if survivor is not None:
            return survivor, True
        current = survivor_id
    return None, False


def _strip_discard_warnings(job: ImportJob) -> int:
    removed = 0
    results: list[Any] = []
    for row in list(job.results or []):
        if not isinstance(row, dict):
            results.append(row)
            continue
        warnings = row.get("warnings")
        if not isinstance(warnings, list):
            results.append(row)
            continue
        kept = [item for item in warnings if not _is_discard_warning(item)]
        removed += len(warnings) - len(kept)
        if len(kept) == len(warnings):
            results.append(row)
            continue
        updated = dict(row)
        updated["warnings"] = kept
        results.append(updated)
    file_warnings = [
        item for item in list(job.file_warnings or []) if not _is_discard_warning(item)
    ]
    job.results = results
    job.file_warnings = file_warnings
    summary = dict(job.summary or {})
    if removed and summary.get("warnings") is not None:
        try:
            current = int(summary["warnings"])
        except (TypeError, ValueError):
            current = 0
        summary["warnings"] = max(0, current - removed)
        job.summary = summary
    return removed


def _website_value(raw_org: Any) -> str | None:
    if not isinstance(raw_org, dict):
        return None
    return _clip(_text(raw_org.get("website")))


def _clip(value: str) -> str | None:
    if not value:
        return None
    return value[:MAX_WEBSITE_LENGTH]


def _is_discard_warning(value: Any) -> bool:
    return isinstance(value, str) and WEBSITE_DISCARD_WARNING in value


def _parse_uuid(value: Any) -> UUID | None:
    if isinstance(value, UUID):
        return value
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
