"""Backfill organization websites from stored import jobs."""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from app.db.models import ImportJob, Organization, OrganizationMerge
from app.services.import_website_backfill import (
    WEBSITE_DISCARD_WARNING,
    backfill_import_websites,
    load_s3_import_payload,
)
from botocore.exceptions import ClientError


def _org(db_session, name: str, website: str | None = None) -> Organization:
    org = Organization(
        name=name,
        manager_id="00000000-0000-0000-0000-0000000000aa",
        review_status="pending_review",
        website=website,
    )
    db_session.add(org)
    db_session.flush()
    return org


def _warning(path: str) -> str:
    return f"{path}: {WEBSITE_DISCARD_WARNING}"


def _job(
    db_session,
    *,
    when: datetime,
    object_key: str,
    results: list[dict],
    warnings: list[str],
    summary_warnings: int,
    dry_run: bool = False,
    status: str = "completed",
    updated_at: datetime | None = None,
) -> ImportJob:
    job = ImportJob(
        object_key=object_key,
        dry_run=dry_run,
        status=status,
        summary={
            "warnings": summary_warnings,
            "organizations": {
                "created": 0,
                "updated": 0,
                "failed": 0,
                "skipped": 0,
            },
        },
        results=results,
        file_warnings=warnings,
        created_at=when,
        updated_at=updated_at or when,
    )
    db_session.add(job)
    db_session.flush()
    return job


def _org_result(org: Organization, status: str, path: str, warning: str) -> dict:
    return {
        "type": "organizations",
        "key": org.name,
        "status": status,
        "id": str(org.id),
        "warnings": [warning, "kept warning"],
        "errors": [],
        "path": path,
    }


def test_backfill_writes_websites_and_drops_warnings(db_session) -> None:
    created = _org(db_session, f"Created {uuid4().hex[:8]}")
    skipped = _org(db_session, f"Skipped {uuid4().hex[:8]}")
    kept = _org(db_session, f"Kept {uuid4().hex[:8]}", "https://keep.example")
    created_warning = _warning("organizations[0]")
    skip_warning = _warning("organizations[1]")
    keep_warning = _warning("organizations[2]")
    first = _job(
        db_session,
        when=datetime(2024, 1, 1, tzinfo=UTC),
        object_key=f"admin/imports/first-{uuid4().hex}.json",
        results=[_org_result(created, "created", "organizations[0]", created_warning)],
        warnings=[created_warning],
        summary_warnings=2,
    )
    second = _job(
        db_session,
        when=datetime(2024, 2, 1, tzinfo=UTC),
        object_key=f"admin/imports/second-{uuid4().hex}.json",
        results=[
            _org_result(created, "updated", "organizations[0]", created_warning),
            _org_result(skipped, "skipped", "organizations[1]", skip_warning),
            _org_result(kept, "skipped", "organizations[2]", keep_warning),
        ],
        warnings=[created_warning, skip_warning, keep_warning],
        summary_warnings=6,
    )
    dry = _job(
        db_session,
        when=datetime(2024, 3, 1, tzinfo=UTC),
        object_key=f"admin/imports/dry-{uuid4().hex}.json",
        results=[_org_result(created, "created", "organizations[0]", created_warning)],
        warnings=[created_warning],
        summary_warnings=2,
        dry_run=True,
    )
    missing_key = f"admin/imports/missing-{uuid4().hex}.json"
    missing = _job(
        db_session,
        when=datetime(2024, 4, 1, tzinfo=UTC),
        object_key=missing_key,
        results=[_org_result(skipped, "created", "organizations[0]", skip_warning)],
        warnings=[skip_warning],
        summary_warnings=2,
    )
    payloads = {
        first.object_key: {
            "organizations": [{"name": created.name, "website": "https://old.example"}]
        },
        second.object_key: {
            "organizations": [
                {"name": created.name, "website": " https://new.example "},
                {"name": skipped.name, "website": "https://skipped.example"},
                {"name": kept.name, "website": "https://replace.example"},
            ]
        },
        dry.object_key: {
            "organizations": [{"name": created.name, "website": "https://dry.example"}]
        },
    }

    report = backfill_import_websites(
        db_session,
        lambda key: payloads.get(key),
    )
    db_session.flush()

    db_session.refresh(created)
    db_session.refresh(skipped)
    db_session.refresh(kept)
    db_session.refresh(first)
    db_session.refresh(second)
    db_session.refresh(dry)
    db_session.refresh(missing)
    assert created.website == "https://new.example"
    assert skipped.website == "https://skipped.example"
    assert kept.website == "https://keep.example"
    assert report.websites_written == 3
    assert report.payloads_missing == [missing_key]
    assert all(
        WEBSITE_DISCARD_WARNING not in warning
        for job in (first, second, dry)
        for warning in (job.file_warnings or [])
    )
    assert first.results[0]["warnings"] == ["kept warning"]
    assert first.summary["warnings"] == 1
    assert second.summary["warnings"] == 3
    assert dry.results[0]["warnings"] == ["kept warning"]
    assert missing.file_warnings == [skip_warning]
    assert missing.results[0]["warnings"] == [skip_warning, "kept warning"]
    assert missing.summary["warnings"] == 2


