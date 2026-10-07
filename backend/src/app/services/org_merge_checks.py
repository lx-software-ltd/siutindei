"""Merge warnings and identity checks that must run before children move."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Activity, Location, Organization
from app.exceptions import ValidationError


def merge_warnings(session, survivor, sources) -> list[str]:
    """Explain manager, review, and child-row effects before a merge."""
    warnings: list[str] = []
    if any(source.manager_id != survivor.manager_id for source in sources):
        warnings.append(
            "A merged organization has a different manager. "
            "That manager loses this record."
        )
    if survivor.review_status != "approved" and any(
        source.review_status == "approved" for source in sources
    ):
        warnings.append(
            "The survivor is still pending review while a merged "
            "organization is approved."
        )
    if _records_combine(session, survivor, sources):
        warnings.append(
            "Matching addresses and activity names are combined onto the survivor."
        )
    elif _locations_overlap(session, survivor, sources):
        warnings.append(
            "Locations look like the same place. Different addresses both stay."
        )
    return warnings


def assert_identity_unique(
    session: Session,
    survivor: Organization,
    name: str,
    place_id: str,
) -> None:
    """Reject a planned name or place id that belongs to a third organization.

    The check runs before those values are written. A query after the write
    autoflushes the new name and hits the unique index before this can raise.
    """
    with session.no_autoflush:
        clash = session.scalar(
            select(Organization.id).where(
                Organization.id != survivor.id,
                func.lower(func.trim(Organization.name)) == name.casefold(),
            )
        )
    if clash is not None:
        raise ValidationError(
            "This name matches another organization",
            field="name",
        )
    if not place_id:
        return
    with session.no_autoflush:
        place_clash = session.scalar(
            select(Organization.id).where(
                Organization.id != survivor.id,
                Organization.place_id == place_id,
            )
        )
    if place_clash is not None:
        raise ValidationError(
            "This place id matches another organization",
            field="place_id",
        )


def _records_combine(session, survivor, sources) -> bool:
    ids = [survivor.id, *[source.id for source in sources]]
    addresses = [
        _text(row.address).casefold()
        for row in session.scalars(select(Location).where(Location.org_id.in_(ids)))
        if _text(row.address)
    ]
    if len(addresses) != len(set(addresses)):
        return True
    names = [
        _text(row.name).casefold()
        for row in session.scalars(select(Activity).where(Activity.org_id.in_(ids)))
        if _text(row.name)
    ]
    return len(names) != len(set(names))


def _locations_overlap(session, survivor, sources) -> bool:
    ids = [survivor.id, *[source.id for source in sources]]
    rows = list(session.scalars(select(Location).where(Location.org_id.in_(ids))).all())
    for left in rows:
        for right in rows:
            if str(left.org_id) == str(right.org_id) or str(left.id) >= str(right.id):
                continue
            if (
                _text(left.address)
                and _text(left.address).casefold() == _text(right.address).casefold()
            ):
                return True
            if _close(left, right):
                return True
    return False


def _close(left: Location, right: Location) -> bool:
    left_lat = left.lat
    left_lng = left.lng
    right_lat = right.lat
    right_lng = right.lng
    if left_lat is None or left_lng is None or right_lat is None or right_lng is None:
        return False
    lat_m = (float(left_lat) - float(right_lat)) * 111_000
    lng_m = (float(left_lng) - float(right_lng)) * 111_000 * 0.85
    return (lat_m * lat_m + lng_m * lng_m) ** 0.5 <= 50


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
