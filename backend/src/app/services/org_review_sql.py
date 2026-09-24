"""SQL summaries and blocker filters for the organization review queue.

``summarize_catalog`` must return the same counts as
``summarize_snapshots`` in ``org_review.py``. Blocker predicates mirror
``collect_issues``. Warning issue codes are counted here for the summary
and still filtered in Python when paging the queue.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import case, func, literal, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.db.models import Activity, ActivityPricing, ActivitySchedule, Location
from app.db.models import Organization
from app.services.org_review import REVIEW_STATUSES

BLOCKER_ISSUE_CODES = (
    "missing_description",
    "no_locations",
    "no_activities",
    "missing_coordinates",
    "missing_pricing",
    "missing_schedule",
)

_WS_EDGES = r"^[[:space:]]+|[[:space:]]+$"


def summarize_catalog(session: Session) -> dict[str, Any]:
    """Aggregate review counts without loading every organization."""
    source_key = func.coalesce(
        func.nullif(Organization.source, literal("")),
        literal("unknown"),
    )
    status_source_key = func.coalesce(
        func.nullif(Organization.status_source, literal("")),
        literal("unknown"),
    )
    grouped = session.execute(
        select(
            Organization.review_status,
            source_key,
            status_source_key,
            func.count(),
        ).group_by(
            Organization.review_status,
            source_key,
            status_source_key,
        )
    ).all()
    by_review = {status: 0 for status in REVIEW_STATUSES}
    by_source: dict[str, int] = {}
    by_status_source: dict[str, int] = {}
    total = 0
    for review_status, source, status_source, count in grouped:
        amount = int(count)
        total += amount
        by_review[review_status] = by_review.get(review_status, 0) + amount
        by_source[source] = by_source.get(source, 0) + amount
        by_status_source[status_source] = (
            by_status_source.get(status_source, 0) + amount
        )

    issue_row = session.execute(
        select(
            *[
                _count_where(predicate).label(code)
                for code, predicate in _issue_predicates().items()
            ],
            _count_where(has_blocker_clause()).label("with_blockers"),
        ).select_from(Organization)
    ).one()
    by_issue = {
        code: int(getattr(issue_row, code) or 0)
        for code in _issue_predicates()
        if int(getattr(issue_row, code) or 0)
    }
    return {
        "total": total,
        "by_review_status": by_review,
        "by_source": by_source,
        "by_status_source": by_status_source,
        "by_issue": by_issue,
        "with_blockers": int(issue_row.with_blockers or 0),
    }


def has_blocker_clause() -> ColumnElement[bool]:
    """True when the organization has at least one release blocker."""
    predicates = _issue_predicates()
    return or_(*(predicates[code] for code in BLOCKER_ISSUE_CODES))


def issue_clause(code: str) -> ColumnElement[bool] | None:
    """SQL predicate for a known issue code, or None when it is unknown."""
    return _issue_predicates().get(code)


def _issue_predicates() -> dict[str, ColumnElement[bool]]:
    return {
        "missing_description": _blank(Organization.description),
        "source_attribution": or_(
            Organization.description_source == "template",
            Organization.description.contains("Source:"),
        ),
        "missing_zh_name": _blank(Organization.name_translations.op("->>")("zh")),
        "missing_zh_description": _blank(
            Organization.description_translations.op("->>")("zh")
        ),
        "no_contact": _no_contact(),
        "no_media": func.coalesce(func.cardinality(Organization.media_urls), 0) == 0,
        "no_logo": _blank(Organization.logo_media_url),
        "no_place_id": _blank(Organization.place_id),
        "no_locations": ~_location_exists(),
        "no_activities": ~_activity_exists(),
        "missing_coordinates": _child_exists(
            Location,
            or_(Location.lat.is_(None), Location.lng.is_(None)),
        ),
        "missing_pricing": _activity_missing(ActivityPricing),
        "missing_schedule": _activity_missing(ActivitySchedule),
        "missing_activity_description": _child_exists(
            Activity,
            _blank(Activity.description),
        ),
        "default_age_range": _child_exists(
            Activity,
            (func.lower(Activity.age_range) == 0)
            & (func.upper(Activity.age_range) == 19),
        ),
    }


def _count_where(predicate: ColumnElement[bool]) -> ColumnElement[Any]:
    return func.coalesce(func.sum(case((predicate, 1), else_=0)), 0)


def _blank(column: Any) -> ColumnElement[bool]:
    trimmed = func.regexp_replace(
        func.coalesce(column, ""),
        _WS_EDGES,
        "",
        "g",
    )
    return func.length(trimmed) == 0


def _no_contact() -> ColumnElement[bool]:
    fields = (
        Organization.phone_number,
        Organization.email,
        Organization.whatsapp,
        Organization.facebook,
        Organization.instagram,
        Organization.tiktok,
        Organization.twitter,
        Organization.xiaohongshu,
        Organization.wechat,
    )
    return (
        _blank(fields[0])
        & _blank(fields[1])
        & _blank(fields[2])
        & _blank(fields[3])
        & _blank(fields[4])
        & _blank(fields[5])
        & _blank(fields[6])
        & _blank(fields[7])
        & _blank(fields[8])
    )


def _location_exists() -> ColumnElement[bool]:
    return _child_exists(Location)


def _activity_exists() -> ColumnElement[bool]:
    return _child_exists(Activity)


def _child_exists(model: Any, extra: ColumnElement[bool] | None = None) -> Any:
    conditions = [model.org_id == Organization.id]
    if extra is not None:
        conditions.append(extra)
    return select(model.id).where(*conditions).exists()


def _activity_missing(child: Any) -> Any:
    missing_child = ~select(child.id).where(child.activity_id == Activity.id).exists()
    return _child_exists(Activity, missing_child)
