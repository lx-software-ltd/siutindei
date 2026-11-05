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


def _queue(session: Session, **fields: object) -> ImportChangeProposal:
    row = ImportChangeProposal(status="pending", **fields)
    session.add(row)
    session.flush()
    session.execute(text("SELECT set_config('app.current_user_id', 'admin-sub', true)"))
    return row


def test_accept_age_keeps_the_other_bound(db_session, sample_activity) -> None:
    from app.db.age_bounds import inclusive_age_bounds

    row = _queue(
        db_session,
        entity_type="activity",
        entity_id=sample_activity.id,
        org_id=sample_activity.org_id,
        field="age_min",
        base_value=5,
        current_value=5,
        proposed_value=8,
    )
    accept_proposal(db_session, row.id, "admin-sub")
    db_session.refresh(sample_activity)
    assert inclusive_age_bounds(sample_activity.age_range) == (8, 12)


def test_accept_status_records_the_importer(db_session, sample_organization) -> None:
    sample_organization.status_source = "provider"
    row = _queue(
        db_session,
        entity_type="organization",
        entity_id=sample_organization.id,
        org_id=sample_organization.id,
        field="status",
        base_value="operational",
        current_value="operational",
        proposed_value="hidden",
    )
    accept_proposal(db_session, row.id, "admin-sub")
    db_session.refresh(sample_organization)
    assert sample_organization.status == "hidden"
    assert sample_organization.status_source == "importer"


def test_accept_refuses_an_owner_listing_status(
    db_session, sample_organization
) -> None:
    from app.exceptions import ValidationError

    sample_organization.status = "operational"
    sample_organization.status_source = "owner"
    row = _queue(
        db_session,
        entity_type="organization",
        entity_id=sample_organization.id,
        org_id=sample_organization.id,
        field="status",
        base_value="operational",
        current_value="operational",
        proposed_value="hidden",
    )
    with pytest.raises(ValidationError, match="owner listing status"):
        accept_proposal(db_session, row.id, "admin-sub")
    db_session.refresh(sample_organization)
    db_session.refresh(row)
    assert sample_organization.status == "operational"
    assert row.status == "pending"


def test_accept_phone_keeps_the_country_code(db_session, sample_organization) -> None:
    sample_organization.phone_country_code = "HK"
    sample_organization.phone_number = "21234567"
    row = _queue(
        db_session,
        entity_type="organization",
        entity_id=sample_organization.id,
        org_id=sample_organization.id,
        field="phone_number",
        base_value="21234567",
        current_value="21234567",
        proposed_value="29876543",
    )
    accept_proposal(db_session, row.id, "admin-sub")
    db_session.refresh(sample_organization)
    assert sample_organization.phone_number == "29876543"
    assert sample_organization.phone_country_code == "HK"


def test_accept_category_name_sets_the_category(
    db_session, sample_activity, sample_activity_category
) -> None:
    from app.db.models import ActivityCategory

    other = ActivityCategory(name=f"Other Sport {uuid4()}", display_order=1)
    db_session.add(other)
    db_session.flush()
    row = _queue(
        db_session,
        entity_type="activity",
        entity_id=sample_activity.id,
        org_id=sample_activity.org_id,
        field="source_category_name",
        base_value=sample_activity_category.name,
        current_value=sample_activity_category.name,
        proposed_value=other.name,
    )
    accept_proposal(db_session, row.id, "admin-sub")
    db_session.refresh(sample_activity)
    assert sample_activity.category_id == other.id
    assert sample_activity.source_category_name == other.name


def test_accept_pricing_amount(db_session, sample_pricing) -> None:
    from decimal import Decimal

    row = _queue(
        db_session,
        entity_type="pricing",
        entity_id=sample_pricing.id,
        org_id=sample_pricing.activity.org_id,
        field="amount",
        base_value="150.00",
        current_value="150.00",
        proposed_value="200.00",
    )
    accept_proposal(db_session, row.id, "admin-sub")
    db_session.refresh(sample_pricing)
    assert sample_pricing.amount == Decimal("200.00")


