"""Tests for lifting appended Source lines into source columns."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from psycopg.types.range import Range

from app.db.models import Activity, Organization

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "backend/db/alembic/versions/0035_org_source_fields.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location(
        "migration_0035_org_source_fields",
        _MIGRATION_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_peel_url_and_note() -> None:
    migration = _migration()
    description, url, note, pairs = migration.peel_appended_source(
        "Hello\nSource: https://example.test — checked"
    )
    assert description == "Hello"
    assert url == "https://example.test"
    assert note == "checked"
    assert pairs == {}


def test_peel_url_only() -> None:
    migration = _migration()
    description, url, note, _pairs = migration.peel_appended_source(
        "Hello\nSource: https://example.test"
    )
    assert description == "Hello"
    assert url == "https://example.test"
    assert note is None


def test_peel_note_only() -> None:
    migration = _migration()
    description, url, note, _pairs = migration.peel_appended_source(
        "Hello\nSource: checked"
    )
    assert description == "Hello"
    assert url is None
    assert note == "checked"


def test_peel_note_keeps_internal_dash() -> None:
    migration = _migration()
    _description, url, note, _pairs = migration.peel_appended_source(
        "Hello\nSource: checked — extra"
    )
    assert url is None
    assert note == "checked — extra"


def test_peel_url_note_keeps_later_dash() -> None:
    migration = _migration()
    _description, url, note, _pairs = migration.peel_appended_source(
        "Hello\nSource: https://example.test — note — more"
    )
    assert url == "https://example.test"
    assert note == "note — more"


def test_peel_catalog_pairs() -> None:
    migration = _migration()
    description, url, note, pairs = migration.peel_appended_source(
        "Venue\nSource: source=lcsd; sourceId=lcsd-9; descriptionSource=template"
    )
    assert description == "Venue"
    assert url is None
    assert note is None
    assert pairs["source"] == "lcsd"
    assert pairs["sourceId"] == "lcsd-9"
    assert pairs["descriptionSource"] == "template"


def test_peel_description_that_is_only_the_source_line() -> None:
    migration = _migration()
    description, url, note, _pairs = migration.peel_appended_source(
        "Source: https://example.test"
    )
    assert description is None
    assert url == "https://example.test"
    assert note is None


def test_peel_repeated_lines_use_the_last_one() -> None:
    migration = _migration()
    description, url, note, _pairs = migration.peel_appended_source(
        "Hello\nSource: https://old.test — first\nSource: https://new.test — second"
    )
    assert description == "Hello"
    assert url == "https://new.test"
    assert note == "second"


def test_peel_ignores_source_mention_inside_a_sentence() -> None:
    migration = _migration()
    text = "See Source: the brochure"
    description, url, note, pairs = migration.peel_appended_source(text)
    assert description == text
    assert url is None
    assert note is None
    assert pairs == {}


def test_peel_keeps_non_trailing_source_line() -> None:
    migration = _migration()
    text = "Source: https://mid.test — keep\nMore description"
    description, url, note, pairs = migration.peel_appended_source(text)
    assert description == text
    assert url is None
    assert note is None
    assert pairs == {}


def test_peel_trailing_blank_lines() -> None:
    migration = _migration()
    description, url, note, _pairs = migration.peel_appended_source(
        "Hello\nSource: https://example.test\n\n"
    )
    assert description == "Hello"
    assert url == "https://example.test"
    assert note is None


def test_peel_preserves_free_text_semicolons() -> None:
    migration = _migration()
    _description, url, note, _pairs = migration.peel_appended_source(
        "Hello\nSource: checked;extra"
    )
    assert url is None
    assert note == "checked;extra"


def test_backfill_updates_existing_rows(
    db_session,
    sample_activity_category,
) -> None:
    migration = _migration()
    org = Organization(
        name="Backfill Org",
        description=(
            "Hello\nSource: source=lcsd; sourceId=lcsd-9; " "descriptionSource=template"
        ),
        manager_id="00000000-0000-0000-0000-000000000099",
    )
    db_session.add(org)
    db_session.flush()
    activity = Activity(
        org_id=org.id,
        category_id=sample_activity_category.id,
        name="Backfill Class",
        description="Class\nSource: https://class.test — roster",
        age_range=Range(5, 10, bounds="[]"),
    )
    db_session.add(activity)
    db_session.flush()

    migration.backfill_appended_sources(db_session.connection())
    db_session.expire_all()

    found_org = db_session.get(Organization, org.id)
    found_activity = db_session.get(Activity, activity.id)
    assert found_org is not None
    assert found_org.description == "Hello"
    assert found_org.source == "lcsd"
    assert found_org.source_id == "lcsd-9"
    assert found_org.description_source == "template"
    assert found_org.source_url is None
    assert found_org.source_note is None
    assert found_activity is not None
    assert found_activity.description == "Class"
    assert found_activity.source_url == "https://class.test"
    assert found_activity.source_note == "roster"


def test_backfill_does_not_copy_activity_pairs_to_org(
    db_session,
    sample_activity_category,
) -> None:
    migration = _migration()
    org = Organization(
        name="Activity Pair Org",
        description="Plain description",
        manager_id="00000000-0000-0000-0000-000000000099",
    )
    db_session.add(org)
    db_session.flush()
    activity = Activity(
        org_id=org.id,
        category_id=sample_activity_category.id,
        name="Paired Class",
        description=(
            "Class\nSource: source=lcsd; sourceId=lcsd-9; "
            "descriptionSource=template"
        ),
        age_range=Range(5, 10, bounds="[]"),
    )
    db_session.add(activity)
    db_session.flush()

    migration.backfill_appended_sources(db_session.connection())
    db_session.expire_all()

    found_org = db_session.get(Organization, org.id)
    found_activity = db_session.get(Activity, activity.id)
    assert found_org is not None
    assert found_org.description == "Plain description"
    assert found_org.source is None
    assert found_org.source_id is None
    assert found_org.description_source is None
    assert found_activity is not None
    assert found_activity.description == "Class"
    assert found_activity.source_url is None
    assert found_activity.source_note is None
