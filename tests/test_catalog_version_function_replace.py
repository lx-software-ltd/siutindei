"""0049 replaces helper functions a failed attempt already committed.

The first production run of this revision committed
``catalog_backfill_*_batch(text)`` with ``integer`` returns, then
failed before stamping ``0049``. ``CREATE OR REPLACE`` cannot change a
return type, so the next upgrade has to drop those copies first.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

_ROOT = Path(__file__).resolve().parents[1]
_INI = _ROOT / "backend" / "db" / "alembic.ini"
_SCRIPT = _ROOT / "backend" / "db" / "alembic"
_READY = {"0048_catalog_versions", "0049_catalog_version_fixes"}
_HEAD = "0049_catalog_version_fixes"

# Drop batches before the functions they call. Signatures match the
# copies revision 0049 used to leave behind.
_HELPERS = (
    "catalog_backfill_deleted_batch(text)",
    "catalog_backfill_deleted(text, text[])",
    "catalog_backfill_live_batch(text)",
    "catalog_backfill_live(text, uuid[])",
)

_OLD_HELPERS = (
    """
    CREATE FUNCTION catalog_backfill_live(etable text, ids uuid[] DEFAULT NULL)
    RETURNS void
    LANGUAGE plpgsql
    AS $$
    BEGIN
        RETURN;
    END;
    $$
    """,
    """
    CREATE FUNCTION catalog_backfill_live_batch(etable text)
    RETURNS integer
    LANGUAGE plpgsql
    AS $$
    BEGIN
        PERFORM catalog_backfill_live(etable, NULL);
        RETURN 0;
    END;
    $$
    """,
    """
    CREATE FUNCTION catalog_backfill_deleted(
        etable text,
        ids text[] DEFAULT NULL
    )
    RETURNS void
    LANGUAGE plpgsql
    AS $$
    BEGIN
        RETURN;
    END;
    $$
    """,
    """
    CREATE FUNCTION catalog_backfill_deleted_batch(etable text)
    RETURNS integer
    LANGUAGE plpgsql
    AS $$
    BEGIN
        PERFORM catalog_backfill_deleted(etable, NULL);
        RETURN 0;
    END;
    $$
    """,
)


def _drop_helpers(engine) -> None:
    with engine.begin() as connection:
        for name in _HELPERS:
            connection.execute(text(f"DROP FUNCTION IF EXISTS {name}"))


def _result_type(connection, name: str) -> str | None:
    return connection.execute(
        text(
            "SELECT pg_get_function_result(p.oid) "
            "FROM pg_proc p "
            "JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = 'public' AND p.proname = :name"
        ),
        {"name": name},
    ).scalar()


def test_upgrade_replaces_integer_backfill_functions(test_engine) -> None:
    if test_engine.dialect.name != "postgresql":
        pytest.skip("catalog version DDL is PostgreSQL")
    with Session(test_engine) as session:
        if session.scalar(text("SELECT to_regclass('public.alembic_version')")) is None:
            pytest.skip("alembic_version is not installed")
        current = session.scalar(text("SELECT version_num FROM alembic_version"))
    if current not in _READY:
        pytest.skip(f"database is at {current}")

    os.environ["DATABASE_URL"] = test_engine.url.render_as_string(hide_password=False)
    from alembic import command
    from alembic.config import Config

    config = Config(str(_INI))
    config.set_main_option("script_location", str(_SCRIPT))
    try:
        if current == _HEAD:
            command.downgrade(config, "0048_catalog_versions")
        _drop_helpers(test_engine)
        with test_engine.begin() as connection:
            for statement in _OLD_HELPERS:
                connection.execute(text(statement))
            assert _result_type(connection, "catalog_backfill_live_batch") == "integer"
            assert (
                _result_type(connection, "catalog_backfill_deleted_batch") == "integer"
            )
        command.upgrade(config, "head")
        with Session(test_engine) as session:
            assert (
                session.scalar(text("SELECT version_num FROM alembic_version")) == _HEAD
            )
            assert (
                session.scalar(
                    text("SELECT to_regprocedure('catalog_backfill_live_batch(text)')")
                )
                is None
            )
            assert (
                session.scalar(
                    text(
                        "SELECT to_regprocedure('catalog_backfill_deleted_batch(text)')"
                    )
                )
                is None
            )
    finally:
        _drop_helpers(test_engine)
        command.upgrade(config, "head")
