"""A full-access crud partner key can import a catalog file."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.api.partner_imports import (
    _apply_flags,
    partner_import_object_key,
    resolve_import_manager,
)
from app.api.partner_routes import handle_partner_routes
from app.db.models import (
    ActivityCategory,
    GeographicArea,
    ImportJob,
    Location,
    Organization,
)
from app.services.catalog_version_match import set_import_job_context
from app.services.category_suggestions.resolve import import_enrichment_ids
from app.services.data_quality.runs import enqueue_staged_run, stage_import_run
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.test_partner_routes import _partner_event

_MANAGER = "00000000-0000-0000-0000-0000000000aa"
_OTHER = "00000000-0000-0000-0000-0000000000bb"
_PLACEHOLDER = "REPLACE_WITH_YOUR_MANAGER_ID"


def _patch_engine(monkeypatch, engine) -> None:
    monkeypatch.setattr("app.api.partner_imports.get_engine", lambda: engine)


def _post(
    body: dict,
    *,
    query: str = "",
    scope: str = "crud",
    org_scope: str = "",
) -> dict:
    path = "/v1/partner/imports" + (("?" + query) if query else "")
    event = _partner_event("POST", path, scope, org_scope)
    event["body"] = json.dumps(body)
    if query:
        event["queryStringParameters"] = dict(
            part.split("=", 1) for part in query.split("&")
        )
    return handle_partner_routes(event, "POST", "imports", None)


def _payload(name: str, *, description: str | None = "Visited restaurant") -> dict:
    return {
        "default_manager_id": _PLACEHOLDER,
        "organizations": [
            {
                "name": name,
                "description": description,
                "website": "https://example.test/restaurant",
                "locations": [
                    {
                        "name": "1 Test Street",
                        "address": "1 Test Street",
                        "area_name": "Partner Import Area",
                        "lat": 22.2,
                        "lng": 114.2,
                    }
                ],
                "activities": [
                    {
                        "name": name,
                        "kind": "eat",
                        "description": "Lunch with high chairs",
                        "category_id": None,
                    }
                ],
            }
        ],
    }


def _seed(engine) -> str:
    with Session(engine) as session:
        area = session.scalar(
            select(GeographicArea).where(GeographicArea.name == "Partner Import Area")
        )
        if area is None:
            session.add(
                GeographicArea(
                    name="Partner Import Area",
                    level="neighbourhood",
                    active=True,
                )
            )
        category = ActivityCategory(name=f"Eat {uuid4().hex[:8]}", display_order=0)
        session.add(category)
        session.commit()
        return str(category.id)


def _delete(engine, name: str, category_id: str) -> None:
    with Session(engine) as session:
        org = session.scalar(select(Organization).where(Organization.name == name))
        if org is not None:
            session.delete(org)
        category = session.get(ActivityCategory, category_id)
        if category is not None:
            session.delete(category)
        area = session.scalar(
            select(GeographicArea).where(GeographicArea.name == "Partner Import Area")
        )
        if (
            area is not None
            and session.scalar(
                select(Location.id).where(Location.area_id == area.id).limit(1)
            )
            is None
        ):
            session.delete(area)
        session.commit()


def test_read_and_scoped_keys_are_forbidden() -> None:
    read = _post({"organizations": []}, scope="read")
    assert read["statusCode"] == 403
    assert "write access" in json.loads(read["body"])["error"]

    scoped = _post({"organizations": []}, org_scope=str(uuid4()))
    assert scoped["statusCode"] == 403
    assert "limited to one organization" in json.loads(scoped["body"])["error"]


def test_placeholder_stops_before_the_database(monkeypatch) -> None:
    def boom():
        raise AssertionError("database opened")

    monkeypatch.setattr("app.api.partner_imports.get_engine", boom)
    monkeypatch.delenv("BOARD_CATALOG_MANAGER_ID", raising=False)
    response = _post(
        {"default_manager_id": _PLACEHOLDER, "organizations": [{"name": "No Write"}]}
    )
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["error"] == "default_manager_id must be a UUID"
    assert body["detail"] == "Field: default_manager_id"


def test_other_manager_is_rejected_before_the_database(monkeypatch) -> None:
    def boom():
        raise AssertionError("database opened")

    monkeypatch.setattr("app.api.partner_imports.get_engine", boom)
    monkeypatch.setenv("BOARD_CATALOG_MANAGER_ID", _MANAGER)
    response = _post(
        {"default_manager_id": _OTHER, "organizations": [{"name": "Wrong Manager"}]}
    )
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["error"] == "manager_id must be the catalog manager"
    assert body["detail"] == "Field: manager_id"


def test_query_manager_imports_and_can_verify_and_approve(
    monkeypatch, test_engine
) -> None:
    _patch_engine(monkeypatch, test_engine)
    monkeypatch.delenv("BOARD_CATALOG_MANAGER_ID", raising=False)
    name = f"Partner Eat {uuid4().hex[:8]}"
    category_id = _seed(test_engine)
    body = _payload(name)
    body["organizations"][0]["activities"][0]["category_id"] = category_id
    try:
        response = _post(
            body,
            query=f"manager_id={_MANAGER}&mark_parent_verified=true&approve=true",
        )
        assert response["statusCode"] == 200
        payload = json.loads(response["body"])
        assert payload["summary"]["organizations"]["created"] == 1
        assert payload["blocked"] == []
        assert payload["failed"] == []
        assert payload["skipped"] == []
        assert payload["replayed"] is False
        assert payload["summary"]["source"] == "partner"
        with Session(test_engine) as session:
            org = session.scalar(select(Organization).where(Organization.name == name))
            assert org is not None
            assert str(org.manager_id) == _MANAGER
            assert org.parent_verified is True
            assert org.parent_verified_at is not None
            assert org.review_status == "approved"
            assert org.website == "https://example.test/restaurant"
            assert org.locations[0].lat == Decimal("22.2")
            assert str(org.import_job_id) == payload["id"]
        assert payload["parent_verified"] == [str(org.id)]
        assert payload["approved"] == [str(org.id)]
    finally:
        _delete(test_engine, name, category_id)


def test_file_flag_does_not_verify(monkeypatch, test_engine) -> None:
    _patch_engine(monkeypatch, test_engine)
    monkeypatch.setenv("BOARD_CATALOG_MANAGER_ID", _MANAGER)
    name = f"Unverified Eat {uuid4().hex[:8]}"
    category_id = _seed(test_engine)
    body = _payload(name)
    body["organizations"][0]["parent_verified"] = True
    body["organizations"][0]["activities"][0]["category_id"] = category_id
    try:
        response = _post(body)
        assert response["statusCode"] == 200
        payload = json.loads(response["body"])
        assert payload["parent_verified"] == []
        assert payload["approved"] == []
        assert any(
            "parent_verified" in warning
            for warning in payload["results"][0]["warnings"]
        )
        with Session(test_engine) as session:
            org = session.scalar(select(Organization).where(Organization.name == name))
            assert org is not None
            assert org.parent_verified is False
            assert org.review_status == "pending_review"
    finally:
        _delete(test_engine, name, category_id)


def test_blocked_approval_keeps_the_import(monkeypatch, test_engine) -> None:
    _patch_engine(monkeypatch, test_engine)
    monkeypatch.setenv("BOARD_CATALOG_MANAGER_ID", _MANAGER)
    name = f"Blocked Eat {uuid4().hex[:8]}"
    category_id = _seed(test_engine)
    body = _payload(name, description=None)
    body["organizations"][0]["activities"][0]["category_id"] = category_id
    try:
        response = _post(body, query="approve=true")
        assert response["statusCode"] == 200
        payload = json.loads(response["body"])
        assert payload["approved"] == []
        assert payload["blocked"][0]["issues"]
        with Session(test_engine) as session:
            org = session.scalar(select(Organization).where(Organization.name == name))
            assert org is not None
            assert org.review_status == "pending_review"
    finally:
        _delete(test_engine, name, category_id)


def test_flags_leave_a_matched_organisation_alone(monkeypatch, test_engine) -> None:
    _patch_engine(monkeypatch, test_engine)
    monkeypatch.setenv("BOARD_CATALOG_MANAGER_ID", _MANAGER)
    name = f"Second Eat {uuid4().hex[:8]}"
    category_id = _seed(test_engine)
    body = _payload(name)
    body["organizations"][0]["activities"][0]["category_id"] = category_id
    try:
        first = _post(body)
        assert json.loads(first["body"])["summary"]["organizations"]["created"] == 1
        second = _post(body, query="mark_parent_verified=true&approve=true")
        assert second["statusCode"] == 200
        payload = json.loads(second["body"])
        assert payload["summary"]["organizations"]["created"] == 0
        assert payload["parent_verified"] == []
        assert payload["approved"] == []
        assert payload["replayed"] is False
        with Session(test_engine) as session:
            org = session.scalar(select(Organization).where(Organization.name == name))
            assert org is not None
            assert org.parent_verified is False
            assert org.review_status == "pending_review"
    finally:
        _delete(test_engine, name, category_id)


def test_dry_run_rejects_the_live_flags(monkeypatch) -> None:
    def boom():
        raise AssertionError("database opened")

    monkeypatch.setattr("app.api.partner_imports.get_engine", boom)
    monkeypatch.setenv("BOARD_CATALOG_MANAGER_ID", _MANAGER)
    response = _post(
        {"default_manager_id": _MANAGER, "organizations": [{"name": "Dry"}]},
        query="dry_run=true&approve=true",
    )
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "live import" in body["error"]
    assert body["detail"] == "Field: dry_run"


def test_repeat_returns_the_stored_job_and_keeps_a_rejection(
    monkeypatch, test_engine
) -> None:
    _patch_engine(monkeypatch, test_engine)
    monkeypatch.setenv("BOARD_CATALOG_MANAGER_ID", _MANAGER)
    name = f"Replay Eat {uuid4().hex[:8]}"
    category_id = _seed(test_engine)
    body = _payload(name)
    body["organizations"][0]["activities"][0]["category_id"] = category_id
    query = "mark_parent_verified=true&approve=true"
    try:
        first = json.loads(_post(body, query=query)["body"])
        second = _post(body, query="mark_parent_verified=True&approve=1")
        assert second["statusCode"] == 200
        replay = json.loads(second["body"])
        assert replay["replayed"] is True
        assert replay["id"] == first["id"]
        with Session(test_engine) as session:
            org = session.scalar(select(Organization).where(Organization.name == name))
            assert org is not None
            org.review_status = "rejected"
            org.review_reason = "not_relevant"
            session.commit()
            org_id = str(org.id)
        third = json.loads(_post(body, query=query)["body"])
        assert third["replayed"] is True
        assert third["id"] == first["id"]
        with Session(test_engine) as session:
            org = session.get(Organization, org_id)
            assert org is not None
            assert org.review_status == "rejected"
            assert org.parent_verified is True
    finally:
        _delete(test_engine, name, category_id)


def test_flags_do_not_touch_a_rejected_name_match(monkeypatch, test_engine) -> None:
    _patch_engine(monkeypatch, test_engine)
    monkeypatch.setenv("BOARD_CATALOG_MANAGER_ID", _MANAGER)
    name = f"Rejected Eat {uuid4().hex[:8]}"
    category_id = _seed(test_engine)
    with Session(test_engine) as session:
        session.add(
            Organization(
                name=name,
                manager_id=_MANAGER,
                description="Visited restaurant",
                review_status="rejected",
                review_reason="duplicate",
            )
        )
        session.commit()
    body = _payload(name)
    body["organizations"][0]["activities"][0]["category_id"] = category_id
    try:
        response = _post(body, query="mark_parent_verified=true&approve=true")
        assert response["statusCode"] == 200
        payload = json.loads(response["body"])
        assert payload["summary"]["organizations"]["created"] == 0
        assert payload["parent_verified"] == []
        assert payload["approved"] == []
        with Session(test_engine) as session:
            org = session.scalar(select(Organization).where(Organization.name == name))
            assert org is not None
            assert org.review_status == "rejected"
            assert org.parent_verified is False
    finally:
        _delete(test_engine, name, category_id)


def test_running_job_conflicts_until_it_is_stale(monkeypatch, test_engine) -> None:
    _patch_engine(monkeypatch, test_engine)
    monkeypatch.setenv("BOARD_CATALOG_MANAGER_ID", _MANAGER)
    name = f"Running Eat {uuid4().hex[:8]}"
    category_id = _seed(test_engine)
    body = _payload(name)
    body["organizations"][0]["activities"][0]["category_id"] = category_id
    probe = deepcopy(body)
    resolve_import_manager(probe, None, _MANAGER)
    object_key = partner_import_object_key(
        probe,
        _MANAGER,
        {"dry_run": False, "mark_parent_verified": False, "approve": False},
    )
    with Session(test_engine) as session:
        session.add(
            ImportJob(
                object_key=object_key,
                dry_run=False,
                status="running",
                summary={"source": "partner"},
                results=[],
                file_warnings=[],
            )
        )
        session.commit()
    try:
        conflict = _post(body)
        assert conflict["statusCode"] == 409
        assert json.loads(conflict["body"])["id"]
        with Session(test_engine) as session:
            job = session.scalar(
                select(ImportJob).where(ImportJob.object_key == object_key)
            )
            assert job is not None
            job.updated_at = datetime.now(UTC) - timedelta(minutes=10)
            session.commit()
        taken = _post(body)
        assert taken["statusCode"] == 200
        payload = json.loads(taken["body"])
        assert payload["replayed"] is False
        assert payload["summary"]["organizations"]["created"] == 1
    finally:
        _delete(test_engine, name, category_id)


def test_invalid_flag_stops_before_the_database(monkeypatch) -> None:
    def boom():
        raise AssertionError("database opened")

    monkeypatch.setattr("app.api.partner_imports.get_engine", boom)
    monkeypatch.setenv("BOARD_CATALOG_MANAGER_ID", _MANAGER)
    response = _post(
        {"default_manager_id": _MANAGER, "organizations": [{"name": "Flag"}]},
        query="approve=yes",
    )
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["error"] == "approve must be true or false"


def test_failed_and_skipped_rows_are_listed(monkeypatch, test_engine) -> None:
    _patch_engine(monkeypatch, test_engine)
    monkeypatch.setenv("BOARD_CATALOG_MANAGER_ID", _MANAGER)
    name = f"Provider Eat {uuid4().hex[:8]}"
    place_id = f"partner-import-{uuid4().hex[:8]}"
    with Session(test_engine) as session:
        session.add(
            Organization(
                name=name,
                manager_id=_OTHER,
                place_id=place_id,
                description="Owned elsewhere",
            )
        )
        session.commit()
    try:
        response = _post(
            {
                "default_manager_id": _MANAGER,
                "organizations": [
                    "nope",
                    {
                        "name": name,
                        "place_id": place_id,
                        "locations": [{"name": "Venue", "address": "1 Test"}],
                    },
                ],
            }
        )
        assert response["statusCode"] == 200
        payload = json.loads(response["body"])
        assert payload["failed"][0]["status"] == "failed"
        assert payload["failed"][0]["errors"]
        assert payload["skipped"]
        assert payload["blocked"] == []
        with Session(test_engine) as session:
            org = session.scalar(select(Organization).where(Organization.name == name))
            assert org is not None
            assert str(org.manager_id) == _OTHER
            assert org.parent_verified is False
    finally:
        _delete(test_engine, name, str(uuid4()))


def test_follow_up_runs_are_queued(monkeypatch, test_engine) -> None:
    _patch_engine(monkeypatch, test_engine)
    monkeypatch.delenv("BOARD_CATALOG_MANAGER_ID", raising=False)
    name = f"Follow Eat {uuid4().hex[:8]}"
    category_id = _seed(test_engine)
    body = _payload(name)
    body["organizations"][0]["activities"][0]["category_id"] = category_id
    seen: dict = {}
    real_context = set_import_job_context
    real_ids = import_enrichment_ids
    real_stage = stage_import_run
    real_enqueue_run = enqueue_staged_run

    def context(session, job_id):
        seen["job_id"] = str(job_id)
        return real_context(session, job_id)

    def enrichment_ids(*, dry_run: bool):
        real_ids(dry_run=dry_run)
        seen["enrichment_cleared"] = True
        if dry_run:
            return []
        return ["00000000-0000-0000-0000-0000000000cc"]

    def stage(session, **kwargs):
        seen["requested_by"] = kwargs["requested_by"]
        return real_stage(session, **kwargs)

    def enqueue_run(run_id):
        seen["run_id"] = run_id
        return real_enqueue_run(run_id)

    def enqueue_categories(ids, **kwargs):
        del kwargs
        seen["enqueued"] = list(ids)

    monkeypatch.setattr(
        "app.services.catalog_version_match.set_import_job_context",
        context,
    )
    monkeypatch.setattr(
        "app.services.category_suggestions.resolve.import_enrichment_ids",
        enrichment_ids,
    )
    monkeypatch.setattr(
        "app.services.data_quality.runs.stage_import_run",
        stage,
    )
    monkeypatch.setattr(
        "app.services.data_quality.runs.enqueue_staged_run",
        enqueue_run,
    )
    monkeypatch.setattr(
        "app.services.category_suggestions.events.enqueue_enrichment",
        enqueue_categories,
    )
    try:
        response = _post(
            body,
            query=f"manager_id={_MANAGER}&mark_parent_verified=true&approve=true",
        )
        assert response["statusCode"] == 200
        payload = json.loads(response["body"])
        assert seen["job_id"] == payload["id"]
        assert seen["enrichment_cleared"] is True
        assert seen["enqueued"] == ["00000000-0000-0000-0000-0000000000cc"]
        assert str(seen["requested_by"]).startswith("api-key:")
        if payload.get("data_quality_run_id"):
            assert seen["run_id"] == payload["data_quality_run_id"]
        else:
            assert "run_id" not in seen
    finally:
        _delete(test_engine, name, category_id)


def test_verify_list_skips_an_org_that_is_already_verified(
    monkeypatch, test_engine
) -> None:
    _patch_engine(monkeypatch, test_engine)
    monkeypatch.setenv("BOARD_CATALOG_MANAGER_ID", _MANAGER)
    name = f"Already Eat {uuid4().hex[:8]}"
    category_id = _seed(test_engine)
    body = _payload(name)
    body["organizations"][0]["activities"][0]["category_id"] = category_id
    try:
        created = json.loads(_post(body)["body"])
        org_id = created["results"][0]["id"]
        with Session(test_engine) as session:
            org = session.get(Organization, org_id)
            assert org is not None
            org.parent_verified = True
            org.parent_verified_at = datetime(2026, 1, 1, tzinfo=UTC)
            org.review_status = "approved"
            session.commit()
            checked_at = org.parent_verified_at
        with Session(test_engine) as session:
            verified, approved, blocked = _apply_flags(
                session,
                [{"type": "organizations", "status": "created", "id": org_id}],
                mark_parent_verified=True,
                approve=True,
                reviewer="api-key:test",
            )
            session.commit()
            org = session.get(Organization, org_id)
            assert org is not None
            assert verified == []
            assert approved == []
            assert blocked == []
            assert org.parent_verified_at == checked_at
            assert org.review_status == "approved"
    finally:
        _delete(test_engine, name, category_id)


def test_approve_leaves_a_rejected_organisation(monkeypatch, test_engine) -> None:
    _patch_engine(monkeypatch, test_engine)
    monkeypatch.setenv("BOARD_CATALOG_MANAGER_ID", _MANAGER)
    name = f"Guard Eat {uuid4().hex[:8]}"
    category_id = _seed(test_engine)
    body = _payload(name)
    body["organizations"][0]["activities"][0]["category_id"] = category_id
    try:
        created = json.loads(_post(body)["body"])
        org_id = created["results"][0]["id"]
        with Session(test_engine) as session:
            org = session.get(Organization, org_id)
            assert org is not None
            org.review_status = "rejected"
            org.review_reason = "duplicate"
            session.commit()
        with Session(test_engine) as session:
            _verified, approved, blocked = _apply_flags(
                session,
                [{"type": "organizations", "status": "created", "id": org_id}],
                mark_parent_verified=False,
                approve=True,
                reviewer="api-key:test",
            )
            session.commit()
            org = session.get(Organization, org_id)
            assert org is not None
            assert approved == []
            assert blocked[0]["message"] == "Organization is rejected"
            assert org.review_status == "rejected"
    finally:
        _delete(test_engine, name, category_id)


def test_dry_run_is_stored_and_replayed(monkeypatch, test_engine) -> None:
    _patch_engine(monkeypatch, test_engine)
    monkeypatch.setenv("BOARD_CATALOG_MANAGER_ID", _MANAGER)
    name = f"Dry Eat {uuid4().hex[:8]}"
    category_id = _seed(test_engine)
    body = _payload(name)
    body["organizations"][0]["activities"][0]["category_id"] = category_id
    try:
        first = _post(body, query="dry_run=true")
        assert first["statusCode"] == 200
        payload = json.loads(first["body"])
        assert payload["replayed"] is False
        assert payload["summary"]["organizations"]["created"] == 1
        second = json.loads(_post(body, query="dry_run=TRUE")["body"])
        assert second["replayed"] is True
        assert second["id"] == payload["id"]
        with Session(test_engine) as session:
            org = session.scalar(select(Organization).where(Organization.name == name))
            assert org is None
            job = session.get(ImportJob, payload["id"])
            assert job is not None
            assert job.dry_run is True
            assert job.summary["source"] == "partner"
    finally:
        _delete(test_engine, name, category_id)
