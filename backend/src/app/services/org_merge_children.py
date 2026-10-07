"""Fold locations and activities that would break unique indexes on merge."""

from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.db.models import (
    Activity,
    ActivityLocation,
    ActivityPricing,
    ActivitySchedule,
    Location,
    NameFixProposal,
    Organization,
)
from app.db.models.category_scan import ActivityCategoryReview
from app.db.models.category_suggestion import CategorySuggestionActivity
from app.db.models.listing_event import ListingEvent


def fold_merged_records(
    session: Session,
    survivor: Organization,
    sources: list[Organization],
) -> None:
    """Reparent children, combining rows the unique indexes cannot both keep."""
    org_ids = [survivor.id, *[source.id for source in sources]]
    _fold_locations(session, survivor, org_ids)
    removed_activities = _fold_activities(session, survivor, org_ids)
    source_ids = [source.id for source in sources]
    session.execute(
        delete(NameFixProposal).where(
            NameFixProposal.entity_type == "organization",
            NameFixProposal.entity_id.in_(source_ids),
        )
    )
    if removed_activities:
        session.execute(
            delete(NameFixProposal).where(
                NameFixProposal.entity_type == "activity",
                NameFixProposal.entity_id.in_(removed_activities),
            )
        )


def _fold_locations(session: Session, survivor: Organization, org_ids: list) -> None:
    rows = list(
        session.scalars(select(Location).where(Location.org_id.in_(org_ids))).all()
    )
    by_address: dict[str, Location] = {}
    by_place: dict[str, Location] = {}
    for row in rows:
        if str(row.org_id) == str(survivor.id):
            _remember_location(by_address, by_place, row)
    for row in rows:
        if str(row.org_id) == str(survivor.id):
            continue
        address_key = _address_key(row.address)
        target = by_address.get(address_key) if address_key else None
        if target is not None:
            _retarget_location(session, row.id, target.id)
            session.flush()
            session.expire(row, ["activity_pricing", "activity_schedules"])
            session.delete(row)
            session.flush()
            continue
        row.org_id = survivor.id
        if row.place_id and row.place_id in by_place:
            row.place_id = None
        _remember_location(by_address, by_place, row)


def _fold_activities(session: Session, survivor: Organization, org_ids: list) -> list:
    rows = list(
        session.scalars(select(Activity).where(Activity.org_id.in_(org_ids))).all()
    )
    kept: dict[str, Activity] = {}
    removed: list = []
    for row in rows:
        if str(row.org_id) == str(survivor.id):
            kept[_activity_key(row.name)] = row
    for row in rows:
        if str(row.org_id) == str(survivor.id):
            continue
        target = kept.get(_activity_key(row.name))
        if target is None:
            row.org_id = survivor.id
            kept[_activity_key(row.name)] = row
            continue
        _retarget_activity(session, row, target, survivor.id)
        session.flush()
        session.expire(row, ["locations", "pricing", "schedules"])
        session.delete(row)
        removed.append(row.id)
        session.flush()
    return removed


def _retarget_location(session: Session, old_id, new_id) -> None:
    kept_links = {
        str(activity_id)
        for activity_id in session.scalars(
            select(ActivityLocation.activity_id).where(
                ActivityLocation.location_id == new_id
            )
        ).all()
    }
    for link in session.scalars(
        select(ActivityLocation).where(ActivityLocation.location_id == old_id)
    ).all():
        if str(link.activity_id) in kept_links:
            session.delete(link)
        else:
            link.location_id = new_id
            kept_links.add(str(link.activity_id))
    session.execute(
        update(ActivityPricing)
        .where(ActivityPricing.location_id == old_id)
        .values(location_id=new_id)
    )
    _retarget_schedules(session, old_id, new_id, "location")
    session.execute(
        update(ListingEvent)
        .where(ListingEvent.location_id == old_id)
        .values(location_id=new_id)
    )