def test_backfill_fills_a_merged_survivor_and_skips_a_delete(db_session) -> None:
    survivor = _org(db_session, f"Survivor {uuid4().hex[:8]}")
    deleted_name = f"Deleted {uuid4().hex[:8]}"
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
            snapshot={"name": deleted_name},
            moved_counts={},
        )
    )
    db_session.flush()
    warning = _warning("organizations[0]")
    merged_job = _job(
        db_session,
        when=datetime(2024, 5, 1, tzinfo=UTC),
        object_key=f"admin/imports/merged-{uuid4().hex}.json",
        results=[
            {
                "type": "organizations",
                "key": "Folded",
                "status": "created",
                "id": str(merged_id),
                "warnings": [warning],
                "errors": [],
                "path": "organizations[0]",
            }
        ],
        warnings=[warning],
        summary_warnings=1,
    )
    deleted_job = _job(
        db_session,
        when=datetime(2024, 6, 1, tzinfo=UTC),
        object_key=f"admin/imports/deleted-{uuid4().hex}.json",
        results=[
            {
                "type": "organizations",
                "key": deleted_name,
                "status": "created",
                "id": str(deleted_id),
                "warnings": [warning],
                "errors": [],
                "path": "organizations[0]",
            }
        ],
        warnings=[warning],
        summary_warnings=1,
    )
    payloads = {
        merged_job.object_key: {
            "organizations": [{"name": "Folded", "website": "https://folded.example"}]
        },
        deleted_job.object_key: {
            "organizations": [{"name": deleted_name, "website": "https://gone.example"}]
        },
    }

    report = backfill_import_websites(db_session, lambda key: payloads.get(key))
    db_session.flush()

    db_session.refresh(survivor)
    assert survivor.website == "https://folded.example"
    assert report.websites_written == 1
    assert db_session.get(Organization, deleted_id) is None


def test_backfill_keeps_a_website_typed_after_the_import(db_session) -> None:
    org = _org(db_session, f"Typed {uuid4().hex[:8]}", "https://typed.example")
    warning = _warning("organizations[0]")
    job = _job(
        db_session,
        when=datetime(2024, 1, 1, tzinfo=UTC),
        object_key=f"admin/imports/typed-{uuid4().hex}.json",
        results=[_org_result(org, "updated", "organizations[0]", warning)],
        warnings=[warning],
        summary_warnings=1,
    )
    payloads = {
        job.object_key: {
            "organizations": [{"name": org.name, "website": "https://file.example"}]
        }
    }

    report = backfill_import_websites(db_session, lambda key: payloads.get(key))
    db_session.flush()

    db_session.refresh(org)
    db_session.refresh(job)
    assert org.website == "https://typed.example"
    assert report.websites_written == 0
    assert job.file_warnings == []
    assert job.results[0]["warnings"] == ["kept warning"]


def test_backfill_uses_the_later_completion(db_session) -> None:
    org = _org(db_session, f"Retried {uuid4().hex[:8]}")
    warning = _warning("organizations[0]")
    early = _job(
        db_session,
        when=datetime(2024, 3, 1, tzinfo=UTC),
        updated_at=datetime(2024, 3, 1, tzinfo=UTC),
        object_key=f"admin/imports/early-{uuid4().hex}.json",
        results=[_org_result(org, "updated", "organizations[0]", warning)],
        warnings=[warning],
        summary_warnings=1,
    )
    retry = _job(
        db_session,
        when=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 4, 1, tzinfo=UTC),
        object_key=f"admin/imports/retry-{uuid4().hex}.json",
        results=[_org_result(org, "updated", "organizations[0]", warning)],
        warnings=[warning],
        summary_warnings=1,
    )
    payloads = {
        early.object_key: {
            "organizations": [{"name": org.name, "website": "https://earlier.example"}]
        },
        retry.object_key: {
            "organizations": [{"name": org.name, "website": "https://later.example"}]
        },
    }

    report = backfill_import_websites(db_session, lambda key: payloads.get(key))
    db_session.flush()

    db_session.refresh(org)
    assert org.website == "https://later.example"
    assert report.websites_written == 2


