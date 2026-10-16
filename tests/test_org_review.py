"""Organization review gate, import tagging, and bulk release."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from app.api.admin_imports_export import serialize_export_organization
from app.api.admin_imports_importer import process_import_payload
from app.api.admin_imports_jobs import (
    begin_import_job,
    begin_import_retry,
    fail_import_job,
    list_import_jobs,
)
from app.api.admin_org_review import (
    ReviewListFilters,
    _load_filtered_organizations,
    _map_locations,
    _parse_filters,
    _serialize_queue_item,
)
from app.api.admin_org_review_actions import (
    ReviewBlockedError,
    _apply_decision,
    _apply_fields,
    _parse_fields,
)
from app.api.admin_org_review_cursor import (
    encode_review_cursor,
    parse_review_cursor,
)
from app.api.admin_resource_activity import _serialize_activity
from app.api.admin_resource_organization import _create_organization
from app.db.age_bounds import inclusive_age_bounds
from app.db.models import (
    Activity,
    ActivityPricing,
    ActivitySchedule,
    CatalogVersion,
    GeographicArea,
    ImportJob,
    Location,
    Organization,
)
from app.db.models.enums import PricingType, ScheduleType
from app.db.queries import ActivitySearchFilters, build_search_query
from app.db.repositories import OrganizationRepository
from app.exceptions import ValidationError
from app.services.org_review import (
    ACTIVITY_ADDED_SINCE_REJECTED,
    ACTIVITY_ADDED_SINCE_REJECTED_MESSAGE,
    collect_issues,
    load_snapshots,
    summarize_snapshots,
)
from app.services.org_review_sql import BLOCKER_ISSUE_CODES, summarize_catalog
from psycopg.types.range import Range
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError


def test_collect_issues_flags_blockers() -> None:
    organization = Organization(
        id=uuid4(),
        name="Bare Org",
        manager_id="manager-1",
        description=None,
    )
    issues, _checks = collect_issues(organization, [], [], {}, {})
    codes = {issue.code for issue in issues}
    assert "missing_description" in codes
    assert "no_locations" in codes
    assert "no_activities" in codes
    assert any(issue.severity == "blocker" for issue in issues)


def test_activity_without_a_location_is_a_warning() -> None:
    organization = Organization(
        id=uuid4(),
        name="Harbour Club",
        manager_id="manager-1",
        description="Classes",
        review_status="approved",
    )
    activity = Activity(
        id=uuid4(),
        org_id=organization.id,
        category_id=uuid4(),
        name="Swim Class",
        description="Lane swimming",
        age_range=Range(5, 12, bounds="[]"),
    )
    issues, checks = collect_issues(
        organization,
        [],
        [activity],
        {str(activity.id): 1},
        {str(activity.id): 1},
        linked_activity_ids=set(),
    )
    _issues_without, checks_without = collect_issues(
        organization,
        [],
        [activity],
        {str(activity.id): 1},
        {str(activity.id): 1},
    )
    assert checks == checks_without + 1
    match = next(issue for issue in issues if issue.code == "activity_no_location")
    assert match.severity == "warning"
    assert match.message == "Activity has no location"
    assert "activity_no_location" not in BLOCKER_ISSUE_CODES


def test_hong_kong_name_gap_is_a_warning() -> None:
    organization = Organization(
        id=uuid4(),
        name="Harbour Club",
        manager_id="manager-1",
        description="Classes",
        name_translations={"zh": "海港会"},
        description_translations={"zh": "課程", "zh-HK": "課程"},
    )
    issues, _checks = collect_issues(organization, [], [], {}, {})
    messages = {issue.code: issue.message for issue in issues}
    assert messages["missing_zh_hk_name"] == "Hong Kong name is missing"
    assert "missing_zh_name" not in messages
    assert "missing_en_name" not in messages
    assert "missing_zh_description" not in messages


def test_blank_description_is_not_a_translation_warning() -> None:
    organization = Organization(
        id=uuid4(),
        name="Harbour Club",
        manager_id="manager-1",
        description="   ",
        name_translations={"zh": "海港会", "zh-HK": "海港會"},
    )
    issues, _checks = collect_issues(organization, [], [], {}, {})
    codes = {issue.code for issue in issues}
    assert "missing_description" in codes
    assert "missing_zh_description" not in codes
    assert "missing_zh_hk_description" not in codes
    assert "missing_en_description" not in codes


def test_english_name_gap_is_a_warning() -> None:
    organization = Organization(
        id=uuid4(),
        name=" ",
        manager_id="manager-1",
        description="Classes",
        name_translations={"zh": "海港会", "zh-HK": "海港會"},
        description_translations={"zh": "課程", "zh-HK": "課程"},
    )
    issues, _checks = collect_issues(organization, [], [], {}, {})
    codes = {issue.code for issue in issues}
    assert "missing_en_name" in codes
    assert "missing_zh_name" not in codes
    assert "missing_en_description" not in codes


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


def test_admin_create_starts_in_review(db_session) -> None:
    repo = OrganizationRepository(db_session)
    created = _create_organization(
        repo,
        {
            "name": "Console Org",
            "manager_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
        },
    )
    assert created.review_status == "pending_review"


def test_admin_create_defaults_manager_to_caller(db_session) -> None:
    repo = OrganizationRepository(db_session)
    caller = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    created = _create_organization(
        repo,
        {"name": "Caller Org"},
        default_manager_id=caller,
    )
    assert created.manager_id == caller
    assert created.review_status == "pending_review"


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


def test_bulk_fields_sets_source_url_and_note(db_session, sample_organization) -> None:
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


def test_bulk_fields_sets_website(db_session, sample_organization) -> None:
    repo = OrganizationRepository(db_session)
    _apply_fields(
        repo,
        sample_organization,
        {"website": " https://review.example "},
    )
    assert sample_organization.website == "https://review.example"


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
    issues, _checks = collect_issues(
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
    cursor = parse_review_cursor(encode_review_cursor(page[0], "name"), "name")
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
    assert exported["review_reason"] is None
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


def test_review_list_includes_orgs_created_or_updated_by_import(db_session) -> None:
    job = ImportJob(
        object_key=f"admin/imports/{uuid4().hex}.json",
        dry_run=False,
        summary={},
        results=[],
        file_warnings=[],
    )
    other = ImportJob(
        object_key=f"admin/imports/{uuid4().hex}.json",
        dry_run=False,
        summary={},
        results=[],
        file_warnings=[],
    )
    db_session.add_all([job, other])
    db_session.flush()
    created = Organization(
        name="Created By Job",
        manager_id="00000000-0000-0000-0000-000000000091",
        description="Created",
        import_job_id=job.id,
    )
    updated_version = Organization(
        name="Updated By Version",
        manager_id="00000000-0000-0000-0000-000000000092",
        description="Updated",
        import_job_id=other.id,
    )
    updated_result = Organization(
        name="Updated By Result",
        manager_id="00000000-0000-0000-0000-000000000093",
        description="Updated from the file",
    )
    skipped = Organization(
        name="Skipped Org",
        manager_id="00000000-0000-0000-0000-000000000094",
        description="Left alone",
    )
    child_only = Organization(
        name="Child Only",
        manager_id="00000000-0000-0000-0000-000000000095",
        description="Location changed",
    )
    db_session.add_all([created, updated_version, updated_result, skipped, child_only])
    db_session.flush()
    db_session.add(
        CatalogVersion(
            entity_type="organization",
            entity_id=updated_version.id,
            org_id=updated_version.id,
            version=2,
            action="updated",
            snapshot={"name": updated_version.name},
            txid=2,
            import_job_id=job.id,
        )
    )
    db_session.add(
        CatalogVersion(
            entity_type="location",
            entity_id=uuid4(),
            org_id=child_only.id,
            version=2,
            action="updated",
            snapshot={"address": "1 Side Street"},
            txid=3,
            import_job_id=job.id,
        )
    )
    db_session.add(
        CatalogVersion(
            entity_type="organization",
            entity_id=skipped.id,
            org_id=skipped.id,
            version=2,
            action="deleted",
            snapshot={"name": skipped.name},
            txid=4,
            import_job_id=job.id,
        )
    )
    job.results = [
        {
            "type": "organizations",
            "status": "updated",
            "id": str(updated_result.id),
            "key": updated_result.name,
        },
        {
            "type": "organizations",
            "status": "skipped",
            "id": str(skipped.id),
            "key": skipped.name,
        },
        {
            "type": "organizations",
            "status": "unchanged",
            "id": str(child_only.id),
            "key": child_only.name,
        },
        {
            "type": "locations",
            "status": "updated",
            "id": str(uuid4()),
            "key": "Somewhere",
        },
        {"type": "organizations", "status": "created", "id": "not-a-uuid"},
    ]
    db_session.flush()
    found = _load_filtered_organizations(
        db_session,
        _review_filters(import_job_id=job.id),
        None,
        20,
    )
    assert {org.id for org in found} == {
        created.id,
        updated_version.id,
        updated_result.id,
    }


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
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
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
    kept = ImportJob(
        object_key=f"admin/imports/{uuid4().hex}.json",
        dry_run=False,
        status="completed",
        summary={"captured_categories": 2},
        results=[{"type": "organizations", "key": "Kept", "status": "created"}],
        file_warnings=[],
    )
    db_session.add(kept)
    db_session.flush()
    running = begin_import_retry(db_session, kept)
    fail_import_job(db_session, running.id, "RuntimeError", keep_completed=True)
    db_session.refresh(kept)
    assert kept.status == "completed"
    assert kept.summary == {"captured_categories": 2}
    assert kept.results[0]["key"] == "Kept"
    assert kept.file_warnings == ["Retry failed: RuntimeError"]
    newer = ImportJob(
        object_key=f"admin/imports/{uuid4().hex}.json",
        dry_run=False,
        status="completed",
        summary={},
        results=[],
        file_warnings=[],
        created_at=datetime(2099, 2, 1, tzinfo=UTC),
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


def _review_filters(**overrides: object) -> ReviewListFilters:
    values: dict[str, object] = {
        "review_status": None,
        "source": None,
        "import_job_id": None,
        "status": None,
        "issue": None,
        "has_blockers": None,
        "query": None,
        "sort": "name",
    }
    values.update(overrides)
    return ReviewListFilters(**values)  # type: ignore[arg-type]


def test_parse_filters_reads_neighbourhood_and_map_pins() -> None:
    area_id = uuid4()
    parsed = _parse_filters(
        {
            "queryStringParameters": {
                "area_id": str(area_id),
                "include": "locations",
            }
        }
    )
    assert parsed.area_id == area_id
    assert parsed.include_locations is True
    with pytest.raises(ValidationError, match="area_id must be a UUID"):
        _parse_filters({"queryStringParameters": {"area_id": "not-a-uuid"}})
    with pytest.raises(ValidationError, match="Invalid include"):
        _parse_filters({"queryStringParameters": {"include": "pins"}})


def test_review_list_filters_by_neighbourhood(db_session) -> None:
    suffix = uuid4().hex[:8]
    source = f"neighbourhood-{suffix}"
    region = GeographicArea(name=f"Region {suffix}", level="region", active=True)
    db_session.add(region)
    db_session.flush()
    district = GeographicArea(
        name=f"District {suffix}",
        level="district",
        parent_id=region.id,
        active=True,
    )
    db_session.add(district)
    db_session.flush()
    causeway = GeographicArea(
        name=f"Causeway {suffix}",
        level="neighbourhood",
        parent_id=district.id,
        active=True,
    )
    wanchai = GeographicArea(
        name=f"Wanchai {suffix}",
        level="neighbourhood",
        parent_id=district.id,
        active=True,
    )
    db_session.add_all([causeway, wanchai])
    db_session.flush()
    causeway_only = Organization(
        name=f"AAA Causeway {suffix}",
        manager_id="00000000-0000-0000-0000-000000000041",
        description="Described",
        source=source,
        review_status="pending_review",
    )
    both = Organization(
        name=f"MMM Both {suffix}",
        manager_id="00000000-0000-0000-0000-000000000042",
        description="Described",
        source=source,
        review_status="pending_review",
    )
    unplaced = Organization(
        name=f"ZZZ Unplaced {suffix}",
        manager_id="00000000-0000-0000-0000-000000000043",
        description="Described",
        source=source,
        review_status="pending_review",
    )
    db_session.add_all([causeway_only, both, unplaced])
    db_session.flush()
    db_session.add_all(
        [
            Location(
                org_id=causeway_only.id,
                area_id=causeway.id,
                address="1 Causeway Road",
                lat=Decimal("22.280300"),
                lng=Decimal("114.184600"),
            ),
            Location(
                org_id=both.id,
                area_id=causeway.id,
                address="2 Causeway Road",
                lat=Decimal("22.280400"),
                lng=Decimal("114.184700"),
            ),
            Location(
                org_id=both.id,
                area_id=wanchai.id,
                address="8 Hennessy Road",
                lat=Decimal("22.277200"),
                lng=Decimal("114.172800"),
            ),
        ]
    )
    db_session.flush()

    def names(area_id):
        found = _load_filtered_organizations(
            db_session,
            _review_filters(source=source, area_id=area_id),
            None,
            10,
        )
        return [org.name for org in found]

    assert names(causeway.id) == [causeway_only.name, both.name]
    assert names(wanchai.id) == [both.name]
    assert names(district.id) == [causeway_only.name, both.name]
    assert names(region.id) == [causeway_only.name, both.name]
    assert unplaced.name not in names(district.id)
    with pytest.raises(ValidationError, match="area_id not found"):
        names(uuid4())
    inactive = GeographicArea(
        name=f"Retired {suffix}",
        level="neighbourhood",
        parent_id=district.id,
        active=False,
    )
    db_session.add(inactive)
    db_session.flush()
    with pytest.raises(ValidationError, match="area_id not found"):
        names(inactive.id)

    matched = _load_filtered_organizations(
        db_session,
        _review_filters(source=source, area_id=causeway.id),
        None,
        10,
    )
    both_org = next(org for org in matched if org.id == both.id)
    snapshot = load_snapshots(db_session, [both_org])[0]
    pins = _map_locations(
        snapshot,
        {causeway.id},
        {causeway.id: causeway.name, wanchai.id: wanchai.name},
    )
    assert [pin["address"] for pin in pins] == ["2 Causeway Road"]
    assert pins[0]["area_name"] == causeway.name
    assert pins[0]["lat"] == pytest.approx(22.2804)
    assert pins[0]["lng"] == pytest.approx(114.1847)
    body = _serialize_queue_item(snapshot, map_locations=pins)
    assert body["map_locations"] == pins
    assert "map_locations" not in _serialize_queue_item(snapshot)


def _decide(session, organization, action: str, **overrides: object) -> None:
    values: dict[str, object] = {
        "force": True,
        "notes": None,
        "status": None,
        "reviewer_sub": "admin-sub",
        "notes_provided": False,
        "reason": None,
    }
    values.update(overrides)
    _apply_decision(session, organization, action, **values)  # type: ignore[arg-type]


def test_reject_requires_a_known_reason(db_session, sample_organization) -> None:
    from app.api.admin_org_review_actions import _decision_reason

    with pytest.raises(ValidationError, match="reason is required"):
        _decision_reason(None, "reject")
    with pytest.raises(ValidationError, match="Invalid reason"):
        _decision_reason("closed", "reject")
    with pytest.raises(ValidationError, match="only set when rejecting"):
        _decision_reason("other", "approve")
    assert _decision_reason(None, "reopen") is None

    with pytest.raises(ValidationError, match="reason is required"):
        _decide(db_session, sample_organization, "reject")
    _decide(db_session, sample_organization, "reject", reason="not_relevant")
    assert sample_organization.review_status == "rejected"
    assert sample_organization.review_reason == "not_relevant"
    assert sample_organization.reviewed_by == "admin-sub"
    first_review = sample_organization.reviewed_at
    assert first_review is not None

    sample_organization.reviewed_at = datetime(2020, 1, 1, tzinfo=UTC)
    _decide(db_session, sample_organization, "reject", reason="poor_data")
    assert sample_organization.review_reason == "poor_data"
    assert sample_organization.reviewed_at is not None
    assert sample_organization.reviewed_at > datetime(2020, 1, 1, tzinfo=UTC)

    _decide(db_session, sample_organization, "approve")
    assert sample_organization.review_status == "approved"
    assert sample_organization.review_reason is None
    _decide(db_session, sample_organization, "reject", reason="other")
    _decide(db_session, sample_organization, "reopen")
    assert sample_organization.review_status == "pending_review"
    assert sample_organization.review_reason is None

    with pytest.raises(ValidationError, match="Unsupported bulk fields"):
        _parse_fields({"review_reason": "other"})


def test_reason_is_rejected_only(db_session, sample_organization) -> None:
    with pytest.raises(IntegrityError), db_session.begin_nested():
        sample_organization.review_reason = "other"
        db_session.flush()


def test_activity_added_after_rejection_is_a_warning(
    db_session,
    sample_organization,
    sample_activity_category,
) -> None:
    reviewed_at = datetime(2024, 1, 1, tzinfo=UTC)
    sample_organization.review_status = "rejected"
    sample_organization.review_reason = "not_relevant"
    sample_organization.reviewed_at = reviewed_at
    newer = Activity(
        org_id=sample_organization.id,
        category_id=sample_activity_category.id,
        name=f"Kids Class {uuid4().hex[:8]}",
        description="After the rejection",
        age_range=Range(6, 10, bounds="[]"),
        created_at=datetime(2024, 6, 1, tzinfo=UTC),
    )
    older = Activity(
        org_id=sample_organization.id,
        category_id=sample_activity_category.id,
        name=f"Adult Class {uuid4().hex[:8]}",
        description="Before the rejection",
        age_range=Range(18, 40, bounds="[]"),
        created_at=datetime(2023, 1, 1, tzinfo=UTC),
    )
    db_session.add_all([newer, older])
    db_session.flush()

    def codes_for(organization: Organization) -> set[str]:
        snapshot = load_snapshots(db_session, [organization])[0]
        return {issue.code for issue in snapshot.issues}

    assert ACTIVITY_ADDED_SINCE_REJECTED in codes_for(sample_organization)
    message = next(
        issue.message
        for issue in load_snapshots(db_session, [sample_organization])[0].issues
        if issue.code == ACTIVITY_ADDED_SINCE_REJECTED
    )
    assert message == ACTIVITY_ADDED_SINCE_REJECTED_MESSAGE

    sample_organization.review_reason = "duplicate"
    db_session.flush()
    assert ACTIVITY_ADDED_SINCE_REJECTED in codes_for(sample_organization)

    sample_organization.reviewed_at = datetime(2025, 1, 1, tzinfo=UTC)
    db_session.flush()
    assert ACTIVITY_ADDED_SINCE_REJECTED not in codes_for(sample_organization)

    sample_organization.reviewed_at = reviewed_at
    sample_organization.review_status = "approved"
    sample_organization.review_reason = None
    db_session.flush()
    assert ACTIVITY_ADDED_SINCE_REJECTED not in codes_for(sample_organization)

    sample_organization.review_status = "rejected"
    sample_organization.review_reason = None
    db_session.flush()
    assert ACTIVITY_ADDED_SINCE_REJECTED not in codes_for(sample_organization)


def test_added_since_rejected_filters_in_sql_and_matches_summary(
    db_session,
    sample_organization,
    sample_activity_category,
) -> None:
    sample_organization.review_status = "rejected"
    sample_organization.review_reason = "other"
    sample_organization.reviewed_at = datetime(2024, 1, 1, tzinfo=UTC)
    plain = Organization(
        name=f"No Reason {uuid4().hex[:8]}",
        manager_id="00000000-0000-0000-0000-000000000091",
        description="Rejected earlier",
        review_status="rejected",
    )
    db_session.add(plain)
    db_session.add(
        Activity(
            org_id=sample_organization.id,
            category_id=sample_activity_category.id,
            name=f"Later Class {uuid4().hex[:8]}",
            description="New",
            age_range=Range(5, 9, bounds="[]"),
            created_at=datetime(2024, 8, 1, tzinfo=UTC),
        )
    )
    db_session.flush()

    flagged = _load_filtered_organizations(
        db_session,
        _review_filters(issue=ACTIVITY_ADDED_SINCE_REJECTED),
        None,
        10,
    )
    assert sample_organization.id in {org.id for org in flagged}
    assert plain.id not in {org.id for org in flagged}
    python_ids = {
        snapshot.organization.id
        for snapshot in load_snapshots(
            db_session,
            list(db_session.scalars(select(Organization)).all()),
        )
        if any(issue.code == ACTIVITY_ADDED_SINCE_REJECTED for issue in snapshot.issues)
    }
    assert {org.id for org in flagged} == python_ids

    by_reason = _load_filtered_organizations(
        db_session,
        _review_filters(review_reason="other"),
        None,
        10,
    )
    assert {org.id for org in by_reason} == {sample_organization.id}
    none = _load_filtered_organizations(
        db_session,
        _review_filters(review_reason="none"),
        None,
        20,
    )
    assert plain.id in {org.id for org in none}
    assert sample_organization.id not in {org.id for org in none}

    organizations = list(db_session.scalars(select(Organization)).all())
    snapshots = load_snapshots(db_session, organizations)
    assert summarize_catalog(db_session) == summarize_snapshots(snapshots)
    summary = summarize_catalog(db_session)
    assert summary["by_review_reason"]["other"] >= 1
    assert summary["by_review_reason"]["none"] >= 1
    assert summary["by_issue"][ACTIVITY_ADDED_SINCE_REJECTED] >= 1
