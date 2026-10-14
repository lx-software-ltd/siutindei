"""Historical import jobs without a source become Board API."""

from __future__ import annotations

import importlib.util
import inspect
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from app.api.admin_imports_jobs import job_source
from app.db.models import ImportJob
from sqlalchemy import text
from sqlalchemy.orm import Session

_REVISION = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "db"
    / "alembic"
    / "versions"
    / "0050_import_job_source.py"
)
_WHEN = datetime(2024, 6, 1, tzinfo=UTC)


def _revision():
    spec = importlib.util.spec_from_file_location(
        "rev_0050_import_job_source",
        _REVISION,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _job(session: Session, summary: dict, stamp: datetime) -> ImportJob:
    job = ImportJob(
        object_key=f"admin/imports/{uuid4().hex}.json",
        dry_run=False,
        status="completed",
        summary=summary,
        results=[],
        file_warnings=[],
        created_at=stamp,
        updated_at=stamp,
    )
    session.add(job)
    session.flush()
    return job


def test_downgrade_does_not_strip_source() -> None:
    module = _revision()
    body = inspect.getsource(module.downgrade).upper()
    assert "UPDATE" not in body
    assert "DELETE" not in body
    assert "op.execute(sa.text(BACKFILL_SQL))" in inspect.getsource(module.upgrade)


def test_backfill_stamps_board_and_keeps_known_sources(db_session) -> None:
    if db_session.get_bind().dialect.name != "postgresql":
        pytest.skip("jsonb_set is PostgreSQL")
    module = _revision()
    unlabeled = _job(
        db_session,
        {"organizations": {"created": 1}, "allow_updates": True},
        _WHEN,
    )
    unknown = _job(
        db_session,
        {"source": "legacy", "allow_updates": False},
        _WHEN,
    )
    empty = _job(db_session, {}, _WHEN)
    ui_job = _job(db_session, {"source": "ui", "warnings": 1}, _WHEN)
    board_job = _job(db_session, {"source": "board", "warnings": 2}, _WHEN)
    array_key = f"admin/imports/array-{uuid4().hex}.json"
    db_session.execute(
        text(
            """
            INSERT INTO import_jobs (
                object_key, summary, results, file_warnings,
                created_at, updated_at
            )
            VALUES (
                :key, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, :when, :when
            )
            """
        ),
        {"key": array_key, "when": _WHEN},
    )
    db_session.execute(text(module.BACKFILL_SQL))
    db_session.expire_all()

    assert unlabeled.summary["source"] == "board"
    assert unlabeled.summary["allow_updates"] is True
    assert unlabeled.summary["organizations"] == {"created": 1}
    assert unknown.summary == {"source": "board", "allow_updates": False}
    assert empty.summary == {"source": "board"}
    assert ui_job.summary == {"source": "ui", "warnings": 1}
    assert board_job.summary == {"source": "board", "warnings": 2}
    for job in (unlabeled, unknown, empty, ui_job, board_job):
        assert job.updated_at == _WHEN
        assert job_source(job) in {"ui", "board"}
    assert job_source(ui_job) == "ui"
    assert job_source(unlabeled) == "board"

    array_summary = db_session.execute(
        text("SELECT summary, updated_at FROM import_jobs WHERE object_key = :key"),
        {"key": array_key},
    ).one()
    assert array_summary.summary == []
    assert array_summary.updated_at == _WHEN
