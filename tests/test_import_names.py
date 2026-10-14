"""Import writes cleaned names and keeps the original spelling."""

from __future__ import annotations

from app.api.admin_imports_upsert import upsert_activity, upsert_organization
from app.db.models import ImportSettings, NameFixProposal
from app.services.data_quality.names import record_imported_name
from sqlalchemy import select


def _set_cleanup(session, mode: str) -> None:
    row = session.get(ImportSettings, 1)
    if row is None:
        row = ImportSettings(id=1, name_cleanup=mode)
        session.add(row)
    else:
        row.name_cleanup = mode
    session.flush()


def test_upsert_organization_stores_cleaned_name(db_session) -> None:
    org, status = upsert_organization(
        db_session,
        {
            "name": "HARBOUR CLUB",
            "manager_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        },
    )
    assert status == "created"
    assert org.name == "Harbour Club"
    assert org.source_note is None


def test_reimport_of_dirty_name_updates_cleaned_row(db_session) -> None:
    created, _status = upsert_organization(
        db_session,
        {
            "name": "HARBOUR CLUB",
            "manager_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        },
    )
    updated, status = upsert_organization(
        db_session,
        {
            "name": "HARBOUR CLUB",
            "manager_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "email": "desk@example.com",
        },
        allow_updates=True,
    )
    assert status == "updated"
    assert updated.id == created.id
    assert updated.email == "desk@example.com"


def test_activity_name_stays_when_org_is_approved(
    db_session,
    sample_organization,
    sample_activity_category,
) -> None:
    sample_organization.review_status = "approved"
    db_session.flush()
    activity, status = upsert_activity(
        db_session,
        sample_organization,
        {
            "name": "SWIM CLASS",
            "description": "Laps",
            "age_min": 5,
            "age_max": 12,
            "category_id": str(sample_activity_category.id),
        },
    )
    assert status == "created"
    assert activity.name == "SWIM CLASS"
    assert activity.source_note is None


def test_activity_name_is_cleaned_while_pending(
    db_session,
    sample_organization,
    sample_activity_category,
) -> None:
    activity, status = upsert_activity(
        db_session,
        sample_organization,
        {
            "name": "SWIM CLASS",
            "description": "Laps",
            "age_min": 5,
            "age_max": 12,
            "category_id": str(sample_activity_category.id),
        },
    )
    assert status == "created"
    assert activity.name == "Swim Class"
    assert activity.source_note is None


def test_off_stores_the_raw_name(db_session) -> None:
    _set_cleanup(db_session, "off")
    org, status = upsert_organization(
        db_session,
        {
            "name": "HARBOUR CLUB",
            "manager_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        },
    )
    assert status == "created"
    assert org.name == "HARBOUR CLUB"
    assert db_session.scalars(select(NameFixProposal)).all() == []


def test_propose_stores_the_raw_name_and_a_pending_proposal(db_session) -> None:
    _set_cleanup(db_session, "propose")
    org, status = upsert_organization(
        db_session,
        {
            "name": "HARBOUR CLUB",
            "manager_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "_name_change": {
                "original": "Harbour Club",
                "proposed": "Forged",
                "status": "applied",
                "rules": [],
            },
        },
    )
    assert status == "created"
    assert org.name == "HARBOUR CLUB"
    row = db_session.scalars(select(NameFixProposal)).one()
    assert row.status == "pending"
    assert row.proposed_value == "Harbour Club"
    assert row.decided_by is None


def test_propose_reimport_keeps_an_accepted_name(db_session) -> None:
    created, _status = upsert_organization(
        db_session,
        {
            "name": "HARBOUR CLUB",
            "manager_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        },
    )
    assert created.name == "Harbour Club"
    _set_cleanup(db_session, "propose")
    updated, status = upsert_organization(
        db_session,
        {
            "name": "HARBOUR CLUB",
            "manager_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "email": "desk@example.com",
        },
        allow_updates=True,
    )
    assert status == "updated"
    assert updated.name == "Harbour Club"
    pending = db_session.scalars(
        select(NameFixProposal).where(NameFixProposal.status == "pending")
    ).all()
    assert pending == []


def test_forged_name_change_is_ignored(db_session, sample_organization) -> None:
    record_imported_name(
        db_session,
        sample_organization,
        {
            "name": "Forged",
            "_name_change": {
                "original": "Harbour Club",
                "proposed": "Forged",
                "rules": [],
                "status": "pending",
                "translations": {},
            },
        },
        "organization",
    )
    assert db_session.scalars(select(NameFixProposal)).all() == []
