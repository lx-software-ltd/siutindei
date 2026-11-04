"""Full-access crud partner keys can merge organizations."""

from __future__ import annotations

import json
from uuid import uuid4

from app.api.admin import _handle_partner_routes
from app.db.models import Organization, OrganizationMerge
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tests.test_partner_routes import _partner_event

_MANAGER = "00000000-0000-0000-0000-000000000001"


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
) -> dict:
    event = _partner_event(
        "POST",
        "/v1/partner/org-duplicates/merge",
        scope,
        org_id,
    )
    body: dict = {
        "survivor_id": str(survivor_id),
        "source_ids": [str(source_id)],
    }
    if dry_run:
        body["dry_run"] = True
    event["body"] = json.dumps(body)
    return event


def test_org_scoped_crud_key_cannot_merge() -> None:
    event = _merge_event(uuid4(), uuid4(), org_id=str(uuid4()))
    response = _handle_partner_routes(event, "POST", "org-duplicates", "merge")
    assert response["statusCode"] == 403
    assert "limited to one organization" in json.loads(response["body"])["error"]


def test_read_key_cannot_merge() -> None:
    event = _merge_event(uuid4(), uuid4(), scope="read")
    response = _handle_partner_routes(event, "POST", "org-duplicates", "merge")
    assert response["statusCode"] == 403
    assert "write access" in json.loads(response["body"])["error"]


def test_unknown_org_duplicates_path_is_404() -> None:
    event = _partner_event("GET", "/v1/partner/org-duplicates", "crud", "")
    response = _handle_partner_routes(event, "GET", "org-duplicates", None)
    assert response["statusCode"] == 404

    dismiss = _partner_event("POST", "/v1/partner/org-duplicates/dismiss", "crud", "")
    response = _handle_partner_routes(dismiss, "POST", "org-duplicates", "dismiss")
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
        preview = _handle_partner_routes(
            _merge_event(survivor_id, source_id, dry_run=True),
            "POST",
            "org-duplicates",
            "merge",
        )
        assert preview["statusCode"] == 200
        body = json.loads(preview["body"])
        assert body["dry_run"] is True
        assert body["survivor_id"] == str(survivor_id)
        assert str(source_id) in body["source_ids"]
        with Session(test_engine) as session:
            assert session.get(Organization, source_id) is not None

        merged = _handle_partner_routes(
            _merge_event(survivor_id, source_id),
            "POST",
            "org-duplicates",
            "merge",
        )
        assert merged["statusCode"] == 201
        result = json.loads(merged["body"])
        assert result["dry_run"] is False
        assert result["survivor_id"] == str(survivor_id)
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
    finally:
        _cleanup(test_engine, survivor_id, source_id)
