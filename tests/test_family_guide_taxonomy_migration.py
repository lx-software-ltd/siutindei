"""Round trip of 0066_family_guide_taxonomy on a catalogue at 0065."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "backend" / "db" / "alembic"
_BEFORE = "0065_activity_kind_facts"
_HEAD = "0066_family_guide_taxonomy"
_PREFIX = "c1111111-1111-1111-1111-11111111"
_ACTOR = "migration:0066"


def _cat(suffix: str) -> UUID:
    return UUID(_PREFIX + suffix)


def _config():
    from alembic.config import Config

    # No ini file, so env.py leaves the test run's logging alone.
    config = Config()
    config.set_main_option("script_location", str(_SCRIPT))
    return config


def _seed(session: Session, ids: dict[str, UUID]) -> None:
    session.execute(text("SET LOCAL app.catalog_backfill = 'on'"))
    orgs = {
        "school_org": "pending_review",
        "mixed_org": "pending_review",
        "duplicate_org": "rejected",
        "empty_org": "pending_review",
        "venue_org": "pending_review",
    }
    for key, status in orgs.items():
        session.execute(
            text(
                "INSERT INTO organizations "
                "(id, name, description, manager_id, review_status, review_reason) "
                "VALUES (:id, :name, 'Fictional', :manager, :status, :reason)"
            ),
            {
                "id": ids[key],
                "name": f"Round trip {key} {ids[key].hex[:6]}",
                "manager": "00000000-0000-0000-0000-000000000066",
                "status": status,
                "reason": "duplicate" if status == "rejected" else None,
            },
        )
    activities = {
        "primary": ("school_org", "1213", "class"),
        "secondary": ("school_org", "1214", "class"),
        "international": ("mixed_org", "1215", "class"),
        "dance": ("mixed_org", "1231", "camp"),
        "dup_school": ("duplicate_org", "1213", "class"),
        "parents": ("venue_org", "1224", "place"),
        "playground": ("venue_org", "1251", "class"),
        "sports_group": ("venue_org", "1204", "class"),
    }
    for key, (org_key, suffix, kind) in activities.items():
        session.execute(
            text(
                "INSERT INTO activities "
                "(id, org_id, category_id, name, age_range, kind, facts) "
                "VALUES (:id, :org, :cat, :name, '[3,8]', :kind, "
                "CAST(:facts AS jsonb))"
            ),
            {
                "id": ids[key],
                "org": ids[org_key],
                "cat": _cat(suffix),
                "name": f"Round trip {key}",
                "kind": kind,
                "facts": '{"toilets": true}' if kind == "place" else "{}",
            },
        )
    session.execute(
        text(
            "INSERT INTO category_suggestions "
            "(id, fingerprint, requested_name, suggested_parent_id, "
            "maps_to_category_id) "
            "VALUES (:id, :fp, 'Round trip phonics', :parent, :maps)"
        ),
        {
            "id": ids["suggestion"],
            "fp": f"round trip phonics {ids['suggestion'].hex[:6]}",
            "parent": _cat("1202"),
            "maps": _cat("1221"),
        },
    )
    session.execute(
        text(
            "INSERT INTO category_suggestions "
            "(id, fingerprint, requested_name, status, merged_into_category_id) "
            "VALUES (:id, 'drama', 'Drama', 'merged', :merged) "
            "ON CONFLICT (fingerprint) DO NOTHING"
        ),
        {"id": ids["drama"], "merged": _cat("1234")},
    )
    session.execute(
        text(
            "INSERT INTO category_scan_runs "
            "(id, status, batch_size, batches_total, total_activities) "
            "VALUES (:id, 'queued', 10, 1, 1)"
        ),
        {"id": ids["run"]},
    )
    session.execute(
        text(
            "INSERT INTO activity_category_reviews "
            "(id, scan_run_id, activity_id, org_id, verdict, status, "
            "current_category_id, proposed_category_id, previous_category_id) "
            "VALUES (:id, :run, :activity, :org, 'reassign', 'pending', "
            ":current, :proposed, :previous)"
        ),
        {
            "id": ids["review"],
            "run": ids["run"],
            "activity": ids["sports_group"],
            "org": ids["venue_org"],
            "current": _cat("1221"),
            "proposed": _cat("1222"),
            "previous": _cat("1202"),
        },
    )


def _one(session: Session, sql: str, **params):
    return session.execute(text(sql), params).one()


def _check_head(session: Session, ids: dict[str, UUID]) -> None:
    def category(key: str) -> UUID:
        return session.scalar(
            text("SELECT category_id FROM activities WHERE id = :id"),
            {"id": ids[key]},
        )

    assert category("primary") == _cat("1213")
    assert category("international") == _cat("1215")
    assert category("dance") == _cat("1305")
    assert category("sports_group") == _cat("1302")
    assert _one(
        session,
        "SELECT category_id, kind, facts FROM activities WHERE id = :id",
        id=ids["parents"],
    ) == (_cat("1309"), "class", {})
    assert _one(
        session,
        "SELECT category_id, kind FROM activities WHERE id = :id",
        id=ids["playground"],
    ) == (_cat("1411"), "place")
    stale = session.scalar(
        text(
            "SELECT count(*) FROM activities a "
            "WHERE a.category_id::text LIKE :old "
            "AND a.category_id NOT IN (:p, :s, :i)"
        ),
        {
            "old": _PREFIX + "12%",
            "p": _cat("1213"),
            "s": _cat("1214"),
            "i": _cat("1215"),
        },
    )
    assert stale == 0
    assert session.scalar(
        text("SELECT parent_id FROM activity_categories WHERE id = :id"),
        {"id": _cat("1213")},
    ) == _cat("1404")

    school = _one(
        session,
        "SELECT review_status, review_reason, reviewed_by "
        "FROM organizations WHERE id = :id",
        id=ids["school_org"],
    )
    assert school == ("rejected", "not_relevant", _ACTOR)
    statuses = {
        key: session.scalar(
            text("SELECT review_status FROM organizations WHERE id = :id"),
            {"id": ids[key]},
        )
        for key in ("mixed_org", "empty_org", "venue_org")
    }
    assert statuses == dict.fromkeys(statuses, "pending_review")
    assert _one(
        session,
        "SELECT review_reason FROM organizations WHERE id = :id",
        id=ids["duplicate_org"],
    ) == ("duplicate",)

    assert _one(
        session,
        "SELECT suggested_parent_id, maps_to_category_id "
        "FROM category_suggestions WHERE id = :id",
        id=ids["suggestion"],
    ) == (_cat("1308"), _cat("1308"))
    assert _one(
        session,
        "SELECT count(*), max(merged_into_category_id::text) "
        "FROM category_suggestions WHERE fingerprint = 'drama'",
    ) == (1, str(_cat("1305")))
    assert _one(
        session,
        "SELECT current_category_id, proposed_category_id, previous_category_id "
        "FROM activity_category_reviews WHERE id = :id",
        id=ids["review"],
    ) == (_cat("1308"), _cat("1306"), _cat("1308"))
    assert _one(
        session,
        "SELECT merged_into_category_id FROM category_suggestions "
        "WHERE requested_name = 'Sports and movement' AND decided_by = :actor",
        actor=_ACTOR,
    ) == (_cat("1302"),)
    hidden = session.scalars(
        text("SELECT id FROM activity_categories WHERE hidden_from_public")
    ).all()
    assert set(hidden) == {_cat("1404"), _cat("1405")}


def _check_downgraded(session: Session, ids: dict[str, UUID]) -> None:
    assert (
        session.scalar(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'activity_categories' "
                "AND column_name = 'hidden_from_public'"
            )
        )
        is None
    )
    on_new = session.scalar(
        text(
            "SELECT count(*) FROM activities "
            "WHERE category_id::text LIKE :topic OR category_id::text LIKE :root"
        ),
        {"topic": _PREFIX + "13%", "root": _PREFIX + "14%"},
    )
    assert on_new == 0
    assert session.scalar(
        text("SELECT category_id FROM activities WHERE id = :id"),
        {"id": ids["primary"]},
    ) == _cat("1213")
    assert session.scalar(
        text("SELECT parent_id FROM activity_categories WHERE id = :id"),
        {"id": _cat("1213")},
    ) == _cat("1201")
    assert (
        session.scalar(
            text("SELECT count(*) FROM category_suggestions WHERE decided_by = :a"),
            {"a": _ACTOR},
        )
        == 0
    )
    wizard = session.scalars(
        text("SELECT id FROM activity_categories WHERE show_in_wizard")
    ).all()
    assert {_cat(f"120{n}") for n in range(1, 8)} <= set(wizard)


def _cleanup(engine, ids: dict[str, UUID]) -> None:
    with Session(engine) as session:
        session.execute(text("SET LOCAL app.catalog_backfill = 'on'"))
        session.execute(
            text("DELETE FROM activity_category_reviews WHERE id = :id"),
            {"id": ids["review"]},
        )
        session.execute(
            text("DELETE FROM category_scan_runs WHERE id = :id"),
            {"id": ids["run"]},
        )
        session.execute(
            text("DELETE FROM category_suggestions WHERE id IN (:a, :b)"),
            {"a": ids["suggestion"], "b": ids["drama"]},
        )
        org_ids = [ids[key] for key in ids if key.endswith("_org")]
        session.execute(
            text("DELETE FROM activities WHERE org_id = ANY(:orgs)"),
            {"orgs": org_ids},
        )
        session.execute(
            text("DELETE FROM organizations WHERE id = ANY(:orgs)"),
            {"orgs": org_ids},
        )
        session.commit()


def test_round_trip_keeps_every_activity_on_a_valid_category(test_engine) -> None:
    if test_engine.dialect.name != "postgresql":
        pytest.skip("migration SQL is PostgreSQL")
    with Session(test_engine) as session:
        current = session.scalar(text("SELECT version_num FROM alembic_version"))
    if current != _HEAD:
        pytest.skip(f"database is at {current}")

    os.environ["DATABASE_URL"] = test_engine.url.render_as_string(hide_password=False)
    from alembic import command

    config = _config()
    keys = [
        "school_org",
        "mixed_org",
        "duplicate_org",
        "empty_org",
        "venue_org",
        "primary",
        "secondary",
        "international",
        "dance",
        "dup_school",
        "parents",
        "playground",
        "sports_group",
        "suggestion",
        "drama",
        "run",
        "review",
    ]
    ids = {key: uuid4() for key in keys}
    try:
        command.downgrade(config, _BEFORE)
        with Session(test_engine) as session:
            _seed(session, ids)
            session.commit()

        command.upgrade(config, _HEAD)
        with Session(test_engine) as session:
            _check_head(session, ids)

        command.downgrade(config, "-1")
        with Session(test_engine) as session:
            _check_downgraded(session, ids)

        command.upgrade(config, _HEAD)
        with Session(test_engine) as session:
            _check_head(session, ids)
    finally:
        command.upgrade(config, "head")
        _cleanup(test_engine, ids)
        with Session(test_engine) as session:
            assert (
                session.scalar(text("SELECT version_num FROM alembic_version")) == _HEAD
            )
