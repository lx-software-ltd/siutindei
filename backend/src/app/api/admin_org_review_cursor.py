"""Keyset pagination for the organization review queue."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_

from app.api.admin_request import _decode_cursor
from app.db.models import Organization
from app.exceptions import ValidationError


@dataclass(frozen=True)
class ReviewCursor:
    org_id: UUID
    name: str | None
    last_imported_at: datetime | None


def encode_review_cursor(organization: Organization, sort: str) -> str:
    imported_at = organization.last_imported_at
    payload = json.dumps(
        {
            "sort": sort,
            "id": str(organization.id),
            "name": organization.name,
            "last_imported_at": (
                imported_at.isoformat() if imported_at is not None else None
            ),
        }
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")


def parse_review_cursor(value: str | None, sort: str) -> ReviewCursor | None:
    if value is None or value == "":
        return None
    try:
        payload = _decode_cursor(value)
        if payload.get("sort") != sort or "id" not in payload:
            raise ValueError("sort")
        imported_raw = payload.get("last_imported_at")
        imported_at = datetime.fromisoformat(imported_raw) if imported_raw else None
        return ReviewCursor(
            org_id=UUID(payload["id"]),
            name=payload.get("name"),
            last_imported_at=imported_at,
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise ValidationError("Invalid cursor", field="cursor") from exc


def apply_review_order(stmt: Any, sort: str) -> Any:
    if sort == "last_imported_at":
        return stmt.order_by(
            Organization.last_imported_at.desc().nulls_last(),
            Organization.id.desc(),
        )
    return stmt.order_by(Organization.name, Organization.id)


def apply_review_cursor(stmt: Any, sort: str, cursor: ReviewCursor | None) -> Any:
    if cursor is None:
        return stmt
    if sort == "name":
        name = cursor.name or ""
        return stmt.where(
            or_(
                Organization.name > name,
                and_(
                    Organization.name == name,
                    Organization.id > cursor.org_id,
                ),
            )
        )
    if cursor.last_imported_at is None:
        return stmt.where(
            and_(
                Organization.last_imported_at.is_(None),
                Organization.id < cursor.org_id,
            )
        )
    return stmt.where(
        or_(
            Organization.last_imported_at < cursor.last_imported_at,
            and_(
                Organization.last_imported_at == cursor.last_imported_at,
                Organization.id < cursor.org_id,
            ),
            Organization.last_imported_at.is_(None),
        )
    )