def _retarget_activity(
    session, source: Activity, target: Activity, survivor_id
) -> None:
    kept_links = {
        str(location_id)
        for location_id in session.scalars(
            select(ActivityLocation.location_id).where(
                ActivityLocation.activity_id == target.id
            )
        ).all()
    }
    for link in session.scalars(
        select(ActivityLocation).where(ActivityLocation.activity_id == source.id)
    ).all():
        if str(link.location_id) in kept_links:
            session.delete(link)
        else:
            link.activity_id = target.id
            kept_links.add(str(link.location_id))
    session.execute(
        update(ActivityPricing)
        .where(ActivityPricing.activity_id == source.id)
        .values(activity_id=target.id)
    )
    _retarget_schedules(session, source.id, target.id, "activity")
    _retarget_reviews(session, source.id, target.id, survivor_id)
    _retarget_suggestion_links(session, source.id, target.id, survivor_id)
    session.execute(
        update(ListingEvent)
        .where(ListingEvent.activity_id == source.id)
        .values(activity_id=target.id)
    )
    _retarget_name_fixes(session, source.id, target.id)


def _retarget_schedules(session, old_id, new_id, kind: str) -> None:
    column = (
        ActivitySchedule.location_id
        if kind == "location"
        else ActivitySchedule.activity_id
    )
    incoming = list(session.scalars(select(ActivitySchedule).where(column == old_id)))
    kept = list(session.scalars(select(ActivitySchedule).where(column == new_id)))
    kept_keys = {_schedule_key(row, kind) for row in kept}
    for schedule in incoming:
        if _schedule_key(schedule, kind) in kept_keys:
            session.delete(schedule)
            continue
        if kind == "location":
            schedule.location_id = new_id
        else:
            schedule.activity_id = new_id
        kept_keys.add(_schedule_key(schedule, kind))


def _schedule_key(schedule: ActivitySchedule, kind: str) -> tuple:
    other = schedule.activity_id if kind == "location" else schedule.location_id
    languages = tuple(schedule.languages or [])
    return (str(other), languages)


def _retarget_name_fixes(session, source_id, target_id) -> None:
    rows = list(
        session.scalars(
            select(NameFixProposal).where(
                NameFixProposal.entity_type == "activity",
                NameFixProposal.entity_id == source_id,
            )
        ).all()
    )
    for row in rows:
        if row.status != "pending":
            row.entity_id = target_id
            continue
        clash = session.scalar(
            select(NameFixProposal.id).where(
                NameFixProposal.entity_type == "activity",
                NameFixProposal.entity_id == target_id,
                NameFixProposal.field == row.field,
                NameFixProposal.status == "pending",
                NameFixProposal.id != row.id,
            )
        )
        if clash is not None:
            session.delete(row)
            continue
        row.entity_id = target_id


def _retarget_reviews(session, source_id, target_id, survivor_id) -> None:
    rows = list(
        session.scalars(
            select(ActivityCategoryReview).where(
                ActivityCategoryReview.activity_id == source_id
            )
        ).all()
    )
    for row in rows:
        clash = session.scalar(
            select(ActivityCategoryReview.id).where(
                ActivityCategoryReview.scan_run_id == row.scan_run_id,
                ActivityCategoryReview.activity_id == target_id,
            )
        )
        if clash is not None:
            session.delete(row)
            continue
        row.activity_id = target_id
        row.org_id = survivor_id


def _retarget_suggestion_links(session, source_id, target_id, survivor_id) -> None:
    rows = list(
        session.scalars(
            select(CategorySuggestionActivity).where(
                CategorySuggestionActivity.activity_id == source_id
            )
        ).all()
    )
    kept = {
        str(suggestion_id)
        for suggestion_id in session.scalars(
            select(CategorySuggestionActivity.suggestion_id).where(
                CategorySuggestionActivity.activity_id == target_id
            )
        ).all()
    }
    for row in rows:
        if str(row.suggestion_id) in kept:
            session.delete(row)
            continue
        row.activity_id = target_id
        row.org_id = survivor_id


def _remember_location(by_address, by_place, row: Location) -> None:
    address_key = _address_key(row.address)
    if address_key and address_key not in by_address:
        by_address[address_key] = row
    if row.place_id and row.place_id not in by_place:
        by_place[row.place_id] = row


def _address_key(address: str | None) -> str:
    return (address or "").strip().casefold()


def _activity_key(name: str | None) -> str:
    return (name or "").strip().casefold()
