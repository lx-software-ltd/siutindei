"""Cursor filters for name-fix proposal lists."""

from __future__ import annotations

import base64
import json
from datetime import datetime
from uuid import UUID

from sqlalchemy import String, and_, cast, or_, select
from sqlalchemy.orm import Session

from app.db.models import Activity, NameFixProposal, Organization
from app.exceptions import ValidationError
from app.services.name_sanitizer import RULE_CODES


def proposal_stmt(status, entity_type, rule, org_id, query):
    """Pending and decided proposals whose organization or activity still exists."""
    stmt = select(NameFixProposal)
    if status:
        stmt = stmt.where(NameFixProposal.status == status)
    if entity_type:
        stmt = stmt.where(NameFixProposal.entity_type == entity_type)
    if rule:
        if rule not in RULE_CODES:
            raise ValidationError("Invalid rule", field="rule")
        stmt = stmt.where(
            cast(NameFixProposal.rules, String).ilike(f'%"{rule}"%', escape="\\")
        )
    if org_id is not None:
        activity_ids = select(Activity.id).where(Activity.org_id == org_id)
        stmt = stmt.where(
            or_(
                and_(
                    NameFixProposal.entity_type == "organization",
                    NameFixProposal.entity_id == org_id,
                ),
                and_(
                    NameFixProposal.entity_type == "activity",
                    NameFixProposal.entity_id.in_(activity_ids),
                ),
            )
        )
    if query:
        pattern = ilike_pattern(query)
        stmt = stmt.where(
            or_(
                NameFixProposal.current_value.ilike(pattern, escape="\\"),
                NameFixProposal.proposed_value.ilike(pattern, escape="\\"),
            )
        )
    org_exists = (
        select(Organization.id)
        .where(Organization.id == NameFixProposal.entity_id)
        .exists()
    )
    activity_exists = (
        select(Activity.id).where(Activity.id == NameFixProposal.entity_id).exists()
    )
    stmt = stmt.where(
        or_(
            and_(NameFixProposal.entity_type == "organization", org_exists),
            and_(NameFixProposal.entity_type == "activity", activity_exists),
        )
    )
    return stmt.order_by(NameFixProposal.created_at.desc(), NameFixProposal.id.desc())


def entity_exists(session: Session, row: NameFixProposal) -> bool:
    if row.entity_type == "organization":
        return session.get(Organization, row.entity_id) is not None
    return session.get(Activity, row.entity_id) is not None


def reject_stale_name(stored: str | None, recorded: str | None) -> None:
    if (stored or "").strip() != (recorded or "").strip():
        raise ValidationError("The stored name changed. Scan again.", field="name")


def ilike_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def encode_cursor(created_at: datetime, proposal_id) -> str:
    raw = json.dumps({"t": created_at.isoformat(), "id": str(proposal_id)}).encode()
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def decode_cursor(value: str) -> tuple[datetime, UUID]:
    padded = value + "=" * (-len(value) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")))
        stamp = datetime.fromisoformat(str(payload["t"]))
        proposal_id = UUID(str(payload["id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("cursor is invalid", field="cursor") from exc
    return stamp, proposal_id
