"""Empty catalog import times are filled from import history."""

from __future__ import annotations

import importlib.util
import inspect
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from app.db.models import CatalogVersion, ImportJob, Organization, OrganizationMerge
from sqlalchemy import text
from sqlalchemy.orm import Session

_REVISION = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "db"
    / "alembic"
    / "versions"
    / "0052_import_time_backfill.py"
)
_EARLY = datetime(2024, 1, 15, tzinfo=UTC)
_LATER = datetime(2024, 6, 1, tzinfo=UTC)
_KEPT = datetime(2023, 5, 1, tzinfo=UTC)
_TOUCHED = datetime(2022, 1, 1, tzinfo=UTC)


def _revision():
    spec = importlib.util.spec_from_file_location(
        "rev_0052_import_time_backfill",
        _REVISION,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _org(session: Session, *, imported_at: datetime | None = None) -> Organization:
    org = Organization(
        name=f"Org {uuid4().hex[:8]}",
        manager_id="00000000-0000-0000-0000-0000000000aa",
        review_status="pending_review",
        last_imported_at=imported_at,
        updated_at=_TOUCHED,
        version=3,
    )
    session.add(org)
    session.flush()
    return org


def _job(
    session: Session,
    when: datetime,
    results: list[dict],
    *,
    dry_run: bool = False,
    status: str = "completed",
) -> ImportJob:
    job = ImportJob(
        object_key=f"admin/imports/{uuid4().hex}.json",
        dry_run=dry_run,
        status=status,
        summary={},
        results=results,
        file_warnings=[],
        created_at=when,
        updated_at=when,
    )
    session.add(job)
    session.flush()
    return job


def _org_result(org_id: object, status: str) -> dict:
    return {
        "type": "organizations",
        "key": "Playhouse",
        "status": status,
        "id": str(org_id),
        "warnings": [],
        "errors": [],
    }


def _apply(session: Session) -> None:
    session.execute(text(_revision().BACKFILL_SQL))
    session.expire_all()


def test_downgrade_does_not_clear_times() -> None:
    module = _revision()
    body = inspect.getsource(module.downgrade).upper()
    assert "UPDATE" not in body
    assert "DELETE" not in body
    assert "op.execute(sa.text(BACKFILL_SQL))" in inspect.getsource(module.upgrade)


def test_backfill_fills_times_and_keeps_stored_ones(db_session: Session) -> None:
    if db_session.get_bind().dialect.name != "postgresql":
        pytest.skip("jsonb history backfill is PostgreSQL")
    skipped = _org(db_session)
    created = _org(db_session)
    kept = _org(db_session, imported_at=_KEPT)
    kept.import_job_id = None
    child_only = _org(db_session)
    untouched = _org(db_session)
    creating = _job(
        db_session,
        _EARLY,
        [_org_result(created.id, "created"), _org_result(kept.id, "created")],
    )
    _job(
        db_session,
        _LATER,
        [
            _org_result(skipped.id, "skipped"),
            _org_result(created.id, "unchanged"),
            _org_result(kept.id, "updated"),
        ],
    )
    dry = _job(
        db_session,
        datetime(2025, 1, 1, tzinfo=UTC),
        [_org_result(untouched.id, "created")],
        dry_run=True,
    )
    failed = _job(
        db_session,
        datetime(2025, 2, 1, tzinfo=UTC),
        [_org_result(untouched.id, "failed")],
    )
    _job(
        db_session,
        datetime(2025, 3, 1, tzinfo=UTC),
        [_org_result(untouched.id, "created")],
        status="failed",
    )
    location_id = uuid4()
    db_session.add(
        CatalogVersion(
            entity_type="location",
            entity_id=location_id,
            org_id=child_only.id,
            version=1,
            action="created",
            snapshot={"address": "1 Lane"},
            txid=1,
            import_job_id=creating.id,
            created_at=datetime(2024, 3, 1, tzinfo=UTC),
        )
    )
    db_session.flush()

    _apply(db_session)

    db_session.refresh(skipped)
    db_session.refresh(created)
    db_session.refresh(kept)
    db_session.refresh(child_only)
    db_session.refresh(untouched)
    assert skipped.last_imported_at == _LATER
    assert skipped.import_job_id is None
    assert created.last_imported_at == _LATER
    assert created.import_job_id == creating.id
    assert kept.last_imported_at == _KEPT
    assert kept.import_job_id == creating.id
    assert child_only.last_imported_at == datetime(2024, 3, 1, tzinfo=UTC)
    assert child_only.import_job_id is None
    assert untouched.last_imported_at is None
    assert untouched.import_job_id is None
    for org in (skipped, created, kept, child_only, untouched):
        assert org.updated_at == _TOUCHED
        assert org.version == 3
    assert dry.dry_run is True
    assert failed.status == "completed"

    _apply(db_session)
    db_session.refresh(created)
    assert created.last_imported_at == _LATER
    assert created.import_job_id == creating.id


def test_backfill_follows_a_merge_and_ignores_a_delete(db_session: Session) -> None:
    if db_session.get_bind().dialect.name != "postgresql":
        pytest.skip("jsonb history backfill is PostgreSQL")
    survivor = _org(db_session)
    merged_id = uuid4()
    deleted_id = uuid4()
    db_session.add(
        OrganizationMerge(
            merged_org_id=merged_id,
            survivor_org_id=survivor.id,
            snapshot={"name": "Folded"},
            moved_counts={},
        )
    )
    db_session.add(
        OrganizationMerge(
            merged_org_id=deleted_id,
            survivor_org_id=None,
            kind="delete",
            snapshot={"name": "Gone"},
            moved_counts={},
        )
    )
    db_session.flush()
    job = _job(
        db_session,
        _EARLY,
        [
            _org_result(merged_id, "created"),
            _org_result(deleted_id, "created"),
            _org_result("not-a-uuid", "created"),
        ],
    )

    _apply(db_session)

    db_session.refresh(survivor)
    assert survivor.last_imported_at == _EARLY
    assert survivor.import_job_id == job.id
    assert survivor.updated_at == _TOUCHED
    assert survivor.version == 3
