"""A deleted organization is not created again by a later import."""

from __future__ import annotations

from uuid import UUID, uuid4

from app.api.admin_crud import _crud_delete
from app.api.admin_imports_importer import process_import_payload
from app.api.admin_resources import _RESOURCE_CONFIG
from app.db.models import AuditLog, CatalogVersion, Organization, OrganizationMerge
from app.exceptions import NotFoundError
from app.services.org_delete import (
    ORGANIZATION_DELETED,
    forget_deleted_organization,
    list_deleted_organizations,
    remember_deleted_organization,
)
from sqlalchemy import select


def _versioned(session, org_id: object) -> bool:
    """True when the database already stored version 1 for this organization."""
    return (
        session.scalar(
            select(CatalogVersion.id).where(
                CatalogVersion.entity_type == "organization",
                CatalogVersion.entity_id == org_id,
                CatalogVersion.version == 1,
            )
        )
        is not None
    )


def _assert_not_recreated(result: dict, versioned: bool) -> None:
    """A remembered deletion stays gone, with or without a version-1 row."""
    if versioned:
        assert result["status"] in {"skipped", "unchanged"}
        assert any(
            "not imported again" in item for item in result.get("warnings") or []
        )
        return
    assert result["status"] == "skipped"
    assert result["errors"][0]["message"] == ORGANIZATION_DELETED


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
    org_id = sample_organization.id
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
    _assert_not_recreated(by_type["organizations"], _versioned(db_session, org_id))
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
    org_id = sample_organization.id
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
    if _versioned(db_session, org_id):
        assert by_name["Harbour Club"]["status"] == "unchanged"
    else:
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
    org_id = sample_organization.id
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
    _assert_not_recreated(results[0], _versioned(db_session, org_id))
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
            snapshot={"name": "Folded Club", "email": "hidden@example.com"},
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
    folded = db_session.scalar(
        select(OrganizationMerge).where(OrganizationMerge.place_id == "ChIJfolded")
    )
    assert folded is not None
    assert folded.kind == "delete"
    assert folded.survivor_org_id is None
    assert set(folded.snapshot) == {"name", "names"}
    assert "email" not in folded.snapshot


def test_same_name_with_a_different_place_id_is_created(
    db_session,
    sample_organization,
) -> None:
    sample_organization.name = "Harbour Club"
    sample_organization.place_id = "ChIJdeleted-club"
    db_session.flush()
    remember_deleted_organization(db_session, sample_organization, None)
    db_session.delete(sample_organization)
    db_session.flush()

    _summary, results = process_import_payload(
        db_session,
        _payload(
            "Harbour Club",
            "00000000-0000-0000-0000-000000000001",
            place_id="ChIJother-club",
        ),
        [],
        allow_org_updates=True,
    )
    assert results[0]["status"] == "created"


def test_source_id_matches_only_the_same_catalog(
    db_session,
    sample_organization,
) -> None:
    sample_organization.name = "Harbour Club"
    sample_organization.source = "lcsd"
    sample_organization.source_id = "catalog-42"
    db_session.flush()
    remember_deleted_organization(db_session, sample_organization, None)
    db_session.delete(sample_organization)
    db_session.flush()

    _summary, other_catalog = process_import_payload(
        db_session,
        _payload(
            "Other Catalog Club",
            "00000000-0000-0000-0000-000000000001",
            source="edb",
            source_id="catalog-42",
        ),
        [],
        allow_org_updates=True,
    )
    assert other_catalog[0]["status"] == "created"

    _summary, same_catalog = process_import_payload(
        db_session,
        _payload(
            "Harbour Club Again",
            "00000000-0000-0000-0000-000000000001",
            source="lcsd",
            source_id="catalog-42",
        ),
        [],
        allow_org_updates=True,
    )
    assert same_catalog[0]["status"] == "skipped"


def test_name_only_deletion_blocks_a_file_that_has_a_place_id(
    db_session,
    sample_organization,
) -> None:
    sample_organization.name = "Harbour Club"
    sample_organization.place_id = None
    sample_organization.source_id = None
    db_session.flush()
    org_id = sample_organization.id
    remember_deleted_organization(db_session, sample_organization, None)
    db_session.delete(sample_organization)
    db_session.flush()

    _summary, results = process_import_payload(
        db_session,
        _payload(
            "Harbour Club",
            "00000000-0000-0000-0000-000000000001",
            place_id="ChIJnew-club",
        ),
        [],
        allow_org_updates=True,
    )
    _assert_not_recreated(results[0], _versioned(db_session, org_id))


