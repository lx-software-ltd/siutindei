"""Listing kinds, checked facts, and the kind backfill."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from app.api.admin_crud import _drop_admin_only_write_fields
from app.api.admin_imports_upsert import upsert_activity
from app.api.admin_resource_activity import (
    _create_activity,
    _serialize_activity,
    _update_activity,
    _update_activity_for_manager,
)
from app.db.models import Activity, ActivityCategory
from app.db.repositories import ActivityRepository
from app.exceptions import ValidationError
from app.services.catalog_version_payload import activity_payload
from app.services.catalog_version_shape import activity_shape, payload_differs
from app.services.import_merge import decide_fields
from app.services.listing_kinds import (
    FACT_KEYS,
    KINDS,
    facts_for_kind,
    guess_kind,
    parse_kind,
    validate_facts,
)
from psycopg.types.range import Range
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

_REVISION = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "db"
    / "alembic"
    / "versions"
    / "0065_activity_kind_facts.py"
)


def _revision():
    spec = importlib.util.spec_from_file_location(
        "rev_0065_activity_kind_facts",
        _REVISION,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _category_id(suffix: str) -> UUID:
    return UUID(f"c1111111-1111-1111-1111-11111111{suffix}")


def _ensure_category(db_session, suffix: str) -> UUID:
    category_id = _category_id(suffix)
    if db_session.get(ActivityCategory, category_id) is None:
        db_session.add(
            ActivityCategory(
                id=category_id,
                name=f"Backfill test {suffix} {uuid4().hex[:6]}",
                display_order=0,
            )
        )
        db_session.flush()
    return category_id


def _activity(db_session, org, category_id, name: str) -> Activity:
    activity = Activity(
        org_id=org.id,
        category_id=category_id,
        name=name,
        age_range=Range(3, 8, bounds="[]"),
    )
    db_session.add(activity)
    db_session.flush()
    return activity


def _create_body(org, category, **extra):
    return {
        "org_id": str(org.id),
        "category_id": str(category.id),
        "name": extra.pop("name", "Harbour Class"),
        "age_min": 2,
        "age_max": 6,
        **extra,
    }


def test_kinds_and_fact_keys_match_the_plan() -> None:
    assert KINDS == ("class", "camp", "place", "preschool", "eat")
    assert FACT_KEYS["class"] == ("drop_in", "parent_stays", "sen_friendly")
    assert FACT_KEYS["camp"] == (
        "drop_in",
        "parent_stays",
        "sen_friendly",
        "lunch_included",
    )
    assert "lifeguard" in FACT_KEYS["place"]
    assert "high_chairs" in FACT_KEYS["eat"]
    assert FACT_KEYS["preschool"] == ()


def test_parse_kind_rejects_unknown_values() -> None:
    assert parse_kind("camp") == "camp"
    for bad in ("Camp", "party", "", None, 3):
        with pytest.raises(ValidationError) as exc_info:
            parse_kind(bad)
        assert exc_info.value.field == "kind"


def test_validate_facts_accepts_booleans_for_the_kind() -> None:
    assert validate_facts("place", {"toilets": True, "shade": False}) == {
        "shade": False,
        "toilets": True,
    }
    assert validate_facts("camp", {"lunch_included": True}) == {"lunch_included": True}
    assert validate_facts("preschool", {}) == {}
    assert validate_facts("class", None) == {}


@pytest.mark.parametrize(
    ("kind", "facts"),
    [
        ("class", {"lunch_included": True}),
        ("class", {"toilets": True}),
        ("preschool", {"drop_in": True}),
        ("place", {"toilets": "yes"}),
        ("place", {"toilets": 1}),
        ("place", {"toilets": None}),
        ("place", ["toilets"]),
        ("place", "toilets"),
    ],
)
def test_validate_facts_rejects_unknown_keys_and_non_booleans(kind, facts) -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate_facts(kind, facts)
    assert exc_info.value.field == "facts"


def test_facts_for_kind_drops_keys_the_kind_does_not_allow() -> None:
    facts = {"drop_in": True, "lunch_included": False, "sen_friendly": True}
    assert facts_for_kind("class", facts) == {"drop_in": True, "sen_friendly": True}
    assert facts_for_kind("place", facts) == {}
    assert facts_for_kind("camp", facts) == facts


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("Summer Camp", "camp"),
        ("Football camps for juniors", "camp"),
        ("Pottery WORKSHOP", "camp"),
        ("Clay workshops", "camp"),
        ("Holiday course: sailing", "camp"),
        ("兒童夏令營", "camp"),
        ("冬令營 2027", "camp"),
        ("足球日營", "camp"),
        ("親子工作坊", "camp"),
        ("暑期班 繪畫", "camp"),
        ("Campbell Football Club", "class"),
        ("Camping basics", "class"),
        ("Workshopping drama", "class"),
        ("Weekly swim class", "class"),
        ("", "class"),
    ],
)
def test_guess_kind_uses_the_backfill_patterns(name: str, kind: str) -> None:
    assert guess_kind(name) == kind


def test_backfill_sets_kind_from_category_then_name(
    db_session, sample_organization, sample_activity_category
) -> None:
    other = sample_activity_category.id
    rows = {
        "playground": (_ensure_category(db_session, "1251"), "Harbour playground"),
        "pool": (_ensure_category(db_session, "1242"), "Summer camp at the pool"),
        "group": (_ensure_category(db_session, "1205"), "Free play"),
        "museum": (_ensure_category(db_session, "1263"), "Museum workshop"),
        "nursery": (_ensure_category(db_session, "1211"), "Holiday course nursery"),
        "creche": (_ensure_category(db_session, "1212"), "Day care"),
        "tutoring": (_ensure_category(db_session, "1221"), "Exam workshop"),
        "camp": (other, "Summer Camp"),
        "camp_zh": (other, "親子夏令營"),
        "course": (other, "Holiday course in art"),
        "plain": (other, "Campbell Football"),
    }
    created = {
        key: _activity(db_session, sample_organization, category_id, name)
        for key, (category_id, name) in rows.items()
    }
    _revision().backfill_kind(db_session.connection())
    for activity in created.values():
        db_session.refresh(activity)
    kinds = {key: activity.kind for key, activity in created.items()}
    assert kinds == {
        "playground": "place",
        "pool": "place",
        "group": "place",
        "museum": "place",
        "nursery": "preschool",
        "creche": "preschool",
        "tutoring": "camp",
        "camp": "camp",
        "camp_zh": "camp",
        "course": "camp",
        "plain": "class",
    }
    for key in ("tutoring", "camp", "camp_zh", "course", "plain"):
        assert guess_kind(created[key].name) == kinds[key]
    assert (
        db_session.execute(
            text("SELECT current_setting('app.catalog_backfill', true)")
        ).scalar()
        != "on"
    )


def test_database_rejects_unknown_kind_and_non_object_facts(
    db_session, sample_activity
) -> None:
    for statement in (
        "UPDATE activities SET kind = 'party' WHERE id = :id",
        "UPDATE activities SET facts = '[]'::jsonb WHERE id = :id",
    ):
        nested = db_session.begin_nested()
        with pytest.raises(IntegrityError):
            db_session.execute(text(statement), {"id": sample_activity.id})
            db_session.flush()
        nested.rollback()


def test_new_activity_defaults_to_class_with_no_facts(
    db_session, sample_activity
) -> None:
    db_session.refresh(sample_activity)
    assert sample_activity.kind == "class"
    assert sample_activity.facts == {}
    body = _serialize_activity(sample_activity)
    assert body["kind"] == "class"
    assert body["facts"] == {}


def test_admin_create_accepts_kind_and_facts(
    db_session, sample_organization, sample_activity_category
) -> None:
    repo = ActivityRepository(db_session)
    entity = _create_activity(
        repo,
        _create_body(
            sample_organization,
            sample_activity_category,
            kind="place",
            facts={"toilets": True, "lifeguard": False},
        ),
    )
    repo.create(entity)
    db_session.flush()
    db_session.refresh(entity)
    assert entity.kind == "place"
    assert entity.facts == {"lifeguard": False, "toilets": True}
    serialized = _serialize_activity(entity)
    assert serialized["kind"] == "place"
    assert serialized["facts"] == {"lifeguard": False, "toilets": True}


def test_admin_create_rejects_facts_the_kind_does_not_allow(
    db_session, sample_organization, sample_activity_category
) -> None:
    repo = ActivityRepository(db_session)
    with pytest.raises(ValidationError) as exc_info:
        _create_activity(
            repo,
            _create_body(
                sample_organization,
                sample_activity_category,
                facts={"toilets": True},
            ),
        )
    assert exc_info.value.field == "facts"


def test_changing_kind_drops_facts_the_new_kind_does_not_allow(
    db_session, sample_activity
) -> None:
    repo = ActivityRepository(db_session)
    _update_activity(
        repo,
        sample_activity,
        {"kind": "camp", "facts": {"drop_in": True, "lunch_included": True}},
    )
    db_session.flush()
    assert sample_activity.kind == "camp"
    assert sample_activity.facts == {"drop_in": True, "lunch_included": True}

    _update_activity(repo, sample_activity, {"kind": "class"})
    db_session.flush()
    assert sample_activity.kind == "class"
    assert sample_activity.facts == {"drop_in": True}

    _update_activity(repo, sample_activity, {"facts": {"parent_stays": False}})
    db_session.flush()
    assert sample_activity.facts == {"parent_stays": False}

    with pytest.raises(ValidationError) as exc_info:
        _update_activity(
            repo,
            sample_activity,
            {"kind": "preschool", "facts": {"drop_in": True}},
        )
    assert exc_info.value.field == "facts"

    with pytest.raises(ValidationError) as exc_info:
        _update_activity(repo, sample_activity, {"kind": "party"})
    assert exc_info.value.field == "kind"


def test_managers_cannot_write_kind_or_facts(db_session, sample_activity) -> None:
    body = {"name": "Studio", "kind": "place", "facts": {"toilets": True}}
    _drop_admin_only_write_fields(body)
    assert body == {"name": "Studio"}

    repo = ActivityRepository(db_session)
    _update_activity_for_manager(
        repo,
        sample_activity,
        {"kind": "place", "facts": {"toilets": True}},
    )
    db_session.flush()
    db_session.refresh(sample_activity)
    assert sample_activity.kind == "class"
    assert sample_activity.facts == {}


def test_import_guesses_kind_when_the_file_sends_none(
    db_session, sample_organization, sample_activity_category
) -> None:
    activity, status = upsert_activity(
        db_session,
        sample_organization,
        {
            "name": "Sailing summer camp",
            "category_id": str(sample_activity_category.id),
            "age_min": 6,
            "age_max": 12,
        },
    )
    assert status == "created"
    assert activity.kind == "camp"


def test_import_uses_the_file_kind_and_facts(
    db_session, sample_organization, sample_activity_category
) -> None:
    activity, status = upsert_activity(
        db_session,
        sample_organization,
        {
            "name": "Harbour beach",
            "category_id": str(sample_activity_category.id),
            "age_min": 0,
            "age_max": 12,
            "kind": "place",
            "facts": {"toilets": True, "shade": False},
        },
    )
    assert status == "created"
    assert activity.kind == "place"
    assert activity.facts == {"shade": False, "toilets": True}


def test_import_update_without_kind_keeps_the_admin_kind(
    db_session, sample_organization, sample_activity_category
) -> None:
    payload = {
        "name": "Weekly art camp club",
        "category_id": str(sample_activity_category.id),
        "age_min": 6,
        "age_max": 12,
    }
    activity, _status = upsert_activity(db_session, sample_organization, payload)
    assert activity.kind == "camp"
    activity.kind = "class"
    db_session.flush()
    updated, _status = upsert_activity(
        db_session,
        sample_organization,
        {**payload, "description": "Now with a description"},
    )
    assert updated.id == activity.id
    assert updated.kind == "class"


def test_three_way_merge_keeps_an_admin_edit_to_kind_and_facts() -> None:
    base = {"name": "Swim", "kind": "class", "facts": {}}
    present = {"kind", "facts"}

    clean = decide_fields(
        "activity",
        base,
        base,
        {"name": "Swim", "kind": "camp", "facts": {"drop_in": True}},
        present,
        mode="merge",
    )
    assert {change.field: change.action for change in clean.changes} == {
        "facts": "apply",
        "kind": "apply",
    }

    admin = {"name": "Swim", "kind": "place", "facts": {"toilets": True}}
    unchanged_file = decide_fields("activity", base, admin, base, present, mode="merge")
    assert unchanged_file.status == "unchanged"

    conflict = decide_fields(
        "activity",
        base,
        admin,
        {"name": "Swim", "kind": "camp", "facts": {"drop_in": True}},
        present,
        mode="merge",
    )
    assert conflict.status == "proposed"
    assert {change.field: change.action for change in conflict.changes} == {
        "facts": "proposal",
        "kind": "proposal",
    }


def test_catalog_shape_carries_kind_and_facts(db_session, sample_activity) -> None:
    sample_activity.kind = "place"
    sample_activity.facts = {"toilets": True}
    db_session.flush()
    payload = activity_payload(sample_activity)
    assert payload["kind"] == "place"
    assert payload["facts"] == {"toilets": True}
    shape = activity_shape(payload)
    assert shape["kind"] == "place"
    assert shape["facts"] == {"toilets": True}


def test_snapshot_from_before_kinds_reads_as_a_class_with_no_facts() -> None:
    old = {"name": "Swim", "age_range": Range(3, 8, bounds="[]")}
    shape = activity_shape(old)
    assert shape["kind"] == "class"
    assert shape["facts"] == {}
    live = {**old, "kind": "class", "facts": {}}
    assert not payload_differs("activity", live, old)
    assert payload_differs("activity", {**live, "kind": "camp"}, old)
