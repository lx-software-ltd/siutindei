"""Organization merge reparents children and forwards old ids."""

from __future__ import annotations

from app.db.models import Activity, AuditLog, Location, Organization
from app.db.repositories.organization import OrganizationRepository
from app.exceptions import ValidationError
from app.services.org_merge import merge_organizations
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import Range
import pytest


def _org(db_session, name: str, **kwargs) -> Organization:
    org = Organization(
        name=name,
        manager_id=kwargs.pop(
            "manager_id",
            "00000000-0000-0000-0000-0000000000aa",
        ),
        review_status=kwargs.pop("review_status", "pending_review"),
        **kwargs,
    )
    db_session.add(org)
    db_session.flush()
    return org


def test_dry_run_does_not_delete(db_session, sample_geographic_area) -> None:
    survivor = _org(db_session, "Harbour Club")
    source = _org(db_session, "Harbour Club Limited", phone_number="21234567")
    location = Location(
        org_id=source.id,
        area_id=sample_geographic_area.id,
        address="1 Pier Road",
    )
    db_session.add(location)
    db_session.flush()

    plan = merge_organizations(
        db_session,
        survivor.id,
        [source.id],
        dry_run=True,
    )

    assert plan["dry_run"] is True
    assert plan["moved"]["locations"] == 1
    assert db_session.get(Organization, source.id) is not None
    db_session.refresh(location)
    assert location.org_id == source.id


def test_merge_reparents_location_and_forwards_ids(
    db_session,
    sample_geographic_area,
) -> None:
    survivor = _org(
        db_session,
        "Harbour Club",
        place_id="place-keep",
        review_status="approved",
    )
    source = _org(
        db_session,
        "Harbour Club Limited",
        place_id="place-old",
        source_id="src-old",
        email="desk@example.com",
    )
    location = Location(
        org_id=source.id,
        area_id=sample_geographic_area.id,
        address="1 Pier Road",
    )
    db_session.add(location)
    db_session.flush()

    plan = merge_organizations(
        db_session,
        survivor.id,
        [source.id],
        merged_by="admin-sub",
    )

    assert plan["merged"] is True
    assert db_session.get(Organization, source.id) is None
    db_session.refresh(location)
    db_session.refresh(survivor)
    assert location.org_id == survivor.id
    assert survivor.email == "desk@example.com"
    assert survivor.place_id == "place-keep"
    repo = OrganizationRepository(db_session)
    assert repo.find_by_place_id("place-old").id == survivor.id
    assert repo.find_by_source_id("src-old").id == survivor.id
    audit = db_session.scalars(select(AuditLog).where(AuditLog.action == "MERGE")).one()
    assert audit.new_values["source_ids"] == [str(source.id)]
    assert "email" in audit.new_values["filled_fields"]


def test_merge_folds_the_same_address(db_session, sample_geographic_area) -> None:
    survivor = _org(db_session, "Harbour Club")
    source = _org(db_session, "Harbour Club Limited")
    kept = Location(
        org_id=survivor.id,
        area_id=sample_geographic_area.id,
        address="1 Pier Road",
    )
    dropped = Location(
        org_id=source.id,
        area_id=sample_geographic_area.id,
        address="1 pier road",
    )
    db_session.add_all([kept, dropped])
    db_session.flush()
    merge_organizations(db_session, survivor.id, [source.id])
    rows = list(
        db_session.scalars(select(Location).where(Location.org_id == survivor.id)).all()
    )
    assert len(rows) == 1
    assert rows[0].id == kept.id


def test_merge_keeps_different_addresses(db_session, sample_geographic_area) -> None:
    survivor = _org(db_session, "Harbour Club")
    source = _org(db_session, "Harbour Club Limited")
    db_session.add_all(
        [
            Location(
                org_id=survivor.id,
                area_id=sample_geographic_area.id,
                address="1 Pier Road",
            ),
            Location(
                org_id=source.id,
                area_id=sample_geographic_area.id,
                address="9 Hill Street",
            ),
        ]
    )
    db_session.flush()
    merge_organizations(db_session, survivor.id, [source.id])
    count = db_session.scalar(
        select(func.count()).select_from(Location).where(Location.org_id == survivor.id)
    )
    assert count == 2


def test_merge_rejects_a_name_owned_by_a_third_organization(db_session) -> None:
    survivor = _org(db_session, "Harbour Club")
    source = _org(db_session, "Harbour Club Limited")
    _org(db_session, "Taken Name")
    with pytest.raises(ValidationError):
        merge_organizations(
            db_session,
            survivor.id,
            [source.id],
            {"name": "Taken Name"},
        )


def test_merge_folds_matching_activity_names(
    db_session,
    sample_activity_category,
) -> None:
    survivor = _org(db_session, "Harbour Club")
    source = _org(db_session, "Harbour Club Limited")
    kept = Activity(
        org_id=survivor.id,
        category_id=sample_activity_category.id,
        name="Harbour Sailing",
        description="Sailing",
        age_range=Range(0, 18, bounds="[]"),
    )
    dropped = Activity(
        org_id=source.id,
        category_id=sample_activity_category.id,
        name="harbour sailing",
        description="Sailing too",
        age_range=Range(0, 18, bounds="[]"),
    )
    db_session.add_all([kept, dropped])
    db_session.flush()
    merge_organizations(db_session, survivor.id, [source.id])
    rows = list(
        db_session.scalars(select(Activity).where(Activity.org_id == survivor.id)).all()
    )
    assert len(rows) == 1
    assert rows[0].id == kept.id