def test_reimport_skips_a_name_the_organization_used_before(
    db_session,
    sample_organization,
) -> None:
    sample_organization.name = "Harbour Club"
    sample_organization.email = "hidden@example.com"
    sample_organization.phone_number = "21234567"
    sample_organization.source_note = "Imported name: Old Spelling Club"
    db_session.add(
        AuditLog(
            table_name="organizations",
            record_id=str(sample_organization.id),
            action="UPDATE",
            old_values={"name": "Former Harbour", "email": "hidden@example.com"},
            new_values={"name": "Harbour Club"},
        )
    )
    db_session.flush()
    org_id = sample_organization.id
    remember_deleted_organization(db_session, sample_organization, "admin-sub")
    db_session.delete(sample_organization)
    db_session.flush()

    stored = db_session.scalar(
        select(OrganizationMerge).where(
            OrganizationMerge.kind == "delete",
            OrganizationMerge.merged_org_id == org_id,
        )
    )
    assert stored is not None
    assert set(stored.snapshot) == {"name", "names"}
    assert "Former Harbour" in stored.snapshot["names"]
    assert "Old Spelling Club" in stored.snapshot["names"]
    assert "hidden@example.com" not in str(stored.snapshot)

    _summary, results = process_import_payload(
        db_session,
        _payload(
            "Former Harbour",
            "00000000-0000-0000-0000-000000000001",
        ),
        [],
        allow_org_updates=True,
    )
    assert results[0]["status"] == "skipped"

    listed = list_deleted_organizations(
        db_session,
        query="Former",
        cursor=None,
        limit=10,
    )
    assert listed["items"]
    assert "email" not in listed["items"][0]
    assert listed["items"][0]["deleted_by"] == "admin-sub"


def test_forgetting_a_deletion_allows_reimport(
    db_session,
    sample_organization,
) -> None:
    sample_organization.name = "Harbour Club"
    db_session.flush()
    remember_deleted_organization(db_session, sample_organization, "admin-sub")
    db_session.delete(sample_organization)
    db_session.flush()
    remembered = list_deleted_organizations(
        db_session,
        query=None,
        cursor=None,
        limit=10,
    )
    forget_deleted_organization(db_session, UUID(remembered["items"][0]["id"]))
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
    assert results[0]["status"] == "created"


def test_deleted_list_does_not_include_merge_rows(
    db_session,
    sample_organization,
) -> None:
    sample_organization.name = "Kept Club"
    db_session.add(
        OrganizationMerge(
            merged_org_id=uuid4(),
            survivor_org_id=sample_organization.id,
            snapshot={"name": "Harbour Club", "email": "hidden@example.com"},
            moved_counts={},
        )
    )
    db_session.flush()
    listed = list_deleted_organizations(
        db_session,
        query="Harbour",
        cursor=None,
        limit=10,
    )
    assert listed["items"] == []


def test_forget_rejects_a_merge_row(db_session, sample_organization) -> None:
    row = OrganizationMerge(
        merged_org_id=sample_organization.id,
        survivor_org_id=sample_organization.id,
        snapshot={"name": "Harbour Club"},
        moved_counts={},
    )
    db_session.add(row)
    db_session.flush()
    try:
        forget_deleted_organization(db_session, row.id)
    except NotFoundError:
        return
    raise AssertionError("merge row was forgotten")


def test_admin_delete_blocks_reimport(
    monkeypatch,
    db_session,
    sample_organization,
) -> None:
    sample_organization.name = "Harbour Club"
    sample_organization.place_id = "ChIJadmin-delete"
    db_session.flush()
    org_id = sample_organization.id
    monkeypatch.setattr(db_session, "commit", db_session.flush)
    response = _crud_delete(
        _event("admin"),
        db_session,
        _RESOURCE_CONFIG["organizations"],
        str(sample_organization.id),
    )
    assert response["statusCode"] == 204
    _summary, results = process_import_payload(
        db_session,
        _payload(
            "Harbour Club",
            "00000000-0000-0000-0000-000000000001",
            place_id="ChIJadmin-delete",
        ),
        [],
        allow_org_updates=True,
    )
    _assert_not_recreated(results[0], _versioned(db_session, org_id))


def test_manager_delete_allows_reimport(
    monkeypatch,
    db_session,
    sample_organization,
) -> None:
    sample_organization.name = "Harbour Club"
    sample_organization.place_id = "ChIJmanager-delete"
    db_session.flush()
    org_id = sample_organization.id
    monkeypatch.setattr(db_session, "commit", db_session.flush)
    response = _crud_delete(
        _event("manager", "manager-sub"),
        db_session,
        _RESOURCE_CONFIG["organizations"],
        str(sample_organization.id),
    )
    assert response["statusCode"] == 204
    _summary, results = process_import_payload(
        db_session,
        _payload(
            "Harbour Club",
            "00000000-0000-0000-0000-000000000001",
            place_id="ChIJmanager-delete",
        ),
        [],
        allow_org_updates=True,
    )
    if _versioned(db_session, org_id):
        _assert_not_recreated(results[0], True)
        assert (
            db_session.scalar(
                select(Organization).where(
                    Organization.place_id == "ChIJmanager-delete"
                )
            )
            is None
        )
    else:
        assert results[0]["status"] == "created"


def _event(groups: str, user_sub: str = "admin-sub") -> dict:
    return {
        "requestContext": {
            "authorizer": {"userSub": user_sub, "groups": groups},
        },
    }
