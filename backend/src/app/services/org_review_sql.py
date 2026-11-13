"""SQL summaries and blocker filters for the organization review queue.

``summarize_catalog`` must return the same counts as
``summarize_snapshots`` in ``org_review.py``. Blocker predicates mirror
``collect_issues``; an activity in a hidden category raises no
pricing or schedule blocker, and the kind rules live in
``org_review_kinds.py``. Warning issue codes are counted here for the summary
and still filtered in Python when paging the queue.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import String, and_, case, cast, func, literal, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.db.category_visibility import public_category_clause
from app.db.models import (
    Activity,
    ActivityLocation,
    Location,
    NameFixProposal,
    Organization,
)
from app.db.models.category_scan import ActivityCategoryReview
from app.db.models.category_suggestion import PENDING_CATEGORY_ID
from app.services.description_boilerplate import (
    CANTONESE_IMPORT_BOILERPLATE,
    ENGLISH_IMPORT_BOILERPLATE,
    ENGLISH_IMPORT_STEMS,
)
from app.services.org_review import (
    ACTIVITY_ADDED_SINCE_REJECTED,
    NO_LISTABLE,
    REVIEW_REASONS,
    REVIEW_STATUSES,
)
from app.services.org_review_kinds import (
    kind_issue_predicates,
    missing_pricing_blocker,
)

BLOCKER_ISSUE_CODES = (
    "missing_description",
    "no_locations",
    "no_activities",
    "missing_coordinates",
    "missing_pricing",
    "missing_schedule",
    "pending_category",
    "pending_name_fix",
)

SQL_FILTERABLE_ISSUE_CODES = (
    *BLOCKER_ISSUE_CODES,
    ACTIVITY_ADDED_SINCE_REJECTED,
)

_WS_EDGES = r"^[[:space:]]+|[[:space:]]+$"


def summarize_catalog(session: Session) -> dict[str, Any]:
    """Aggregate review counts without loading every organization."""
    source_key = func.coalesce(
        func.nullif(Organization.source, literal("")),
        literal("manual"),
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
    by_review = dict.fromkeys(REVIEW_STATUSES, 0)
    by_review_reason = _reason_counts(session)
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
        "by_review_reason": by_review_reason,
        "by_source": by_source,
        "by_status_source": by_status_source,
        "by_issue": by_issue,
        "with_blockers": int(issue_row.with_blockers or 0),
    }


def _reason_counts(session: Session) -> dict[str, int]:
    """Count rejected organizations by reason. Null is `none`."""
    reason_key = case(
        (Organization.review_reason.is_(None), literal("none")),
        else_=Organization.review_reason,
    )
    grouped = session.execute(
        select(reason_key, func.count())
        .where(Organization.review_status == "rejected")
        .group_by(reason_key)
    ).all()
    counts = dict.fromkeys((*REVIEW_REASONS, "none"), 0)
    for reason, count in grouped:
        counts[str(reason)] = counts.get(str(reason), 0) + int(count)
    return counts


def has_blocker_clause() -> ColumnElement[bool]:
    """True when the organization has at least one release blocker."""
    predicates = {
        **_issue_predicates(),
        "missing_pricing": missing_pricing_blocker(public_category_clause),
    }
    return or_(*(predicates[code] for code in BLOCKER_ISSUE_CODES))


def issue_clause(code: str) -> ColumnElement[bool] | None:
    """SQL predicate for a known issue code, or None when it is unknown."""
    return _issue_predicates().get(code)


def _issue_predicates() -> dict[str, ColumnElement[bool]]:
    return {
        "missing_description": _blank(Organization.description),
        "source_attribution": or_(
            and_(
                Organization.description_source == "template",
                _text_is_boilerplate(Organization.description),
            ),
            _json_text_is_boilerplate(Organization.description_translations, "zh"),
            _json_text_is_boilerplate(Organization.description_translations, "zh-HK"),
            Organization.description.contains("Source:"),
        ),
        "missing_zh_name": _translation_gap(
            Organization.name, Organization.name_translations, "zh"
        ),
        "missing_zh_hk_name": _translation_gap(
            Organization.name, Organization.name_translations, "zh-HK"
        ),
        "missing_en_name": _translation_gap(
            Organization.name, Organization.name_translations, "en"
        ),
        "missing_zh_description": _translation_gap(
            Organization.description, Organization.description_translations, "zh"
        ),
        "missing_zh_hk_description": _translation_gap(
            Organization.description, Organization.description_translations, "zh-HK"
        ),
        "missing_en_description": _translation_gap(
            Organization.description, Organization.description_translations, "en"
        ),
        "no_contact": _no_contact(),
        "no_media": func.coalesce(func.cardinality(Organization.media_urls), 0) == 0,
        "no_logo": _blank(Organization.logo_media_url),
        "no_place_id": _blank(Organization.place_id),
        "no_locations": ~_location_exists(),
        "no_activities": ~_activity_exists(),
        NO_LISTABLE: and_(
            _activity_exists(),
            ~_child_exists(Activity, public_category_clause(Activity.category_id)),
        ),
        "missing_coordinates": _child_exists(
            Location,
            or_(Location.lat.is_(None), Location.lng.is_(None)),
        ),
        "pending_category": _child_exists(
            Activity,
            Activity.category_id == PENDING_CATEGORY_ID,
        ),
        "pending_name_fix": or_(
            select(NameFixProposal.id)
            .where(
                NameFixProposal.entity_type == "organization",
                NameFixProposal.entity_id == Organization.id,
                NameFixProposal.status == "pending",
            )
            .exists(),
            _child_exists(
                Activity,
                select(NameFixProposal.id)
                .where(
                    NameFixProposal.entity_type == "activity",
                    NameFixProposal.entity_id == Activity.id,
                    NameFixProposal.status == "pending",
                )
                .exists(),
            ),
        ),
        "category_check_pending": _child_exists(
            Activity,
            select(ActivityCategoryReview.id)
            .where(ActivityCategoryReview.activity_id == Activity.id)
            .where(ActivityCategoryReview.status == "pending")
            .exists(),
        ),
        "activity_no_location": _activity_missing_location(),
        "missing_activity_description": _child_exists(
            Activity,
            _blank(Activity.description),
        ),
        "default_age_range": _child_exists(
            Activity,
            (func.lower(Activity.age_range) == 0)
            & (func.upper(Activity.age_range) == 19),
        ),
        ACTIVITY_ADDED_SINCE_REJECTED: and_(
            Organization.review_status == "rejected",
            Organization.review_reason.is_not(None),
            Organization.reviewed_at.is_not(None),
            _child_exists(
                Activity,
                Activity.created_at > Organization.reviewed_at,
            ),
        ),
        **kind_issue_predicates(public_category_clause),
    }


def _count_where(predicate: ColumnElement[bool]) -> ColumnElement[Any]:
    return func.coalesce(func.sum(case((predicate, 1), else_=0)), 0)


def _text_is_boilerplate(column: Any) -> ColumnElement[bool]:
    """True when this text column is still an import filler sentence."""
    return or_(
        and_(
            column.contains(ENGLISH_IMPORT_BOILERPLATE),
            or_(*(column.contains(stem) for stem in ENGLISH_IMPORT_STEMS)),
        ),
        column.contains(CANTONESE_IMPORT_BOILERPLATE),
    )


def _json_text_is_boilerplate(column: Any, language: str) -> ColumnElement[bool]:
    """True when a JSON language value is still an import filler sentence."""
    return _text_is_boilerplate(
        cast(func.coalesce(column.op("->>")(language), ""), String)
    )


def _blank(column: Any) -> ColumnElement[bool]:
    trimmed = func.regexp_replace(
        func.coalesce(column, ""),
        _WS_EDGES,
        "",
        "g",
    )
    return func.length(trimmed) == 0


def _translation_gap(base, translations, language: str) -> ColumnElement[bool]:
    """True when one required language has text and this language is blank."""
    present = or_(
        ~_blank(base),
        ~_blank(translations.op("->>")("zh")),
        ~_blank(translations.op("->>")("zh-HK")),
    )
    target = base if language == "en" else translations.op("->>")(language)
    return and_(present, _blank(target))


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
        Organization.website,
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
        & _blank(fields[9])
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


def _activity_missing_location() -> Any:
    missing = (
        ~select(ActivityLocation.activity_id)
        .where(ActivityLocation.activity_id == Activity.id)
        .exists()
    )
    return _child_exists(Activity, missing)
