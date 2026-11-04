"""Full-access crud partner keys can merge organizations."""

from __future__ import annotations

import json
from uuid import uuid4

from app.api.admin import _handle_partner_routes
from app.db.models import ApiKey, AuditLog, Organization, OrganizationMerge
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from tests.test_partner_routes import _partner_event

_MANAGER = "00000000-0000-0000-0000-000000000001"
_MERGE_RESOURCE = "organization-merges"


def _patch_engines(monkeypatch, engine) -> None:
    monkeypatch.setattr("app.api.admin_org_duplicates.get_engine", lambda: engine)


def _org(session: Session, name: str, **kwargs) -> Organization:
    org = Organization(
        name=name,
        manager_id=_MANAGER,
        review_status=kwargs.pop("review_status", "pending_review"),
        **kwargs,
    )
    session.add(org)
    session.flush()
    return org


def _cleanup(engine, *ids) -> None:
    with Session(engine) as session:
        session.execute(delete(ApiKey).where(ApiKey.org_id.in_(ids)))
        session.execute(
            delete(OrganizationMerge).where(
                OrganizationMerge.merged_org_id.in_(ids)
                | OrganizationMerge.survivor_org_id.in_(ids)
            )
        )
        for row_id in ids:
            row = session.get(Organization, row_id)
            if row is not None:
                session.delete(row)
        session.commit()


def _merge_event(
    survivor_id,
    source_id,
    *,
    scope: str = "crud",
    org_id: str = "",
    dry_run: bool = False,
    body: dict | None = None,
) -> dict:
    event = _partner_event(
        "POST",
        "/v1/partner/organization-merges",
        scope,
        org_id,
    )
    payload = {
        "survivor_id": str(survivor_id),
        "source_ids": [str(source_id)],
    }
    if dry_run:
        payload["dry_run"] = True
    if body is not None:
        payload = body
    event["body"] = json.dumps(payload)
    return event


def _post(event: dict) -> dict:
    return _handle_partner_routes(event, "POST", _MERGE_RESOURCE, None)


def test_org_scoped_crud_key_cannot_merge() -> None:
    event = _merge_event(uuid4(), uuid4(), org_id=str(uuid4()))
    response = _post(event)
    assert response["statusCode"] == 403
    assert "limited to one organization" in json.loads(response["body"])["error"]


def test_org_scoped_key_cannot_merge_its_own_survivor(monkeypatch, test_engine) -> None:
    _patch_engines(monkeypatch, test_engine)
    token = uuid4().hex[:8]
    with Session(test_engine) as session:
        survivor = _org(session, f"Harbour Club {token}")
        source = _org(session, f"Harbour Club {token} Limited")
        survivor_id = survivor.id
        source_id = source.id
        session.commit()
    try:
        response = _post(_merge_event(survivor_id, source_id, org_id=str(survivor_id)))
        assert response["statusCode"] == 403
        with Session(test_engine) as session:
            assert session.get(Organization, survivor_id) is not None
            assert session.get(Organization, source_id) is not None
    finally:
        _cleanup(test_engine, survivor_id, source_id)


def test_read_key_cannot_merge() -> None:
    event = _merge_event(uuid4(), uuid4(), scope="read")
    response = _post(event)
    assert response["statusCode"] == 403
    assert "write access" in json.loads(response["body"])["error"]


def test_duplicate_routes_and_the_old_merge_path_are_404() -> None:
    event = _partner_event("GET", "/v1/partner/organization-merges", "crud", "")
    response = _handle_partner_routes(event, "GET", _MERGE_RESOURCE, None)
    assert response["statusCode"] == 404

    old = _partner_event("POST", "/v1/partner/org-duplicates/merge", "crud", "")
    response = _handle_partner_routes(old, "POST", "org-duplicates", "merge")
    assert response["statusCode"] == 404

    dismiss = _partner_event("POST", "/v1/partner/org-duplicates/dismiss", "crud", "")
    response = _handle_partner_routes(dismiss, "POST", "org-duplicates", "dismiss")
    assert response["statusCode"] == 404


def test_merge_rejects_a_bad_id_and_a_survivor_that_is_also_a_source(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.api.admin_org_duplicates.get_engine",
        lambda: (_ for _ in ()).throw(AssertionError("database")),
    )
    bad = _merge_event(
        uuid4(),
        uuid4(),
        body={"survivor_id": "not-a-uuid", "source_ids": [str(uuid4())]},
    )
    response = _post(bad)
    assert response["statusCode"] == 400

    same = str(uuid4())
    overlap = _merge_event(
        same,
        same,
        body={"survivor_id": same, "source_ids": [same]},
    )
    response = _post(overlap)
    assert response["statusCode"] == 400
    assert "survivor_id is also a source" in json.loads(response["body"])["error"]


def test_merge_returns_404_for_an_unknown_organization(
    monkeypatch, test_engine
) -> None:
    _patch_engines(monkeypatch, test_engine)
    response = _post(_merge_event(uuid4(), uuid4()))
    assert response["statusCode"] == 404


