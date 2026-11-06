"""Full-access crud partner keys can run website enrichment."""

from __future__ import annotations

import json
from decimal import Decimal
from uuid import uuid4

from app.api import partner_routes
from app.api.admin import _handle_partner_routes
from app.db.models import AuditLog, Organization
from app.db.models.import_settings import DataQualityRun
from app.db.models.org_enrichment import OrgEnrichmentProposal, OrgEnrichmentRun
from app.services.enrichment.store import load_settings
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tests.test_partner_routes import _partner_event

_MANAGER = "00000000-0000-0000-0000-000000000001"


def _patch_engines(monkeypatch, engine) -> None:
    monkeypatch.setattr("app.api.admin_enrichment.get_engine", lambda: engine)
    monkeypatch.setattr(
        "app.services.enrichment.guard.host_is_blocked",
        lambda host, resolve=None: False,
    )


def _org(session: Session, name: str) -> Organization:
    org = Organization(
        name=name,
        manager_id=_MANAGER,
        review_status="pending_review",
    )
    session.add(org)
    session.flush()
    return org


def _cleanup(engine, *ids) -> None:
    with Session(engine) as session:
        session.execute(
            delete(OrgEnrichmentProposal).where(OrgEnrichmentProposal.org_id.in_(ids))
        )
        session.execute(
            delete(OrgEnrichmentRun).where(OrgEnrichmentRun.org_id.in_(ids))
        )
        for row_id in ids:
            row = session.get(Organization, row_id)
            if row is not None:
                session.delete(row)
        session.commit()


def _event(
    method: str,
    path: str,
    *,
    scope: str = "crud",
    org_id: str = "",
    body: dict | None = None,
) -> dict:
    event = _partner_event(method, path, scope, org_id)
    if body is not None:
        event["body"] = json.dumps(body)
    return event


def _call(event: dict, method: str, resource: str, resource_id: str | None) -> dict:
    return _handle_partner_routes(event, method, resource, resource_id)


def _enrich_event(org_id, method: str, tail: str = "", **kwargs) -> dict:
    path = f"/v1/partner/organizations/{org_id}/enrichment{tail}"
    return _event(method, path, **kwargs)


def _enrich(org_id, method: str, tail: str = "", **kwargs) -> dict:
    return _call(
        _enrich_event(org_id, method, tail, **kwargs),
        method,
        "organizations",
        str(org_id),
    )


def _settings_snapshot(engine) -> tuple[int, Decimal]:
    with Session(engine) as session:
        row = load_settings(session)
        pages = row.max_pages
        limit = Decimal(str(row.monthly_cost_limit_usd))
        session.commit()
        return pages, limit


def _restore_settings(engine, pages: int, limit: Decimal) -> None:
    with Session(engine) as session:
        row = load_settings(session)
        row.max_pages = pages
        row.monthly_cost_limit_usd = limit
        session.commit()


def test_org_scoped_key_cannot_read_enrichment_for_its_own_org() -> None:
    org_id = str(uuid4())
    event = _event(
        "GET",
        f"/v1/partner/organizations/{org_id}/enrichment",
        org_id=org_id,
    )
    response = _call(event, "GET", "organizations", org_id)
    assert response["statusCode"] == 403
    assert "limited to one organization" in json.loads(response["body"])["error"]


def test_read_key_cannot_read_or_start_enrichment() -> None:
    org_id = str(uuid4())
    for method in ("GET", "POST"):
        response = _enrich(org_id, method, scope="read", body={})
        assert response["statusCode"] == 403
        assert "write access" in json.loads(response["body"])["error"]


def test_read_key_cannot_read_enrichment_settings() -> None:
    event = _event("GET", "/v1/partner/enrichment-settings", scope="read")
    response = _call(event, "GET", "enrichment-settings", None)
    assert response["statusCode"] == 403
    assert "write access" in json.loads(response["body"])["error"]


def test_org_scoped_key_cannot_read_enrichment_settings() -> None:
    event = _event(
        "GET",
        "/v1/partner/enrichment-settings",
        org_id=str(uuid4()),
    )
    response = _call(event, "GET", "enrichment-settings", None)
    assert response["statusCode"] == 403
    assert "limited to one organization" in json.loads(response["body"])["error"]


def test_organization_detail_without_enrichment_tail_stays_a_read(monkeypatch) -> None:
    seen: dict[str, str | None] = {}

    def fake_get(event, resource_id, managed_org_ids):
        del event, managed_org_ids
        seen["id"] = resource_id
        return {"statusCode": 200, "body": "{}"}

    monkeypatch.setattr(partner_routes, "partner_get_organizations", fake_get)
    org_id = str(uuid4())
    event = _event("GET", f"/v1/partner/organizations/{org_id}", scope="read")
    response = _call(event, "GET", "organizations", org_id)
    assert response["statusCode"] == 200
    assert seen["id"] == org_id