def test_backfill_leaves_unreadable_and_unfinished_jobs(db_session) -> None:
    quiet = _org(db_session, f"Quiet {uuid4().hex[:8]}", "https://quiet.example")
    failed_org = _org(db_session, f"Failed {uuid4().hex[:8]}")
    running_org = _org(db_session, f"Running {uuid4().hex[:8]}")
    warning = _warning("organizations[0]")
    untouched = _job(
        db_session,
        when=datetime(2024, 1, 1, tzinfo=UTC),
        object_key=f"admin/imports/quiet-{uuid4().hex}.json",
        results=[
            {
                "type": "organizations",
                "key": quiet.name,
                "status": "updated",
                "id": str(quiet.id),
                "warnings": ["kept warning"],
                "errors": [],
                "path": "organizations[0]",
            }
        ],
        warnings=["kept warning"],
        summary_warnings=1,
    )
    failed = _job(
        db_session,
        when=datetime(2024, 2, 1, tzinfo=UTC),
        object_key=f"admin/imports/failed-{uuid4().hex}.json",
        results=[_org_result(failed_org, "created", "organizations[0]", warning)],
        warnings=[warning],
        summary_warnings=1,
        status="failed",
    )
    running = _job(
        db_session,
        when=datetime(2024, 3, 1, tzinfo=UTC),
        object_key=f"admin/imports/running-{uuid4().hex}.json",
        results=[_org_result(running_org, "created", "organizations[0]", warning)],
        warnings=[warning],
        summary_warnings=1,
        status="running",
    )

    def load(key: str) -> dict:
        raise AssertionError(key)

    report = backfill_import_websites(db_session, load)
    db_session.flush()

    db_session.refresh(quiet)
    db_session.refresh(failed)
    db_session.refresh(running)
    assert quiet.website == "https://quiet.example"
    assert failed.file_warnings == [warning]
    assert running.file_warnings == [warning]
    assert report.jobs_seen == 0
    assert report.websites_written == 0
    assert untouched.file_warnings == ["kept warning"]


def test_load_s3_import_payload_reads_an_object(monkeypatch) -> None:
    class _Body:
        def read(self) -> bytes:
            return b'{"organizations": [{"website": "https://studio.example"}]}'

    class _Client:
        def get_object(self, Bucket: str, Key: str) -> dict:
            assert Bucket == "import-bucket"
            assert Key == "admin/imports/catalog.json"
            return {"Body": _Body()}

    monkeypatch.setenv("ADMIN_IMPORT_EXPORT_BUCKET", "import-bucket")
    monkeypatch.setattr(
        "app.services.import_website_backfill.get_s3_client",
        lambda: _Client(),
    )

    assert load_s3_import_payload("admin/imports/catalog.json") == {
        "organizations": [{"website": "https://studio.example"}]
    }


def test_load_s3_import_payload_treats_a_missing_object_as_empty(monkeypatch) -> None:
    class _Client:
        def get_object(self, Bucket: str, Key: str) -> dict:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "gone"}},
                "GetObject",
            )

    monkeypatch.setenv("ADMIN_IMPORT_EXPORT_BUCKET", "import-bucket")
    monkeypatch.setattr(
        "app.services.import_website_backfill.get_s3_client",
        lambda: _Client(),
    )

    assert load_s3_import_payload("admin/imports/gone.json") is None


def test_load_s3_import_payload_rejects_a_non_object(monkeypatch) -> None:
    class _Body:
        def read(self) -> bytes:
            return b"[1]"

    monkeypatch.setenv("ADMIN_IMPORT_EXPORT_BUCKET", "import-bucket")
    monkeypatch.setattr(
        "app.services.import_website_backfill.get_s3_client",
        lambda: type(
            "Client", (), {"get_object": lambda self, **_: {"Body": _Body()}}
        )(),
    )

    assert load_s3_import_payload("admin/imports/list.json") is None


def test_load_s3_import_payload_requires_the_bucket(monkeypatch) -> None:
    monkeypatch.delenv("ADMIN_IMPORT_EXPORT_BUCKET", raising=False)

    with pytest.raises(RuntimeError, match="ADMIN_IMPORT_EXPORT_BUCKET"):
        load_s3_import_payload("admin/imports/catalog.json")


def test_backfill_script_refuses_without_the_bucket(monkeypatch) -> None:
    monkeypatch.delenv("ADMIN_IMPORT_EXPORT_BUCKET", raising=False)
    script = (
        Path(__file__).resolve().parents[1] / "scripts/ops/backfill_org_websites.py"
    )
    spec = importlib.util.spec_from_file_location("backfill_org_websites", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        module,
        "get_engine",
        lambda **_: (_ for _ in ()).throw(AssertionError("engine")),
    )

    assert module.main() == 1


def test_load_s3_import_payload_raises_on_invalid_json(monkeypatch) -> None:
    class _Body:
        def read(self) -> bytes:
            return b"not-json"

    monkeypatch.setenv("ADMIN_IMPORT_EXPORT_BUCKET", "import-bucket")
    monkeypatch.setattr(
        "app.services.import_website_backfill.get_s3_client",
        lambda: type(
            "Client", (), {"get_object": lambda self, **_: {"Body": _Body()}}
        )(),
    )

    with pytest.raises(json.JSONDecodeError):
        load_s3_import_payload("admin/imports/bad.json")
