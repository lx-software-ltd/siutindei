"""Topics, fixed roots, hidden categories, and the school cut."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest
from app.api.admin_imports_importer import process_import_payload
from app.api.admin_resource_activity_category import (
    _serialize_activity_category,
    _update_activity_category,
)
from app.api.search_page import count_search_activities
from app.db.incomplete_search import incomplete_activity_ids_query
from app.db.models import (
    Activity,
    ActivityCategory,
    ActivityLocation,
    ActivityPricing,
    ActivitySchedule,
    ActivityScheduleEntry,
    Location,
    Organization,
    PricingType,
    ScheduleType,
)
from app.db.models.category_scan import ActivityCategoryReview
from app.db.models.category_suggestion import (
    MEMBERS_CLUBS_CATEGORY_ID,
    NURSERIES_CATEGORY_ID,
    PENDING_CATEGORY_ID,
    PLACES_CATEGORY_ID,
    SCHOOLS_CATEGORY_ID,
    WIZARD_GROUP_IDS,
)
from app.db.queries import ActivitySearchFilters, build_search_query
from app.db.repositories import ActivityCategoryRepository
from app.exceptions import ValidationError
from app.services.activity_categories import create_activity_category
from app.services.category_suggestions import reviews as review_service
from app.services.category_suggestions.resolve import resolve_category_name
from app.services.listing_kinds import (
    assign_category,
    kind_for_category,
    move_to_category,
)
from app.services.org_review import collect_issues, load_snapshots, summarize_snapshots
from app.services.org_review_decision import (
    HIDDEN_CATEGORY_REVIEWER,
    HIDDEN_ONLY_IMPORT_WARNING,
    reject_if_only_hidden,
)
from app.services.org_review_sql import summarize_catalog
from psycopg.types.range import Range
from sqlalchemy import select

PRIMARY_SCHOOL_ID = UUID("c1111111-1111-1111-1111-111111111213")
PLAYGROUND_ID = UUID("c1111111-1111-1111-1111-111111111411")
SPORTS_ID = UUID("c1111111-1111-1111-1111-111111111302")


def _org(session, name: str = "Harbourview Learning Co") -> Organization:
    org = Organization(
        name=name,
        description="A fictional organization for taxonomy tests",
        manager_id="00000000-0000-0000-0000-000000000001",
    )
    session.add(org)
    session.flush()
    return org


def _activity(
    session,
    org: Organization,
    category_id: UUID,
    *,
    name: str = "Saturday class",
    kind: str = "class",
) -> Activity:
    activity = Activity(
        org_id=org.id,
        category_id=category_id,
        name=name,
        kind=kind,
        age_range=Range(5, 10, bounds="[]"),
    )
    session.add(activity)
    session.flush()
    return activity


def _list(session, org: Organization, activity: Activity, area) -> Location:
    location = Location(
        org_id=org.id,
        area_id=area.id,
        address=f"{activity.name} Example Road",
        lat=Decimal("22.282667"),
        lng=Decimal("114.158167"),
    )
    session.add(location)
    session.flush()
    session.add(
        ActivityPricing(
            activity_id=activity.id,
            location_id=location.id,
            pricing_type=PricingType.PER_CLASS,
            amount=Decimal("120.00"),
            currency="HKD",
        )
    )
    session.add(
        ActivitySchedule(
            activity_id=activity.id,
            location_id=location.id,
            schedule_type=ScheduleType.WEEKLY,
            languages=["en"],
            entries=[
                ActivityScheduleEntry(
                    day_of_week_utc=2,
                    start_minutes_utc=600,
                    end_minutes_utc=660,
                )
            ],
        )
    )
    session.flush()
    return location


def _search_ids(session, filters: ActivitySearchFilters | None = None) -> set[UUID]:
    rows = session.execute(
        build_search_query(filters or ActivitySearchFilters(limit=50))
    ).all()
    return {UUID(str(row._mapping[Activity].id)) for row in rows}


def test_migration_leaves_topics_and_fixed_roots(db_session) -> None:
    assert len(WIZARD_GROUP_IDS) == 9
    for topic_id in WIZARD_GROUP_IDS:
        topic = db_session.get(ActivityCategory, topic_id)
        assert topic is not None and topic.show_in_wizard
        assert topic.parent_id is None
    schools = db_session.get(ActivityCategory, SCHOOLS_CATEGORY_ID)
    clubs = db_session.get(ActivityCategory, MEMBERS_CLUBS_CATEGORY_ID)
    assert schools.hidden_from_public and clubs.hidden_from_public
    primary = db_session.get(ActivityCategory, PRIMARY_SCHOOL_ID)
    assert primary.parent_id == SCHOOLS_CATEGORY_ID
    assert not primary.hidden_from_public


def test_kind_follows_the_root(db_session, sample_activity_category) -> None:
    assert kind_for_category(db_session, PLAYGROUND_ID, "class") == "place"
    assert kind_for_category(db_session, NURSERIES_CATEGORY_ID, "camp") == ("preschool")
    assert kind_for_category(db_session, SPORTS_ID, "place") == "class"
    assert kind_for_category(db_session, SPORTS_ID, "camp") == "camp"
    assert kind_for_category(db_session, sample_activity_category.id, "eat") == "eat"
    assert kind_for_category(db_session, PRIMARY_SCHOOL_ID, "camp") == "camp"


def test_assign_category_trims_facts_for_the_new_kind(db_session) -> None:
    org = _org(db_session)
    activity = _activity(db_session, org, PLAYGROUND_ID, kind="place")
    activity.facts = {"toilets": True, "shade": False}
    db_session.flush()
    assign_category(db_session, activity, SPORTS_ID)
    assert activity.category_id == SPORTS_ID
    assert activity.kind == "class"
    assert activity.facts == {}


def test_school_only_org_is_rejected_and_stays_rejected(db_session) -> None:
    org = _org(db_session)
    activity = _activity(db_session, org, SPORTS_ID)
    assert reject_if_only_hidden(db_session, org.id) is False
    move_to_category(db_session, activity, PRIMARY_SCHOOL_ID)
    assert org.review_status == "rejected"
    assert org.review_reason == "not_relevant"
    assert org.reviewed_by == HIDDEN_CATEGORY_REVIEWER
    assert org.reviewed_at is not None
    move_to_category(db_session, activity, SPORTS_ID)
    assert org.review_status == "rejected"


def test_mixed_empty_and_already_rejected_orgs_are_left_alone(db_session) -> None:
    mixed = _org(db_session, "Kowloon Mixed Academy")
    _activity(db_session, mixed, PRIMARY_SCHOOL_ID)
    _activity(db_session, mixed, SPORTS_ID, name="Summer camp", kind="camp")
    assert reject_if_only_hidden(db_session, mixed.id) is False
    assert mixed.review_status != "rejected"

    empty = _org(db_session, "Empty Example Org")
    assert reject_if_only_hidden(db_session, empty.id) is False

    duplicate = _org(db_session, "Duplicate Example Club")
    duplicate.review_status = "rejected"
    duplicate.review_reason = "duplicate"
    _activity(db_session, duplicate, MEMBERS_CLUBS_CATEGORY_ID)
    assert reject_if_only_hidden(db_session, duplicate.id) is False
    assert duplicate.review_reason == "duplicate"


def test_inherited_hidden_flag_counts(db_session) -> None:
    org = _org(db_session)
    child = ActivityCategory(name="Example members pool", parent_id=SCHOOLS_CATEGORY_ID)
    db_session.add(child)
    db_session.flush()
    _activity(db_session, org, child.id)
    assert reject_if_only_hidden(db_session, org.id) is True


def test_search_hides_hidden_categories_and_counts_agree(
    db_session, sample_geographic_area
) -> None:
    org = _org(db_session)
    shown = _activity(db_session, org, SPORTS_ID, name="Football")
    school = _activity(db_session, org, PRIMARY_SCHOOL_ID, name="Primary year one")
    _list(db_session, org, shown, sample_geographic_area)
    _list(db_session, org, school, sample_geographic_area)

    found = _search_ids(db_session)
    assert shown.id in found
    assert school.id not in found
    filters = ActivitySearchFilters(limit=50)
    assert count_search_activities(db_session, filters) == len(found)

    by_root = _search_ids(
        db_session,
        ActivitySearchFilters(category_ids=[SCHOOLS_CATEGORY_ID], limit=50),
    )
    assert by_root == set()

    schools = db_session.get(ActivityCategory, SCHOOLS_CATEGORY_ID)
    schools.hidden_from_public = False
    db_session.flush()
    assert school.id in _search_ids(db_session)


def test_incomplete_search_hides_hidden_categories(
    db_session, sample_geographic_area
) -> None:
    org = _org(db_session)
    org.review_status = "approved"
    shown = _activity(db_session, org, SPORTS_ID, name="Unpriced football")
    school = _activity(db_session, org, PRIMARY_SCHOOL_ID, name="Unpriced school")
    location = Location(
        org_id=org.id,
        area_id=sample_geographic_area.id,
        address="2 Example Road",
        lat=Decimal("22.3"),
        lng=Decimal("114.2"),
    )
    db_session.add(location)
    db_session.flush()
    for activity in (shown, school):
        db_session.add(
            ActivityLocation(activity_id=activity.id, location_id=location.id)
        )
    db_session.flush()
    ids = {
        UUID(str(row.activity_id))
        for row in db_session.execute(
            incomplete_activity_ids_query(ActivitySearchFilters(limit=50))
        )
    }
    assert shown.id in ids
    assert school.id not in ids


def test_fixed_roots_are_protected_but_children_are_editable(db_session) -> None:
    repo = ActivityCategoryRepository(db_session)
    places = db_session.get(ActivityCategory, PLACES_CATEGORY_ID)
    payload = _serialize_activity_category(places)
    assert payload["is_system"] is True
    assert payload["system_role"] == "places"
    assert payload["hidden_from_public"] is False
    for body in (
        {"name": "Somewhere else"},
        {"parent_id": str(SPORTS_ID)},
        {"show_in_wizard": True},
    ):
        with pytest.raises(ValidationError):
            _update_activity_category(repo, places, dict(body))
    with pytest.raises(ValidationError):
        repo.delete(db_session.get(ActivityCategory, MEMBERS_CLUBS_CATEGORY_ID))

    _update_activity_category(repo, places, {"display_order": 115})
    assert places.display_order == 115
    _update_activity_category(repo, places, {"hidden_from_public": True})
    assert places.hidden_from_public is True

    child = create_activity_category(
        repo,
        {"name": "Example splash pad", "parent_id": str(PLACES_CATEGORY_ID)},
    )
    repo.create(child)
    assert _serialize_activity_category(child)["system_role"] is None
    _update_activity_category(repo, child, {"name": "Example splash park"})
    repo.delete(child)


def test_hidden_flag_rules(db_session) -> None:
    repo = ActivityCategoryRepository(db_session)
    pending = db_session.get(ActivityCategory, PENDING_CATEGORY_ID)
    assert _serialize_activity_category(pending)["system_role"] == "pending"
    with pytest.raises(ValidationError):
        _update_activity_category(repo, pending, {"hidden_from_public": True})
    sports = db_session.get(ActivityCategory, SPORTS_ID)
    with pytest.raises(ValidationError):
        _update_activity_category(repo, sports, {"hidden_from_public": "yes"})
    created = create_activity_category(
        repo,
        {"name": "Example private club", "hidden_from_public": True},
    )
    assert created.hidden_from_public is True


def test_org_review_skips_hidden_blockers_and_warns(db_session) -> None:
    org = _org(db_session)
    school = _activity(db_session, org, PRIMARY_SCHOOL_ID)
    issues, _checks = collect_issues(
        org,
        [],
        [school],
        {},
        {},
        hidden_activity_ids={str(school.id)},
    )
    codes = {issue.code for issue in issues}
    assert "missing_pricing" not in codes
    assert "missing_schedule" not in codes
    assert "no_listable_activities" in codes

    snapshot = load_snapshots(db_session, [org])[0]
    codes = {issue.code for issue in snapshot.issues}
    assert "no_listable_activities" in codes
    assert "missing_pricing" not in codes

    organizations = list(db_session.scalars(select(Organization)).all())
    snapshots = load_snapshots(db_session, organizations)
    assert summarize_catalog(db_session) == summarize_snapshots(snapshots)


def test_review_apply_moves_kind_and_rejects(db_session) -> None:
    from tests.test_category_scan import _run

    org = _org(db_session)
    activity = _activity(db_session, org, PLAYGROUND_ID, kind="place")
    run = _run(db_session)
    review = ActivityCategoryReview(
        scan_run_id=run.id,
        activity_id=activity.id,
        org_id=org.id,
        verdict="reassign",
        status="pending",
        proposed_category_id=MEMBERS_CLUBS_CATEGORY_ID,
    )
    db_session.add(review)
    db_session.flush()
    review_service.apply_review_decision(
        db_session, review, {"action": "apply"}, decided_by="admin"
    )
    assert activity.category_id == MEMBERS_CLUBS_CATEGORY_ID
    assert org.review_status == "rejected"
    assert org.review_reason == "not_relevant"

    review_service.apply_review_decision(
        db_session, review, {"action": "revert"}, decided_by="admin"
    )
    assert activity.category_id == PLAYGROUND_ID
    assert activity.kind == "place"
    assert org.review_status == "rejected"


@pytest.mark.parametrize(
    ("old_name", "new_id"),
    [
        ("Sports and movement", SPORTS_ID),
        ("Swimming pool", UUID("c1111111-1111-1111-1111-111111111414")),
        ("游泳池", UUID("c1111111-1111-1111-1111-111111111414")),
        ("Kindergarten and nursery", UUID("c1111111-1111-1111-1111-111111111422")),
    ],
)
def test_old_labels_resolve_through_aliases(db_session, old_name, new_id) -> None:
    assert resolve_category_name(db_session, old_name).category_id == new_id


def _import(session, org_name: str, activities: list[dict]) -> list[dict]:
    payload = {
        "organizations": [
            {
                "name": org_name,
                "description": "Fictional import organization",
                "manager_id": "00000000-0000-0000-0000-000000000077",
                "activities": [
                    {"description": "Desc", "age_min": 5, "age_max": 10, **item}
                    for item in activities
                ],
            }
        ]
    }
    _summary, results = process_import_payload(session, payload, [])
    return results


def test_import_of_a_school_only_org_rejects_it(db_session) -> None:
    results = _import(
        db_session,
        "Example Primary Academy",
        [{"name": "Primary one", "category_name": "Primary school"}],
    )
    assert HIDDEN_ONLY_IMPORT_WARNING in results[0]["warnings"]
    org = db_session.scalars(
        select(Organization).where(Organization.name == "Example Primary Academy")
    ).one()
    assert org.review_status == "rejected"
    assert org.review_reason == "not_relevant"


def test_import_resolves_an_old_label_and_kind_follows(db_session) -> None:
    results = _import(
        db_session,
        "Example Sports Venue",
        [{"name": "Public pool", "category_name": "Swimming pool"}],
    )
    assert HIDDEN_ONLY_IMPORT_WARNING not in results[0]["warnings"]
    activity = db_session.scalars(
        select(Activity).where(Activity.name == "Public pool")
    ).one()
    assert activity.category_id == UUID("c1111111-1111-1111-1111-111111111414")
    assert activity.kind == "place"
