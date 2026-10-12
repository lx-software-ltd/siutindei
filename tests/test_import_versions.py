"""Import decisions against catalog version 1."""

from uuid import uuid4

from app.api.admin_imports_importer import process_import_payload
from app.db.models import (
    ActivityCategory,
    CatalogVersion,
    Organization,
    OrganizationMerge,
)
from app.services.catalog_version_payload import organization_payload
from sqlalchemy import select
from sqlalchemy.orm import Session


def _remember(session: Session, org: Organization, **overrides: object) -> None:
    """Store version 1. A Postgres trigger may already have written it."""
    snapshot = organization_payload(org)
    snapshot.update(overrides)
    existing = session.scalars(
        select(CatalogVersion).where(
            CatalogVersion.entity_type == "organization",
            CatalogVersion.entity_id == org.id,
            CatalogVersion.version == 1,
        )
    ).first()
    if existing is not None:
        existing.snapshot = snapshot
        existing.reason = None
        session.flush()
        return
    session.add(
        CatalogVersion(
            entity_type="organization",
            entity_id=org.id,
            org_id=org.id,
            version=1,
            action="created",
            snapshot=snapshot,
            txid=1,
        )
    )
    session.flush()


def _edit_later(engine: object, org_id: object, **fields: object) -> None:
    """Apply an admin edit in a later transaction so version 1 stays put."""
    with Session(engine) as session:
        org = session.get(Organization, org_id)
        assert org is not None
        for key, value in fields.items():
            setattr(org, key, value)
        session.commit()


def _file(name: str, manager_id: str, **extra: object) -> dict:
    body = {
        "name": name,
        "description": "Original",
        "manager_id": manager_id,
    }
    body.update(extra)
    return {"organizations": [body]}


def test_identical_reimport_is_unchanged(test_engine) -> None:
    name = f"Versioned Org {uuid4()}"
    manager_id = "00000000-0000-0000-0000-000000000041"
    with Session(test_engine) as session:
        org = Organization(
            name=name,
            description="Original",
            manager_id=manager_id,
        )
        session.add(org)
        session.flush()
        _remember(session, org)
        session.commit()
        org_id = org.id

    with Session(test_engine) as session:
        summary, results = process_import_payload(
            session,
            _file(name, manager_id),
            [],
            allow_org_updates=True,
        )

    assert results[0]["status"] == "unchanged"
    assert summary["organizations"]["unchanged"] == 1
    with Session(test_engine) as session:
        found = session.get(Organization, org_id)
        assert found is not None
        assert found.description == "Original"
        assert found.version == 1


def test_file_matching_version_1_keeps_admin_edit(test_engine) -> None:
    name = f"Edited Org {uuid4()}"
    manager_id = "00000000-0000-0000-0000-000000000042"
    with Session(test_engine) as session:
        org = Organization(
            name=name,
            description="Original",
            manager_id=manager_id,
        )
        session.add(org)
        session.flush()
        _remember(session, org)
        session.commit()
        org_id = org.id
    _edit_later(test_engine, org_id, description="Admin edit")

    with Session(test_engine) as session:
        _summary, results = process_import_payload(
            session,
            _file(name, manager_id),
            [],
            allow_org_updates=True,
        )

    assert results[0]["status"] == "unchanged"
    with Session(test_engine) as session:
        found = session.get(Organization, org_id)
        assert found is not None
        assert found.description == "Admin edit"


def test_changed_source_updates_and_warns_when_admin_edited(test_engine) -> None:
    name = f"Changed Org {uuid4()}"
    manager_id = "00000000-0000-0000-0000-000000000043"
    with Session(test_engine) as session:
        org = Organization(
            name=name,
            description="Original",
            manager_id=manager_id,
        )
        session.add(org)
        session.flush()
        _remember(session, org)
        session.commit()
        org_id = org.id
    _edit_later(test_engine, org_id, description="Admin edit")

    with Session(test_engine) as session:
        _summary, results = process_import_payload(
            session,
            _file(name, manager_id, description="From file"),
            [],
            allow_org_updates=True,
        )

    assert results[0]["status"] == "updated"
    assert any("admin edits" in warning for warning in results[0]["warnings"])
    with Session(test_engine) as session:
        found = session.get(Organization, org_id)
        assert found is not None
        assert found.description == "From file"


def test_removed_org_matching_version_1_is_not_recreated(test_engine) -> None:
    name = f"Removed Org {uuid4()}"
    manager_id = "00000000-0000-0000-0000-000000000044"
    with Session(test_engine) as session:
        org = Organization(
            name=name,
            description="Original",
            manager_id=manager_id,
        )
        session.add(org)
        session.flush()
        _remember(session, org)
        session.delete(org)
        session.commit()

    with Session(test_engine) as session:
        summary, results = process_import_payload(
            session,
            _file(
                name,
                manager_id,
                activities=[{"name": "Should not return", "age_min": 5, "age_max": 8}],
            ),
            [],
            allow_org_updates=True,
        )

    assert results[0]["status"] == "unchanged"
    assert any("not imported again" in warning for warning in results[0]["warnings"])
    assert summary["activities"]["skipped"] == 1
    with Session(test_engine) as session:
        found = session.query(Organization).filter(Organization.name == name).all()
        assert found == []


def test_new_activity_on_unchanged_org_is_created(test_engine) -> None:
    name = f"Live Org {uuid4()}"
    manager_id = "00000000-0000-0000-0000-000000000045"
    with Session(test_engine) as session:
        category = ActivityCategory(name=f"Version Class {uuid4()}", display_order=0)
        org = Organization(
            name=name,
            description="Original",
            manager_id=manager_id,
        )
        session.add(category)
        session.add(org)
        session.flush()
        _remember(session, org)
        session.commit()
        category_id = category.id

    with Session(test_engine) as session:
        summary, results = process_import_payload(
            session,
            _file(
                name,
                manager_id,
                activities=[
                    {
                        "name": f"New Class {uuid4()}",
                        "age_min": 5,
                        "age_max": 8,
                        "category_id": str(category_id),
                    }
                ],
            ),
            [],
            allow_org_updates=True,
        )

    assert results[0]["status"] == "unchanged"
    assert summary["activities"]["created"] == 1


def test_merge_name_does_not_duplicate_survivor(test_engine) -> None:
    manager_id = "00000000-0000-0000-0000-000000000046"
    source_name = f"Merged Source {uuid4()}"
    with Session(test_engine) as session:
        survivor = Organization(
            name=f"Survivor {uuid4()}",
            description="Original",
            manager_id=manager_id,
        )
        session.add(survivor)
        session.flush()
        session.add(
            OrganizationMerge(
                merged_org_id=uuid4(),
                survivor_org_id=survivor.id,
                kind="merge",
                snapshot={"name": source_name, "description": "Original"},
                moved_counts={},
            )
        )
        session.commit()
        survivor_id = survivor.id

    with Session(test_engine) as session:
        _summary, results = process_import_payload(
            session,
            _file(source_name, manager_id),
            [],
            allow_org_updates=True,
        )

    assert results[0]["status"] == "unchanged"
    assert results[0]["id"] == str(survivor_id)
    with Session(test_engine) as session:
        names = session.query(Organization).all()
        assert sum(1 for org in names if org.name == source_name) == 0
