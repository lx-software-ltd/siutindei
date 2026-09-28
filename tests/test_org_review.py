"""Organization review gate, import tagging, and bulk release."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.api.admin_imports_export import serialize_export_organization
from app.api.admin_imports_importer import process_import_payload
from app.api.admin_imports_jobs import (
    begin_import_job,
    fail_import_job,
    list_import_jobs,
)
from app.api.admin_org_review import (
    ReviewListFilters,
    _encode_review_cursor,
    _load_filtered_organizations,
    _parse_review_cursor,
)
from app.api.admin_org_review_actions import (
    ReviewBlockedError,
    _apply_decision,
    _apply_fields,
    _parse_fields,
)
from app.api.admin_resource_activity import _serialize_activity
from app.api.admin_resource_organization import _create_organization
from app.db.age_bounds import inclusive_age_bounds
from app.db.models import (
    Activity,
    ActivityPricing,
    ActivitySchedule,
    ImportJob,
    Location,
    Organization,
)
from app.db.models.enums import PricingType, ScheduleType
from app.db.queries import ActivitySearchFilters, build_search_query
from app.db.repositories import OrganizationRepository
from app.exceptions import ValidationError
from app.services.org_review import collect_issues, load_snapshots, summarize_snapshots
from app.services.org_review_sql import summarize_catalog
from psycopg.types.range import Range
from sqlalchemy import select


def test_collect_issues_flags_blockers() -> None:
    organization = Organization(
        id=uuid4(),
        name="Bare Org",
        manager_id="manager-1",
        description=None,
    )
    issues = collect_issues(organization, [], [], {}, {})
    codes = {issue.code for issue in issues}
    assert "missing_description" in codes
    assert "no_locations" in codes
    assert "no_activities" in codes
    assert any(issue.severity == "blocker" for issue in issues)


def test_import_create_is_pending_and_ignores_review_status(db_session) -> None:
    payload = {
        "organizations": [
            {
                "name": "Imported Pending Org",
                "manager_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "review_status": "approved",
                "description": "A class.",
            }
        ]
    }
    _summary, results = process_import_payload(db_session, payload, [])
    assert results[0]["status"] == "created"
    assert any(
        "review_status is ignored" in warning for warning in results[0]["warnings"]
    )
    org = db_session.execute(
        select(Organization).where(Organization.name == "Imported Pending Org")
    ).scalar_one()
    assert org.review_status == "pending_review"
    assert org.last_imported_at is not None


def test_import_update_keeps_approved_review(db_session, sample_organization) -> None:
    sample_organization.review_status = "approved"
    db_session.flush()
    payload = {
        "organizations": [
            {
                "name": sample_organization.name,
                "manager_id": sample_organization.manager_id,
                "description": "Updated copy",
            }
        ]
    }
    _summary, results = process_import_payload(
        db_session,
        payload,
        [],
        allow_org_updates=True,
    )
    assert results[0]["status"] == "updated"
    db_session.refresh(sample_organization)
    assert sample_organization.review_status == "approved"
    assert sample_organization.last_imported_at is not None


def test_admin_create_is_approved(db_session) -> None:
    repo = OrganizationRepository(db_session)
    created = _create_organization(
        repo,
        {
            "name": "Console Org",
            "manager_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
        },
    )
    assert created.review_status == "approved"


def test_approve_blocks_until_forced(db_session, sample_organization) -> None:
    sample_organization.review_status = "pending_review"
    db_session.flush()
    try:
        _apply_decision(
            db_session,
            sample_organization,
            "approve",
            force=False,
            notes=None,
            status=None,
            reviewer_sub="admin-sub",
            notes_provided=False,
        )
        raise AssertionError("expected blockers")
    except ReviewBlockedError as exc:
        assert exc.issues
    _apply_decision(
        db_session,
        sample_organization,
        "approve",
        force=True,
        notes="ship it",
        status=None,
        reviewer_sub="admin-sub",
        notes_provided=True,
    )
    assert sample_organization.review_status == "approved"
    assert sample_organization.reviewed_by == "admin-sub"
    assert sample_organization.review_notes == "ship it"


def test_bulk_fields_sets_source_url_and_note(
    db_session, sample_organization
) -> None:
    repo = OrganizationRepository(db_session)
    fields = _parse_fields(
        {
            "source_url": "https://review.test",
            "source_note": "called the venue",
        }
    )
    _apply_fields(repo, sample_organization, fields)
    assert sample_organization.source_url == "https://review.test"
    assert sample_organization.source_note == "called the venue"


def test_bulk_fields_sets_email(db_session, sample_organization) -> None:
    repo = OrganizationRepository(db_session)
    _apply_fields(
        repo,
        sample_organization,
        {"email": "studio@example.com", "review_notes": "called them"},
    )
    assert sample_organization.email == "studio@example.com"
    assert sample_organization.review_notes == "called them"


def test_inclusive_age_bounds_from_canonical_range() -> None:
    assert inclusive_age_bounds(Range(0, 19, bounds="[)")) == (0, 18)
    assert inclusive_age_bounds(Range(0, 18, bounds="[]")) == (0, 18)
    assert inclusive_age_bounds("[0,19)") == (0, 18)


def test_default_age_range_matches_database_upper(
    db_session,
    sample_organization,
    sample_activity_category,
) -> None:
    activity = Activity(
        org_id=sample_organization.id,
        category_id=sample_activity_category.id,
        name="Open Age Class",
        description="All ages",
        age_range=Range(0, 18, bounds="[]"),
    )
    db_session.add(activity)
    db_session.flush()
    db_session.refresh(activity)
    issues = collect_issues(
        sample_organization,
        [],
        [activity],
        {str(activity.id): 1},
        {str(activity.id): 1},
    )
    assert "default_age_range" in {issue.code for issue in issues}
    assert _serialize_activity(activity)["age_max"] == 18
    assert _serialize_activity(activity)["age_min"] == 0


def test_sql_summary_matches_python_snapshots(db_session, sample_organization) -> None:
    db_session.flush()
    organizations = list(db_session.scalars(select(Organization)).all())
    snapshots = load_snapshots(db_session, organizations)
    assert summarize_catalog(db_session) == summarize_snapshots(snapshots)


def test_review_list_orders_by_name_and_blocker_filter(
    db_session,
    sample_geographic_area,
    sample_activity_category,
) -> None:
    source = f"queue-{uuid4().hex[:8]}"
    ready = Organization(
        name=f"AAA Ready {source}",
        manager_id="00000000-0000-0000-0000-000000000031",
        description="Ready to release",
        source=source,
        review_status="pending_review",
    )
    blocked = Organization(
        name=f"ZZZ Blocked {source}",
        manager_id="00000000-0000-0000-0000-000000000032",
        description=None,
        source=source,
        review_status="pending_review",
    )
    db_session.add_all([ready, blocked])
    db_session.flush()
    location = Location(
        org_id=ready.id,
        area_id=sample_geographic_area.id,
        address="1 Ready Street",
        lat=Decimal("22.100000"),
        lng=Decimal("114.100000"),
    )
    db_session.add(location)
    db_session.flush()
    activity = Activity(
        org_id=ready.id,
        category_id=sample_activity_category.id,
        name="Ready Class",
        description="Described",
        age_range=Range(5, 12, bounds="[]"),
    )
    db_session.add(activity)
    db_session.flush()
    db_session.add(
        ActivityPricing(
            activity_id=activity.id,
            location_id=location.id,
            pricing_type=PricingType.PER_CLASS,
            amount=Decimal("10.00"),
        )
    )
    db_session.add(
        ActivitySchedule(
            activity_id=activity.id,
            location_id=location.id,
            schedule_type=ScheduleType.WEEKLY,
            languages=["en"],
        )
    )
    db_session.flush()
    filters = ReviewListFilters(
        review_status="pending_review",
        source=source,
        import_job_id=None,
        status=None,
        issue=None,
        has_blockers=None,
        query=None,
        sort="name",
    )
    page = _load_filtered_organizations(db_session, filters, None, 1)
    assert [org.name for org in page] == [ready.name]
    cursor = _parse_review_cursor(_encode_review_cursor(page[0], "name"), "name")
    rest = _load_filtered_organizations(db_session, filters, cursor, 10)
    assert [org.name for org in rest] == [blocked.name]
    blocked_only = _load_filtered_organizations(
        db_session,
        ReviewListFilters(
            review_status=None,
            source=source,
            import_job_id=None,
            status=None,
            issue="missing_description",
            has_blockers=True,
            query=None,
            sort="name",
        ),
        None,
        10,
    )
    assert [org.name for org in blocked_only] == [blocked.name]


def test_export_omits_review_status_and_same_value_is_quiet(
    db_session,
    sample_organization,
) -> None:
    sample_organization.review_status = "approved"
    sample_organization.review_notes = "called"
    db_session.flush()
    exported = serialize_export_organization(
        sample_organization,
        [],
        [],
        [],
        [],
        {},
        ZoneInfo("UTC"),
        [],
    )
    assert "review_status" not in exported
    assert exported["review_notes"] == "called"
    _summary, results = process_import_payload(
        db_session,
        {
            "organizations": [
                {
                    "name": sample_organization.name,
                    "manager_id": sample_organization.manager_id,
                    "description": "Updated copy",
                    "review_status": "approved",
                    "review_notes": "called",
                }
            ]
        },
        [],
        allow_org_updates=True,
    )
    warnings = " ".join(results[0]["warnings"])
    assert "review_status" not in warnings
    assert "review_notes" not in warnings


def test_import_update_keeps_creating_job(db_session, sample_organization) -> None:
    created = ImportJob(
        object_key=f"admin/imports/{uuid4().hex}.json",
        dry_run=False,
        summary={},
        results=[],
        file_warnings=[],
    )
    later = ImportJob(
        object_key=f"admin/imports/{uuid4().hex}.json",
        dry_run=False,
        summary={},
        results=[],
        file_warnings=[],
    )
    db_session.add_all([created, later])
    db_session.flush()
    sample_organization.import_job_id = created.id
    sample_organization.review_status = "approved"
    db_session.flush()
    process_import_payload(
        db_session,
        {
            "organizations": [
                {
                    "name": sample_organization.name,
                    "manager_id": sample_organization.manager_id,
                    "description": "Updated copy",
                    "review_status": "pending_review",
                }
            ]
        },
        [],
        allow_org_updates=True,
        import_job_id=later.id,
    )
    db_session.refresh(sample_organization)
    assert sample_organization.import_job_id == created.id
    assert sample_organization.review_status == "approved"
    assert sample_organization.last_imported_at is not None


def test_bulk_status_sets_owner_source(db_session, sample_organization) -> None:
    repo = OrganizationRepository(db_session)
    _apply_fields(repo, sample_organization, {"status": "hidden"})
    assert sample_organization.status == "hidden"
    assert sample_organization.status_source == "owner"
    try:
        _apply_fields(repo, sample_organization, {"manager_id": ""})
        raise AssertionError("empty manager id should fail")
    except ValidationError as exc:
        assert exc.field == "manager_id"


def test_import_job_failure_and_history_cursor(db_session) -> None:
    older = ImportJob(
        object_key=f"admin/imports/{uuid4().hex}.json",
        dry_run=True,
        status="completed",
        summary={"organizations": {"created": 0}},
        results=[],
        file_warnings=[],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(older)
    db_session.flush()
    started = begin_import_job(db_session, older.object_key)
    assert started.id == older.id
    assert started.status == "running"
    assert started.dry_run is False
    fail_import_job(db_session, started.id, "RuntimeError")
    db_session.refresh(started)
    assert started.status == "failed"
    assert started.summary == {"error": "RuntimeError"}
    newer = ImportJob(
        object_key=f"admin/imports/{uuid4().hex}.json",
        dry_run=False,
        status="completed",
        summary={},
        results=[],
        file_warnings=[],
        created_at=datetime(2099, 2, 1, tzinfo=timezone.utc),
    )
    db_session.add(newer)
    db_session.flush()
    page = list_import_jobs(db_session, limit=1, cursor=None)
    assert page[0].id == newer.id
    rest = list_import_jobs(db_session, limit=500, cursor=newer.id)
    assert older.id in {job.id for job in rest}
    assert newer.id not in {job.id for job in rest}


def test_search_gate_is_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("ORG_REVIEW_GATE_ENABLED", raising=False)
    closed = str(build_search_query(ActivitySearchFilters()).whereclause)
    assert "review_status" not in closed
    monkeypatch.setenv("ORG_REVIEW_GATE_ENABLED", "true")
    opened = str(build_search_query(ActivitySearchFilters()).whereclause)
    assert "review_status" in opened