def test_enrichment_tail_does_not_fall_through_to_organization_update(
    monkeypatch,
) -> None:
    called: list[str] = []

    def fake_crud(*args, **kwargs):
        del args, kwargs
        called.append("crud")
        return {"statusCode": 200, "body": "{}"}

    monkeypatch.setattr(partner_routes, "_handle_crud", fake_crud)
    org_id = str(uuid4())
    response = _enrich(org_id, "PUT", body={"phone_number": "29876543"})
    assert response["statusCode"] == 404
    assert called == []


def test_unknown_enrichment_action_is_404() -> None:
    response = _enrich(uuid4(), "POST", "/nope", body={})
    assert response["statusCode"] == 404


def test_apply_without_ids_is_400() -> None:
    response = _enrich(uuid4(), "POST", "/apply", body={})
    assert response["statusCode"] == 400
    assert "ids" in json.loads(response["body"])["error"]


def test_full_access_get_returns_an_empty_run(monkeypatch, test_engine) -> None:
    _patch_engines(monkeypatch, test_engine)
    token = uuid4().hex[:8]
    with Session(test_engine) as session:
        org = _org(session, f"Harbour Club {token}")
        org_id = org.id
        session.commit()
    try:
        response = _enrich(org_id, "GET")
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["run"] is None
        assert body["proposals"] == []
    finally:
        _cleanup(test_engine, org_id)


def test_full_access_post_queues_a_run(monkeypatch, test_engine) -> None:
    _patch_engines(monkeypatch, test_engine)
    queued: list[tuple[str, str]] = []

    def fake_enqueue(run_id, *, stage: str) -> None:
        queued.append((str(run_id), stage))

    monkeypatch.setattr("app.api.admin_enrichment.enqueue_enrichment", fake_enqueue)
    token = uuid4().hex[:8]
    with Session(test_engine) as session:
        org = _org(session, f"Harbour Club {token}")
        org_id = org.id
        session.commit()
    try:
        response = _enrich(org_id, "POST", body={"website": "https://ok.test/classes"})
        assert response["statusCode"] == 202
        run_id = json.loads(response["body"])["run"]["id"]
        assert queued == [(run_id, "crawl")]
        with Session(test_engine) as session:
            run = session.get(OrgEnrichmentRun, run_id)
            assert run is not None
            assert run.requested_by is not None
            assert run.requested_by.startswith("api-key:")
            assert run.seed_url == "https://ok.test/classes"
            org = session.get(Organization, org_id)
            assert org is not None
            assert org.website in (None, "")
    finally:
        _cleanup(test_engine, org_id)


def test_full_access_post_leaflet_queues_the_leaflet_stage(
    monkeypatch, test_engine
) -> None:
    _patch_engines(monkeypatch, test_engine)
    queued: list[tuple[str, str]] = []

    def fake_enqueue(run_id, *, stage: str) -> None:
        queued.append((str(run_id), stage))

    monkeypatch.setattr("app.api.admin_enrichment.enqueue_enrichment", fake_enqueue)
    token = uuid4().hex[:8]
    with Session(test_engine) as session:
        org = _org(session, f"Leaflet Club {token}")
        org_id = org.id
        session.commit()
    try:
        response = _enrich(
            org_id,
            "POST",
            body={"leaflet": {"url": "https://leaflets.example/term.pdf"}},
        )
        assert response["statusCode"] == 202
        payload = json.loads(response["body"])["run"]
        assert queued == [(payload["id"], "leaflet")]
        assert payload["source"] == "leaflet"
        assert payload["seed_url"] == "https://leaflets.example/term.pdf"
    finally:
        _cleanup(test_engine, org_id)


def test_full_access_presigns_a_leaflet(monkeypatch, test_engine) -> None:
    _patch_engines(monkeypatch, test_engine)

    def fake_presign(org_id, file_name: str, content_type: str) -> dict[str, object]:
        assert file_name == "flyer.jpg"
        assert content_type == "image/jpeg"
        return {
            "upload_url": "https://upload.example",
            "media_url": "https://media.example/k.jpg",
            "object_key": f"organizations/{org_id}/enrichment/leaflets/k.jpg",
            "content_type": content_type,
            "expires_in": 900,
        }

    monkeypatch.setattr("app.services.enrichment.leaflet.presign_leaflet", fake_presign)
    token = uuid4().hex[:8]
    with Session(test_engine) as session:
        org = _org(session, f"Leaflet Upload {token}")
        org_id = org.id
        session.commit()
    try:
        response = _enrich(
            org_id,
            "POST",
            "/leaflet-upload",
            body={"file_name": "flyer.jpg", "content_type": "image/jpeg"},
        )
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["upload_url"] == "https://upload.example"
        assert body["object_key"].endswith(".jpg")
    finally:
        _cleanup(test_engine, org_id)


