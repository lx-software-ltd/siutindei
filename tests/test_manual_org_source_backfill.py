"""Unset organization sources become Manual."""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from uuid import uuid4

from app.db.models import Organization
from sqlalchemy.orm import Session

_REVISION = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "db"
    / "alembic"
    / "versions"
    / "0059_manual_org_source.py"
)


def _revision():
    spec = importlib.util.spec_from_file_location(
        "rev_0059_manual_org_source",
        _REVISION,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _org(session: Session, source: str | None) -> Organization:
    org = Organization(
        name=f"Source {uuid4().hex[:8]}",
        manager_id="00000000-0000-0000-0000-000000000061",
        source=source,
    )
    session.add(org)
    session.flush()
    return org


def test_downgrade_does_not_strip_manual() -> None:
    module = _revision()
    body = inspect.getsource(module.downgrade).upper()
    assert "UPDATE" not in body
    assert "DELETE" not in body
    assert "op.execute(sa.text(BACKFILL_SQL))" in inspect.getsource(module.upgrade)


def test_backfill_stamps_manual_and_keeps_known_sources(db_session) -> None:
    module = _revision()
    unset = _org(db_session, None)
    empty = _org(db_session, "")
    lcsd = _org(db_session, "lcsd")
    already = _org(db_session, "manual")
    db_session.execute(module.sa.text(module.BACKFILL_SQL))
    db_session.flush()
    db_session.refresh(unset)
    db_session.refresh(empty)
    db_session.refresh(lcsd)
    db_session.refresh(already)
    assert unset.source == "manual"
    assert empty.source == "manual"
    assert lcsd.source == "lcsd"
    assert already.source == "manual"
