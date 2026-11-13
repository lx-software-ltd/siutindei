"""Whether an area's listings are good enough to open it to the public.

An area is ready when most of its classes and camps are complete and
enough of its organisers were checked by a parent. Rejected organisers
and listings in hidden categories do not count.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Integer, and_, cast, func, or_, select
from sqlalchemy.orm import Session

from app.db.category_visibility import public_category_clause
from app.db.models import (
    Activity,
    ActivityLocation,
    ActivityPricing,
    ActivitySchedule,
    ActivityScheduleEntry,
    Location,
    Organization,
)
from app.db.queries import area_descendant_ids_subquery
from app.services.org_review_kinds import CATCH_ALL_AGE_MAX, upcoming_session_clause
from app.services.schedule_dates import hong_kong_today

READY_COMPLETE_SHARE = 0.8
READY_VERIFIED_SHARE = 0.5
LISTING_KINDS = ("class", "camp", "place", "preschool", "eat")
GATED_KINDS = ("class", "camp")


def area_readiness(session: Session, area_id: UUID) -> dict[str, Any]:
    """Listings per kind, complete classes and camps, and verified organisers."""
    in_area = Location.area_id.in_(area_descendant_ids_subquery(area_id))
    counted_org = Organization.review_status != "rejected"
    listed_activity_ids = (
        select(ActivityLocation.activity_id)
        .join(Location, Location.id == ActivityLocation.location_id)
        .where(in_area)
    )
    listings = (
        select(Activity.kind, Activity.id)
        .join(Organization, Organization.id == Activity.org_id)
        .where(
            counted_org,
            Activity.id.in_(listed_activity_ids),
            public_category_clause(Activity.category_id),
        )
        .subquery()
    )
    by_kind = dict.fromkeys(LISTING_KINDS, 0)
    for kind, count in session.execute(
        select(listings.c.kind, func.count()).group_by(listings.c.kind)
    ).all():
        by_kind[str(kind)] = int(count)

    complete = int(
        session.scalar(
            select(func.count())
            .select_from(Activity)
            .where(
                Activity.id.in_(select(listings.c.id)),
                Activity.kind.in_(GATED_KINDS),
                _is_complete(),
            )
        )
        or 0
    )
    organisers = (
        select(Organization.id, Organization.parent_verified)
        .where(
            counted_org,
            Organization.id.in_(select(Location.org_id).where(in_area)),
        )
        .subquery()
    )
    organiser_count, verified_count = session.execute(
        select(
            func.count(),
            func.coalesce(func.sum(cast(organisers.c.parent_verified, Integer)), 0),
        ).select_from(organisers)
    ).one()

    gated = sum(by_kind[kind] for kind in GATED_KINDS)
    complete_share = _share(complete, gated)
    verified_share = _share(int(verified_count), int(organiser_count))
    return {
        "area_id": str(area_id),
        "listings_by_kind": by_kind,
        "classes_and_camps": gated,
        "complete_classes_and_camps": complete,
        "organisers": int(organiser_count),
        "verified_organisers": int(verified_count),
        "complete_share": complete_share,
        "verified_share": verified_share,
        "thresholds": {
            "complete_share": READY_COMPLETE_SHARE,
            "verified_share": READY_VERIFIED_SHARE,
        },
        "ready": complete_share is not None
        and verified_share is not None
        and complete_share >= READY_COMPLETE_SHARE
        and verified_share >= READY_VERIFIED_SHARE,
    }


def _is_complete() -> Any:
    """A price and a time that has not ended.

    A class also needs a real age range. A camp needs a dated session
    that has not ended.
    """
    today = hong_kong_today()
    has_price = (
        select(ActivityPricing.id)
        .where(ActivityPricing.activity_id == Activity.id)
        .exists()
    )
    has_time = (
        select(ActivityScheduleEntry.id)
        .join(
            ActivitySchedule, ActivitySchedule.id == ActivityScheduleEntry.schedule_id
        )
        .where(
            ActivitySchedule.activity_id == Activity.id,
            or_(ActivitySchedule.ends_on.is_(None), ActivitySchedule.ends_on >= today),
        )
        .exists()
    )
    has_session = (
        select(ActivitySchedule.id)
        .where(
            ActivitySchedule.activity_id == Activity.id,
            upcoming_session_clause(today),
        )
        .exists()
    )
    lower = func.lower(Activity.age_range)
    upper = func.upper(Activity.age_range)
    catch_all = and_(
        or_(lower.is_(None), lower <= 0),
        or_(upper.is_(None), upper > CATCH_ALL_AGE_MAX),
    )
    return and_(
        has_price,
        has_time,
        or_(Activity.kind != "class", ~catch_all),
        or_(Activity.kind != "camp", has_session),
    )


def _share(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None
