"""Lock catalog parents before a flush so child edits cannot deadlock.

The version trigger updates the parent after the child row is already
locked. Taking the organization lock, then the activity lock, before
that flush keeps every writer on the same order.
"""

from __future__ import annotations

from sqlalchemy import event, select
from sqlalchemy.orm import Session

_REGISTERED = False


def register() -> None:
    """Install the flush listener once."""
    global _REGISTERED
    if _REGISTERED:
        return
    event.listen(Session, "before_flush", _lock_catalog_parents)
    _REGISTERED = True


def _lock_catalog_parents(
    session: Session, flush_context: object, instances: object
) -> None:
    del flush_context, instances
    try:
        bind = session.get_bind()
    except Exception:
        return
    if getattr(getattr(bind, "dialect", None), "name", "") != "postgresql":
        return
    from app.db.models import (
        Activity,
        ActivityLocation,
        ActivityPricing,
        ActivitySchedule,
        ActivityScheduleEntry,
        Location,
        Organization,
    )

    org_ids: set[object] = set()
    activity_ids: set[object] = set()
    schedule_ids: set[object] = set()
    pending = list(session.new) + list(session.dirty) + list(session.deleted)
    for obj in pending:
        if isinstance(obj, Organization) and obj.id is not None:
            org_ids.add(obj.id)
        elif isinstance(obj, Location) and obj.org_id is not None:
            org_ids.add(obj.org_id)
        elif isinstance(obj, Activity):
            if obj.org_id is not None:
                org_ids.add(obj.org_id)
            if obj.id is not None:
                activity_ids.add(obj.id)
        elif isinstance(obj, (ActivityPricing, ActivitySchedule)):
            if obj.activity_id is not None:
                activity_ids.add(obj.activity_id)
        elif isinstance(obj, ActivityLocation) and obj.activity_id is not None:
            activity_ids.add(obj.activity_id)
        elif isinstance(obj, ActivityScheduleEntry) and obj.schedule_id is not None:
            schedule_ids.add(obj.schedule_id)
    if not org_ids and not activity_ids and not schedule_ids:
        return
    with session.no_autoflush:
        if schedule_ids:
            rows = session.execute(
                select(ActivitySchedule.activity_id, Activity.org_id)
                .join(Activity, Activity.id == ActivitySchedule.activity_id)
                .where(ActivitySchedule.id.in_(schedule_ids))
            )
            for activity_id, org_id in rows:
                if activity_id is not None:
                    activity_ids.add(activity_id)
                if org_id is not None:
                    org_ids.add(org_id)
        if activity_ids:
            for org_id in session.scalars(
                select(Activity.org_id).where(Activity.id.in_(activity_ids))
            ):
                if org_id is not None:
                    org_ids.add(org_id)
        if org_ids:
            session.execute(
                select(Organization.id)
                .where(Organization.id.in_(org_ids))
                .order_by(Organization.id)
                .with_for_update()
            )
        if activity_ids:
            session.execute(
                select(Activity.id)
                .where(Activity.id.in_(activity_ids))
                .order_by(Activity.id)
                .with_for_update()
            )