def test_accept_schedule_entries(db_session, sample_activity, sample_location) -> None:
    from app.db.models import ActivitySchedule, ScheduleType

    schedule = ActivitySchedule(
        activity_id=sample_activity.id,
        location_id=sample_location.id,
        schedule_type=ScheduleType.WEEKLY,
        languages=["en"],
    )
    db_session.add(schedule)
    db_session.flush()
    row = _queue(
        db_session,
        entity_type="schedule",
        entity_id=schedule.id,
        org_id=sample_activity.org_id,
        field="weekly_entries",
        base_value=[],
        current_value=[],
        proposed_value=[
            {
                "day_of_week_utc": 1,
                "start_minutes_utc": 540,
                "end_minutes_utc": 600,
            }
        ],
    )
    accept_proposal(db_session, row.id, "admin-sub")
    db_session.refresh(schedule)
    assert len(schedule.entries) == 1
    assert schedule.entries[0].start_minutes_utc == 540


def test_bad_cursor_is_rejected(db_session) -> None:
    from app.exceptions import ValidationError

    with pytest.raises(ValidationError, match="cursor"):
        list_pending(db_session, cursor="not-a-cursor")


def test_accept_all_requires_a_scope(db_session) -> None:
    from app.exceptions import ValidationError

    with pytest.raises(ValidationError, match="org_id or import_job_id"):
        accept_all(db_session, "admin-sub")


def test_handler_lists_and_dismisses(test_engine, monkeypatch) -> None:
    import json

    from app.api.admin_import_changes import handle_import_changes

    monkeypatch.setattr("app.api.admin_import_changes.get_engine", lambda: test_engine)
    with Session(test_engine) as session:
        org = Organization(
            name=f"Handler Org {uuid4()}",
            description="Original",
            manager_id="00000000-0000-0000-0000-000000000086",
        )
        session.add(org)
        session.flush()
        row = ImportChangeProposal(
            entity_type="organization",
            entity_id=org.id,
            org_id=org.id,
            field="description",
            base_value="Original",
            current_value="Admin",
            proposed_value="From file",
            status="pending",
        )
        session.add(row)
        session.commit()
        org_id = str(org.id)
        proposal_id = str(row.id)
    event = {
        "requestContext": {"authorizer": {"groups": "admin", "userSub": "admin-sub"}},
        "queryStringParameters": {"org_id": org_id},
    }
    listed = handle_import_changes(event, "GET", None, None)
    body = json.loads(listed["body"])
    assert listed["statusCode"] == 200
    assert body["items"][0]["field"] == "description"
    dismissed = handle_import_changes(event, "POST", proposal_id, "dismiss")
    assert dismissed["statusCode"] == 200
    with Session(test_engine) as session:
        found = session.get(ImportChangeProposal, proposal_id)
        assert found is not None
        assert found.status == "dismissed"


def test_owner_status_is_not_queued(test_engine) -> None:
    name = f"Owner Status {uuid4()}"
    manager_id = "00000000-0000-0000-0000-000000000087"
    with Session(test_engine) as session:
        org = Organization(
            name=name,
            description="Original",
            manager_id=manager_id,
            status="operational",
            status_source="owner",
        )
        session.add(org)
        session.flush()
        _remember(session, org)
        session.commit()
        org_id = org.id
    with Session(test_engine) as session:
        _summary, results = process_import_payload(
            session,
            _file(name, manager_id, status="hidden"),
            [],
            allow_org_updates=True,
        )
        assert results[0]["status"] == "unchanged"
        pending = session.scalars(
            select(ImportChangeProposal).where(ImportChangeProposal.org_id == org_id)
        ).all()
        assert pending == []
        found = session.get(Organization, org_id)
        assert found is not None
        assert found.status == "operational"
        assert found.status_source == "owner"
