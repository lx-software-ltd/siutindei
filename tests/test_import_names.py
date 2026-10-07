"""Import writes cleaned names and keeps the original spelling."""

from __future__ import annotations

from app.api.admin_imports_upsert import upsert_activity, upsert_organization


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
    assert org.source_note == "Imported name: HARBOUR CLUB"


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
    assert activity.source_note == "Imported name: SWIM CLASS"
