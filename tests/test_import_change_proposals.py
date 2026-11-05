"""Queued import changes."""

from uuid import uuid4

import pytest
from app.api.admin_imports_importer import process_import_payload
from app.db.models import CatalogVersion, ImportChangeProposal, Organization
from app.db.repositories.import_baseline import list_pending
from app.db.repositories.import_change_proposal import (
    accept_all,
    accept_proposal,
    dismiss_proposal,
)
from sqlalchemy import func, select, text
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


def _proposal(session: Session, org_id: object) -> ImportChangeProposal:
    return session.scalars(
        select(ImportChangeProposal).where(ImportChangeProposal.org_id == org_id)
    ).one()


def test_pending_row_is_replaced_by_a_newer_value(test_engine) -> None:
    name = f"Replace Org {uuid4()}"
    manager_id = "00000000-0000-0000-0000-000000000081"
    with Session(test_engine) as session:
        org = Organization(name=name, description="Original", manager_id=manager_id)
        session.add(org)
        session.flush()
        _remember(session, org)
        session.commit()
        org_id = org.id
    _edit_later(test_engine, org_id, description="Admin edit")
    with Session(test_engine) as session:
        process_import_payload(
            session,
            _file(name, manager_id, description="First file"),
            [],
            allow_org_updates=True,
        )
        first_id = _proposal(session, org_id).id
    with Session(test_engine) as session:
        process_import_payload(
            session,
            _file(name, manager_id, description="Second file"),
            [],
            allow_org_updates=True,
        )
        row = _proposal(session, org_id)
        assert row.id == first_id
        assert row.proposed_value == "Second file"
        assert row.status == "pending"


def test_dismissed_value_does_not_return(test_engine) -> None:
    name = f"Dismiss Org {uuid4()}"
    manager_id = "00000000-0000-0000-0000-000000000082"
    with Session(test_engine) as session:
        org = Organization(name=name, description="Original", manager_id=manager_id)
        session.add(org)
        session.flush()
        _remember(session, org)
        session.commit()
        org_id = org.id
    _edit_later(test_engine, org_id, description="Admin edit")
    with Session(test_engine) as session:
        process_import_payload(
            session,
            _file(name, manager_id, description="From file"),
            [],
            allow_org_updates=True,
        )
        dismiss_proposal(session, _proposal(session, org_id).id, "admin-sub")
        session.commit()
    with Session(test_engine) as session:
        process_import_payload(
            session,
            _file(name, manager_id, description="From file"),
            [],
            allow_org_updates=True,
        )
        rows = session.scalars(
            select(ImportChangeProposal).where(ImportChangeProposal.org_id == org_id)
        ).all()
        assert [row.status for row in rows] == ["dismissed"]


def test_accept_writes_the_field_and_marks_applied(test_engine) -> None:
    name = f"Accept Org {uuid4()}"
    manager_id = "00000000-0000-0000-0000-000000000083"
    with Session(test_engine) as session:
        org = Organization(name=name, description="Original", manager_id=manager_id)
        session.add(org)
        session.flush()
        _remember(session, org)
        session.commit()
        org_id = org.id
    _edit_later(test_engine, org_id, description="Admin edit")
    with Session(test_engine) as session:
        process_import_payload(
            session,
            _file(name, manager_id, description="From file"),
            [],
            allow_org_updates=True,
        )
        before = session.scalar(
            select(func.count())
            .select_from(CatalogVersion)
            .where(CatalogVersion.entity_id == org_id)
        )
        if session.get_bind().dialect.name == "postgresql":
            session.execute(
                text("SELECT set_config('app.current_user_id', :user_id, true)"),
                {"user_id": "admin-sub"},
            )
        accept_proposal(session, _proposal(session, org_id).id, "admin-sub")
        session.commit()
    with Session(test_engine) as session:
        found = session.get(Organization, org_id)
        assert found is not None
        assert found.description == "From file"
        assert _proposal(session, org_id).status == "applied"
        if session.get_bind().dialect.name == "postgresql":
            after = session.scalar(
                select(func.count())
                .select_from(CatalogVersion)
                .where(CatalogVersion.entity_id == org_id)
            )
            latest = session.scalars(
                select(CatalogVersion)
                .where(CatalogVersion.entity_id == org_id)
                .order_by(CatalogVersion.version.desc())
            ).first()
            assert after == before + 1
            assert latest is not None
            assert latest.user_id == "admin-sub"


def test_accept_all_is_scoped_to_one_organization(test_engine) -> None:
    manager_id = "00000000-0000-0000-0000-000000000084"
    names = [f"Bulk {index} {uuid4()}" for index in range(2)]
    org_ids = []
    with Session(test_engine) as session:
        for org_name in names:
            org = Organization(
                name=org_name, description="Original", manager_id=manager_id
            )
            session.add(org)
            session.flush()
            _remember(session, org)
            org_ids.append(org.id)
        session.commit()
    for org_id in org_ids:
        _edit_later(test_engine, org_id, description="Admin edit")
    with Session(test_engine) as session:
        process_import_payload(
            session,
            {
                "organizations": [
                    {
                        "name": org_name,
                        "description": "From file",
                        "manager_id": manager_id,
                    }
                    for org_name in names
                ]
            },
            [],
            allow_org_updates=True,
        )
        applied = accept_all(session, "admin-sub", org_id=org_ids[0])
        session.commit()
        assert applied == 1
    with Session(test_engine) as session:
        first = session.get(Organization, org_ids[0])
        second = session.get(Organization, org_ids[1])
        assert first is not None and first.description == "From file"
        assert second is not None and second.description == "Admin edit"


def test_deleted_entity_is_dismissed_on_read(test_engine) -> None:
    name = f"Gone Org {uuid4()}"
    manager_id = "00000000-0000-0000-0000-000000000085"
    with Session(test_engine) as session:
        org = Organization(name=name, description="Original", manager_id=manager_id)
        session.add(org)
        session.flush()
        _remember(session, org)
        session.commit()
        org_id = org.id
    _edit_later(test_engine, org_id, description="Admin edit")
    with Session(test_engine) as session:
        process_import_payload(
            session,
            _file(name, manager_id, description="From file"),
            [],
            allow_org_updates=True,
        )
        org = session.get(Organization, org_id)
        assert org is not None
        session.delete(org)
        session.commit()
    with Session(test_engine) as session:
        page, _cursor = list_pending(session, org_id=org_id)
        session.commit()
        assert page == []
        assert _proposal(session, org_id).status == "dismissed"
