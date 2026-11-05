"""Baselines record what the source last said."""

from uuid import uuid4

import pytest
from app.api.admin_imports_importer import process_import_payload
from app.db.models import Activity, ImportBaseline, Organization
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.test_import_versions import (
    _edit_later,
    _file,
    _remember,
    reset_import_mode,
)


@pytest.fixture(autouse=True)
def _merge_defaults(test_engine) -> None:
    reset_import_mode(test_engine)


def _baseline(session: Session, entity_id: object) -> ImportBaseline | None:
    return session.scalars(
        select(ImportBaseline).where(ImportBaseline.entity_id == entity_id)
    ).first()


def test_baseline_written_for_each_outcome(test_engine) -> None:
    manager_id = "00000000-0000-0000-0000-000000000071"
    created_name = f"Baseline New {uuid4()}"
    same_name = f"Baseline Same {uuid4()}"
    changed_name = f"Baseline Changed {uuid4()}"
    with Session(test_engine) as session:
        same = Organization(
            name=same_name, description="Original", manager_id=manager_id
        )
        changed = Organization(
            name=changed_name,
            description="Original",
            manager_id=manager_id,
        )
        session.add_all([same, changed])
        session.flush()
        _remember(session, same)
        _remember(session, changed)
        session.commit()
        same_id, changed_id = same.id, changed.id
    _edit_later(test_engine, changed_id, description="Admin edit")

    with Session(test_engine) as session:
        process_import_payload(
            session,
            {
                "organizations": [
                    {
                        "name": created_name,
                        "description": "New",
                        "manager_id": manager_id,
                    },
                    {
                        "name": same_name,
                        "description": "Original",
                        "manager_id": manager_id,
                    },
                    {
                        "name": changed_name,
                        "description": "From file",
                        "manager_id": manager_id,
                    },
                ]
            },
            [],
            allow_org_updates=False,
        )
        created = session.scalars(
            select(Organization).where(Organization.name == created_name)
        ).one()
        assert _baseline(session, created.id) is not None
        assert _baseline(session, same_id) is not None
        assert _baseline(session, changed_id) is not None


def test_version_1_is_the_fallback_until_a_baseline_exists(test_engine) -> None:
    name = f"Fallback Org {uuid4()}"
    manager_id = "00000000-0000-0000-0000-000000000072"
    with Session(test_engine) as session:
        org = Organization(name=name, description="Original", manager_id=manager_id)
        session.add(org)
        session.flush()
        _remember(session, org)
        session.commit()
        org_id = org.id

    with Session(test_engine) as session:
        assert _baseline(session, org_id) is None
        _summary, results = process_import_payload(
            session,
            _file(name, manager_id, description="From file"),
            [],
            allow_org_updates=True,
        )
        assert results[0]["status"] == "updated"
        assert _baseline(session, org_id) is not None


def test_renamed_activity_is_found_through_the_baseline(test_engine) -> None:
    name = f"Activity Org {uuid4()}"
    manager_id = "00000000-0000-0000-0000-000000000073"
    from app.db.models import ActivityCategory

    with Session(test_engine) as session:
        category = ActivityCategory(name=f"Baseline Class {uuid4()}", display_order=0)
        session.add(category)
        session.commit()
        category_id = str(category.id)
    with Session(test_engine) as session:
        _summary, results = process_import_payload(
            session,
            {
                "organizations": [
                    {
                        "name": name,
                        "description": "Original",
                        "manager_id": manager_id,
                        "activities": [
                            {
                                "name": "Swim",
                                "age_min": 5,
                                "age_max": 8,
                                "category_id": category_id,
                            }
                        ],
                    }
                ]
            },
            [],
            allow_org_updates=True,
        )
        org_id = results[0]["id"]
    with Session(test_engine) as session:
        activity = session.scalars(
            select(Activity).where(Activity.org_id == org_id)
        ).one()
        activity.name = "Swimming"
        session.commit()
        activity_id = activity.id

    with Session(test_engine) as session:
        _summary, results = process_import_payload(
            session,
            {
                "organizations": [
                    {
                        "name": name,
                        "description": "Original",
                        "manager_id": manager_id,
                        "activities": [{"name": "Swim", "age_min": 6, "age_max": 8}],
                    }
                ]
            },
            [],
            allow_org_updates=True,
        )
        activities = [row for row in results if row["type"] == "activities"]
        assert activities[0]["status"] == "updated"
        assert activities[0]["id"] == str(activity_id)
        found = session.get(Activity, activity_id)
        assert found is not None
        assert found.name == "Swimming"
        from app.db.age_bounds import inclusive_age_bounds

        assert inclusive_age_bounds(found.age_range) == (6, 8)


def test_dry_run_leaves_no_baseline(test_engine) -> None:
    name = f"Dry Org {uuid4()}"
    manager_id = "00000000-0000-0000-0000-000000000074"
    with Session(test_engine) as session:
        process_import_payload(
            session,
            _file(name, manager_id),
            [],
            dry_run=True,
            allow_org_updates=True,
        )
        session.rollback()
    with Session(test_engine) as session:
        orgs = session.scalars(
            select(Organization).where(Organization.name == name)
        ).all()
        assert orgs == []
        named = [
            row
            for row in session.scalars(select(ImportBaseline)).all()
            if (row.payload or {}).get("name") == name
        ]
        assert named == []


def test_reimport_of_a_created_row_has_no_kept_later_warning(test_engine) -> None:
    name = f"Created Twice {uuid4()}"
    manager_id = "00000000-0000-0000-0000-000000000075"
    payload = _file(name, manager_id)
    with Session(test_engine) as session:
        process_import_payload(session, payload, [], allow_org_updates=True)
        session.commit()
    with Session(test_engine) as session:
        _summary, results = process_import_payload(
            session, payload, [], allow_org_updates=True
        )
    assert results[0]["status"] == "unchanged"
    assert results[0]["warnings"] == []
