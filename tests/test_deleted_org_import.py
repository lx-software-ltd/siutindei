"""A deleted organization is not created again by a later import."""

from __future__ import annotations

from uuid import uuid4

from app.api.admin_crud import _crud_delete
from app.api.admin_imports_importer import process_import_payload
from app.api.admin_resources import _RESOURCE_CONFIG
from app.db.models import Organization, OrganizationMerge
from app.services.org_delete import (
    ORGANIZATION_DELETED,
    remember_deleted_organization,
)
from sqlalchemy import select


def _payload(name: str, manager_id: str, **extra: object) -> dict:
    org = {
        "name": name,
        "manager_id": manager_id,
        "description": "Imported again",
    }
    org.update(extra)
    return {"organizations": [org]}


def test_reimport_skips_a_deleted_organization(
    db_session,
    sample_organization,
    sample_activity_category,
) -> None:
    sample_organization.name = "Harbour Club"
    sample_organization.place_id = "ChIJdeleted-club"
    sample_organization.source_id = "catalog-harbour"
    db_session.flush()
    remember_deleted_organization(db_session, sample_organization, "admin-sub")
    db_session.delete(sample_organization)
    db_session.flush()

    summary, results = process_import_payload(
        db_session,
        {
            "organizations": [
                {
                    "name": "HARBOUR CLUB",
                    "manager_id": "00000000-0000-0000-0000-000000000001",
                    "place_id": "ChIJdeleted-club",
                    "source_id": "catalog-harbour",
                    "description": "Should stay gone",
                    "activities": [
                        {
                            "name": "Swim Class",
                            "category_id": str(sample_activity_category.id),
                            "age_min": 4,
                            "age_max": 8,
                        }
                    ],
                }
            ]
        },
        [],
        allow_org_updates=True,
    )
    by_type = {item["type"]: item for item in results}
    assert by_type["organizations"]["status"] == "skipped"
    assert by_type["organizations"]["errors"][0]["message"] == ORGANIZATION_DELETED
    assert by_type["activities"]["status"] == "skipped"
    assert summary["organizations"]["created"] == 0
    assert summary["activities"]["created"] == 0
    found = db_session.scalar(
        select(Organization).where(Organization.place_id == "ChIJdeleted-club")
    )
    assert found is None


def test_reimport_skips_a_deleted_name_and_still_adds_a_new_org(
    db_session,
    sample_organization,
) -> None:
    sample_organization.name = "Harbour Club"
    db_session.flush()
    remember_deleted_organization(db_session, sample_organization, None)
    db_session.delete(sample_organization)
    db_session.flush()

    _summary, results = process_import_payload(
        db_session,
        {
            "organizations": [
                {
                    "name": "Harbour Club",
                    "manager_id": "00000000-0000-0000-0000-000000000001",
                },
                {
                    "name": "New Studio",
                    "manager_id": "00000000-0000-0000-0000-000000000001",
                },
            ]
        },
        [],
        allow_org_updates=True,
    )
    by_name = {item["key"]: item for item in results if item["type"] == "organizations"}
    assert by_name["Harbour Club"]["status"] == "skipped"
    assert by_name["New Studio"]["status"] == "created"
    names = set(db_session.scalars(select(Organization.name)).all())
    assert "Harbour Club" not in names
    assert "New Studio" in names


def test_reimport_skips_a_cleaned_name_of_a_deleted_organization(
    db_session,
    sample_organization,
) -> None:
    sample_organization.name = "Harbour Club"
    db_session.flush()
    remember_deleted_organization(db_session, sample_organization, None)
    db_session.delete(sample_organization)
    db_session.flush()

    _summary, results = process_import_payload(
        db_session,
        _payload(
            "Harbour Club (海港會)",
            "00000000-0000-0000-0000-000000000001",
        ),
        [],
        allow_org_updates=True,
    )
    assert results[0]["status"] == "skipped"
    assert results[0]["errors"][0]["message"] == ORGANIZATION_DELETED
    assert (
        db_session.scalar(
            select(Organization).where(Organization.name == "Harbour Club")
        )
        is None
    )


def test_hand_created_organization_is_imported_after_a_deletion(
    db_session,
    sample_organization,
) -> None:
    sample_organization.name = "Harbour Club"
    db_session.flush()
    remember_deleted_organization(db_session, sample_organization, None)
    db_session.delete(sample_organization)
    db_session.flush()
    live = Organization(
        name="Harbour Club",
        manager_id="00000000-0000-0000-0000-000000000001",
        description="Created by hand",
    )
    db_session.add(live)
    db_session.flush()

    _summary, results = process_import_payload(
        db_session,
        _payload(
            "Harbour Club",
            "00000000-0000-0000-0000-000000000001",
        ),
        [],
        allow_org_updates=True,
    )
    assert results[0]["status"] == "updated"
    assert live.description == "Imported again"


def test_deleting_a_survivor_keeps_merged_place_ids_from_returning(
    db_session,
    sample_organization,
) -> None:
    sample_organization.name = "Kept Club"
    sample_organization.place_id = "ChIJsurvivor"
    db_session.add(
        OrganizationMerge(
            merged_org_id=uuid4(),
            survivor_org_id=sample_organization.id,
            place_id="ChIJfolded",
            snapshot={"name": "Folded Club"},
            moved_counts={},
        )
    )
    db_session.flush()
    remember_deleted_organization(db_session, sample_organization, "admin-sub")
    db_session.delete(sample_organization)
    db_session.flush()

    _summary, results = process_import_payload(
        db_session,
        _payload(
            "Folded Club Returns",
            "00000000-0000-0000-0000-000000000099",
            place_id="ChIJfolded",
        ),
        [],
        allow_org_updates=True,
    )
    assert results[0]["status"] == "skipped"
    assert (
        db_session.scalar(
            select(Organization).where(Organization.place_id == "ChIJfolded")
        )
        is None
    )


def test_crud_delete_records_the_organization(
    monkeypatch,
    db_session,
    sample_organization,
) -> None:
    calls: list[str | None] = []

    def remember(session, org, deleted_by):
        calls.append(deleted_by)
        assert org.id == sample_organization.id

    monkeypatch.setattr(
        "app.api.admin_crud.remember_deleted_organization",
        remember,
    )
    monkeypatch.setattr(db_session, "commit", lambda: None)
    response = _crud_delete(
        {
            "requestContext": {
                "authorizer": {"userSub": "admin-sub", "groups": "admin"},
            },
        },
        db_session,
        _RESOURCE_CONFIG["organizations"],
        str(sample_organization.id),
    )
    assert response["statusCode"] == 204
    assert calls == ["admin-sub"]