def test_full_access_crud_merges_and_dry_run_does_not(monkeypatch, test_engine) -> None:
    _patch_engines(monkeypatch, test_engine)
    token = uuid4().hex[:8]
    with Session(test_engine) as session:
        survivor = _org(session, f"Harbour Club {token}")
        source = _org(
            session,
            f"Harbour Club {token} Limited",
            phone_number="21234567",
        )
        survivor_id = survivor.id
        source_id = source.id
        session.commit()
    try:
        preview = _post(_merge_event(survivor_id, source_id, dry_run=True))
        assert preview["statusCode"] == 200
        body = json.loads(preview["body"])
        assert body["dry_run"] is True
        assert body["survivor_id"] == str(survivor_id)
        assert str(source_id) in body["source_ids"]
        with Session(test_engine) as session:
            assert session.get(Organization, source_id) is not None

        merged = _post(_merge_event(survivor_id, source_id))
        assert merged["statusCode"] == 201
        result = json.loads(merged["body"])
        assert result["dry_run"] is False
        assert result["survivor_id"] == str(survivor_id)
        assert "already_merged" not in result
        with Session(test_engine) as session:
            kept = session.get(Organization, survivor_id)
            assert kept is not None
            assert kept.phone_number == "21234567"
            assert session.get(Organization, source_id) is None
            forwarding = session.scalars(
                select(OrganizationMerge).where(
                    OrganizationMerge.merged_org_id == source_id
                )
            ).one()
            assert forwarding.survivor_org_id == survivor_id
            assert forwarding.merged_by.startswith("api-key:")
            audit = session.scalars(
                select(AuditLog).where(
                    AuditLog.action == "MERGE",
                    AuditLog.record_id == str(survivor_id),
                )
            ).one()
            assert audit.user_id == forwarding.merged_by
    finally:
        _cleanup(test_engine, survivor_id, source_id)


def test_repeat_merge_returns_200_without_a_second_write(
    monkeypatch, test_engine
) -> None:
    _patch_engines(monkeypatch, test_engine)
    token = uuid4().hex[:8]
    with Session(test_engine) as session:
        survivor = _org(session, f"Harbour Club {token}")
        source = _org(session, f"Harbour Club {token} Limited")
        survivor_id = survivor.id
        source_id = source.id
        session.commit()
    try:
        first = _post(_merge_event(survivor_id, source_id))
        assert first["statusCode"] == 201
        again = _post(_merge_event(survivor_id, source_id))
        assert again["statusCode"] == 200
        body = json.loads(again["body"])
        assert body["already_merged"] is True
        assert body["dry_run"] is False
        with Session(test_engine) as session:
            count = session.scalar(
                select(func.count())
                .select_from(OrganizationMerge)
                .where(OrganizationMerge.merged_org_id == source_id)
            )
            assert count == 1
            audits = session.scalars(
                select(AuditLog).where(
                    AuditLog.action == "MERGE",
                    AuditLog.record_id == str(survivor_id),
                )
            ).all()
            assert len(audits) == 1
    finally:
        _cleanup(test_engine, survivor_id, source_id)


def test_merge_moves_an_org_scoped_api_key(monkeypatch, test_engine) -> None:
    _patch_engines(monkeypatch, test_engine)
    token = uuid4().hex[:8]
    key_id = uuid4()
    with Session(test_engine) as session:
        survivor = _org(session, f"Harbour Club {token}")
        source = _org(session, f"Harbour Club {token} Limited")
        session.add(
            ApiKey(
                id=key_id,
                name=f"Harbour import {token}",
                key_prefix="sd_test",
                key_hash=uuid4().hex + uuid4().hex,
                scope="read",
                org_id=source.id,
            )
        )
        survivor_id = survivor.id
        source_id = source.id
        session.commit()
    try:
        response = _post(_merge_event(survivor_id, source_id))
        assert response["statusCode"] == 201
        with Session(test_engine) as session:
            key = session.get(ApiKey, key_id)
            assert key is not None
            assert key.org_id == survivor_id
    finally:
        _cleanup(test_engine, survivor_id, source_id)


def test_missing_user_sub_still_records_the_api_key(monkeypatch, test_engine) -> None:
    _patch_engines(monkeypatch, test_engine)
    token = uuid4().hex[:8]
    with Session(test_engine) as session:
        survivor = _org(session, f"Harbour Club {token}")
        source = _org(session, f"Harbour Club {token} Limited")
        survivor_id = survivor.id
        source_id = source.id
        session.commit()
    try:
        event = _merge_event(survivor_id, source_id)
        key_id = event["requestContext"]["authorizer"]["apiKeyId"]
        event["requestContext"]["authorizer"].pop("userSub")
        response = _post(event)
        assert response["statusCode"] == 201
        with Session(test_engine) as session:
            forwarding = session.scalars(
                select(OrganizationMerge).where(
                    OrganizationMerge.merged_org_id == source_id
                )
            ).one()
            assert forwarding.merged_by == f"api-key:{key_id}"
            audit = session.scalars(
                select(AuditLog).where(
                    AuditLog.action == "MERGE",
                    AuditLog.record_id == str(survivor_id),
                )
            ).one()
            assert audit.user_id == f"api-key:{key_id}"
    finally:
        _cleanup(test_engine, survivor_id, source_id)


def test_merge_rejects_a_source_merged_into_someone_else(
    monkeypatch, test_engine
) -> None:
    _patch_engines(monkeypatch, test_engine)
    token = uuid4().hex[:8]
    with Session(test_engine) as session:
        survivor = _org(session, f"Harbour Club {token}")
        other = _org(session, f"Other Club {token}")
        source = _org(session, f"Harbour Club {token} Limited")
        survivor_id = survivor.id
        other_id = other.id
        source_id = source.id
        session.commit()
    try:
        moved = _post(_merge_event(other_id, source_id))
        assert moved["statusCode"] == 201
        rejected = _post(_merge_event(survivor_id, source_id))
        assert rejected["statusCode"] == 400
        assert "another organization" in json.loads(rejected["body"])["error"]
    finally:
        _cleanup(test_engine, survivor_id, other_id, source_id)
