"""Downgrade of catalog history drops the table and version columns."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

_ROOT = Path(__file__).resolve().parents[1]
_INI = _ROOT / "backend" / "db" / "alembic.ini"
_SCRIPT = _ROOT / "backend" / "db" / "alembic"
_READY = {"0047_catalog_versions", "0048_catalog_version_fixes"}


def test_downgrade_to_0046_removes_catalog_versions(test_engine) -> None:
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
        command.downgrade(config, "0046_deleted_org_import")
        with Session(test_engine) as session:
            assert (
                session.scalar(text("SELECT to_regclass('public.catalog_versions')"))
                is None
            )
            column = session.scalar(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema = 'public' "
                    "AND table_name = 'organizations' "
                    "AND column_name = 'version'"
                )
            )
            assert column is None
    finally:
        command.upgrade(config, "head")
        with Session(test_engine) as session:
            assert session.scalar(
                text("SELECT to_regprocedure('catalog_versions_guard()')")
            )
            assert (
                session.scalar(text("SELECT version_num FROM alembic_version"))
                == "0048_catalog_version_fixes"
            )