def test_read_key_cannot_presign_a_leaflet() -> None:
    org_id = str(uuid4())
    response = _enrich(
        org_id,
        "POST",
        "/leaflet-upload",
        scope="read",
        body={"file_name": "flyer.jpg", "content_type": "image/jpeg"},
    )
    assert response["statusCode"] == 403


def test_org_scoped_key_cannot_presign_a_leaflet() -> None:
    org_id = str(uuid4())
    event = _event(
        "POST",
        f"/v1/partner/organizations/{org_id}/enrichment/leaflet-upload",
        org_id=org_id,
        body={"file_name": "flyer.jpg", "content_type": "image/jpeg"},
    )
    response = _call(event, "POST", "organizations", org_id)
    assert response["statusCode"] == 403


def test_start_without_user_sub_records_the_api_key(monkeypatch, test_engine) -> None:
    _patch_engines(monkeypatch, test_engine)
    monkeypatch.setattr(
        "app.api.admin_enrichment.enqueue_enrichment",
        lambda run_id, *, stage: None,
    )
    token = uuid4().hex[:8]
    with Session(test_engine) as session:
        org = _org(session, f"Harbour Club {token}")
        org_id = org.id
        session.commit()
    event = _enrich_event(org_id, "POST", body={"website": "https://ok.test/"})
    event["requestContext"]["authorizer"].pop("userSub")
    key_id = event["requestContext"]["authorizer"]["apiKeyId"]
    try:
        response = _call(event, "POST", "organizations", str(org_id))
        assert response["statusCode"] == 202
        run_id = json.loads(response["body"])["run"]["id"]
        with Session(test_engine) as session:
            run = session.get(OrgEnrichmentRun, run_id)
            assert run is not None
            assert run.requested_by == f"api-key:{key_id}"
    finally:
        _cleanup(test_engine, org_id)


def test_missing_website_is_422_and_a_bad_url_is_400(monkeypatch, test_engine) -> None:
    _patch_engines(monkeypatch, test_engine)
    token = uuid4().hex[:8]
    with Session(test_engine) as session:
        org = _org(session, f"Harbour Club {token}")
        org_id = org.id
        session.commit()
    try:
        missing = _enrich(org_id, "POST", body={})
        assert missing["statusCode"] == 422
        assert "website" in json.loads(missing["body"])["error"]
        bad = _enrich(org_id, "POST", body={"website": "not-a-url"})
        assert bad["statusCode"] == 400
    finally:
        _cleanup(test_engine, org_id)


def test_active_run_is_409(monkeypatch, test_engine) -> None:
    _patch_engines(monkeypatch, test_engine)
    queued: list[str] = []
    monkeypatch.setattr(
        "app.api.admin_enrichment.enqueue_enrichment",
        lambda run_id, *, stage: queued.append(stage),
    )
    token = uuid4().hex[:8]
    with Session(test_engine) as session:
        org = _org(session, f"Harbour Club {token}")
        session.add(
            OrgEnrichmentRun(
                org_id=org.id,
                status="queued",
                seed_url="https://ok.test/",
            )
        )
        org_id = org.id
        session.commit()
    try:
        response = _enrich(org_id, "POST", body={"website": "https://ok.test/"})
        assert response["statusCode"] == 409
        assert queued == []
    finally:
        _cleanup(test_engine, org_id)


def test_queue_failure_is_503_and_marks_the_run_failed(
    monkeypatch, test_engine
) -> None:
    _patch_engines(monkeypatch, test_engine)

    def fail_enqueue(run_id, *, stage: str) -> None:
        del run_id, stage
        raise RuntimeError("Enrichment queue is not configured")

    monkeypatch.setattr("app.api.admin_enrichment.enqueue_enrichment", fail_enqueue)
    token = uuid4().hex[:8]
    with Session(test_engine) as session:
        org = _org(session, f"Harbour Club {token}")
        org_id = org.id
        session.commit()
    try:
        response = _enrich(org_id, "POST", body={"website": "https://ok.test/"})
        assert response["statusCode"] == 503
        with Session(test_engine) as session:
            run = session.scalar(
                select(OrgEnrichmentRun).where(OrgEnrichmentRun.org_id == org_id)
            )
            assert run is not None
            assert run.status == "failed"
    finally:
        _cleanup(test_engine, org_id)


def test_full_access_dismisses_a_proposal(monkeypatch, test_engine) -> None:
    _patch_engines(monkeypatch, test_engine)
    token = uuid4().hex[:8]
    with Session(test_engine) as session:
        org = _org(session, f"Harbour Club {token}")
        run = OrgEnrichmentRun(
            org_id=org.id,
            status="ready",
            seed_url="https://ok.test/",
        )
        session.add(run)
        session.flush()
        proposal = OrgEnrichmentProposal(
            run_id=run.id,
            org_id=org.id,
            section="Organization",
            kind="update_organization",
            field="description",
            label="Description",
            proposed_value={"description": "Saturday art class for children."},
            confidence=Decimal("0.900"),
            evidence=[],
            proposed_hash=uuid4().hex,
        )
        session.add(proposal)
        session.flush()
        org_id = org.id
        proposal_id = proposal.id
        session.commit()
    try:
        response = _enrich(
            org_id,
            "POST",
            "/dismiss",
            body={"ids": [str(proposal_id)]},
        )
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["results"] == [{"id": str(proposal_id), "status": "dismissed"}]
        with Session(test_engine) as session:
            row = session.get(OrgEnrichmentProposal, proposal_id)
            assert row is not None
            assert row.status == "dismissed"
            assert row.decided_by is not None
            assert row.decided_by.startswith("api-key:")
    finally:
        _cleanup(test_engine, org_id)


def test_full_access_applies_a_proposal(monkeypatch, test_engine) -> None:
    _patch_engines(monkeypatch, test_engine)
    enqueued: list[str] = []
    monkeypatch.setattr(
        "app.services.data_quality.runs.enqueue_staged_run",
        lambda run_id: enqueued.append(run_id),
    )
    token = uuid4().hex[:8]
    with Session(test_engine) as session:
        org = _org(session, f"Harbour Club {token}")
        run = OrgEnrichmentRun(
            org_id=org.id,
            status="ready",
            seed_url="https://ok.test/",
        )
        session.add(run)
        session.flush()
        proposal = OrgEnrichmentProposal(
            run_id=run.id,
            org_id=org.id,
            section="Organization",
            kind="update_organization",
            field="description",
            label="Description",
            proposed_value={"description": "Saturday art class for children."},
            confidence=Decimal("0.900"),
            evidence=[],
            proposed_hash=uuid4().hex,
        )
        session.add(proposal)
        session.flush()
        org_id = org.id
        proposal_id = proposal.id
        session.commit()
    try:
        response = _enrich(
            org_id,
            "POST",
            "/apply",
            body={"ids": [str(proposal_id)]},
        )
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["results"] == [{"id": str(proposal_id), "status": "applied"}]
        if body.get("data_quality_run_id"):
            assert enqueued == [body["data_quality_run_id"]]
        else:
            assert enqueued == []
        with Session(test_engine) as session:
            saved = session.get(Organization, org_id)
            assert saved is not None
            assert saved.description == "Saturday art class for children."
    finally:
        with Session(test_engine) as session:
            session.execute(delete(AuditLog).where(AuditLog.record_id == str(org_id)))
            session.execute(
                delete(DataQualityRun).where(
                    DataQualityRun.scope.contains({"organization_ids": [str(org_id)]})
                )
            )
            session.commit()
        _cleanup(test_engine, org_id)


def test_full_access_reads_and_updates_enrichment_settings(
    monkeypatch, test_engine
) -> None:
    _patch_engines(monkeypatch, test_engine)
    pages, limit = _settings_snapshot(test_engine)
    actor = ""
    try:
        read = _call(
            _event("GET", "/v1/partner/enrichment-settings"),
            "GET",
            "enrichment-settings",
            None,
        )
        assert read["statusCode"] == 200
        assert "max_pages" in json.loads(read["body"])

        put = _event(
            "PUT",
            "/v1/partner/enrichment-settings",
            body={"max_pages": 8},
        )
        actor = put["requestContext"]["authorizer"]["userSub"]
        updated = _call(put, "PUT", "enrichment-settings", None)
        assert updated["statusCode"] == 200
        assert json.loads(updated["body"])["max_pages"] == 8
        with Session(test_engine) as session:
            audit = session.scalar(
                select(AuditLog)
                .where(
                    AuditLog.table_name == "org_enrichment_settings",
                    AuditLog.user_id == actor,
                )
                .order_by(AuditLog.timestamp.desc())
            )
            assert audit is not None
            assert audit.action == "UPDATE"
            assert audit.new_values == {"max_pages": 8}

        invalid = _call(
            _event(
                "PUT",
                "/v1/partner/enrichment-settings",
                body={"max_pages": 21},
            ),
            "PUT",
            "enrichment-settings",
            None,
        )
        assert invalid["statusCode"] == 400
        with Session(test_engine) as session:
            assert load_settings(session).max_pages == 8
    finally:
        _restore_settings(test_engine, pages, limit)
        if actor:
            with Session(test_engine) as session:
                session.execute(
                    delete(AuditLog).where(
                        AuditLog.table_name == "org_enrichment_settings",
                        AuditLog.user_id == actor,
                    )
                )
                session.commit()
