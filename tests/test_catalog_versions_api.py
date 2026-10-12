"""Catalog history list and forget."""

from uuid import uuid4

import pytest
from app.api.admin_versions import _list, handle_versions
from app.db.models import CatalogVersion
from app.exceptions import ValidationError
from app.services.catalog_version_match import forget_removed_baseline
from sqlalchemy.orm import Session


def _event(**params: str) -> dict:
    return {"queryStringParameters": params}


def _version(
    entity_id: object,
    version: int,
    *,
    org_id: object | None = None,
    entity_type: str = "activity",
    snapshot: dict | None = None,
    reason: str | None = None,
) -> CatalogVersion:
    return CatalogVersion(
        entity_type=entity_type,
        entity_id=entity_id,
        org_id=org_id,
        version=version,
        action="created" if version == 1 else "updated",
        snapshot=snapshot or {"name": f"Version {version}"},
        txid=version,
        reason=reason,
    )


def test_entity_history_pages_by_version(db_session: Session) -> None:
    entity_id = uuid4()
    for version in (1, 2, 3):
        db_session.add(_version(entity_id, version))
    db_session.flush()

    first = _list(
        db_session,
        _event(entity_type="activity", entity_id=str(entity_id), limit="2"),
    )
    assert [item["version"] for item in first["items"]] == [3, 2]
    assert first["next_cursor"].startswith("v|2|")

    second = _list(
        db_session,
        _event(
            entity_type="activity",
            entity_id=str(entity_id),
            limit="2",
            cursor=first["next_cursor"],
        ),
    )
    assert [item["version"] for item in second["items"]] == [1]
    assert second["next_cursor"] is None


def test_blocking_list_requires_an_organization(db_session: Session) -> None:
    with pytest.raises(ValidationError, match="org_id"):
        _list(db_session, _event(blocking="true"))


def test_forget_removed_baseline_strips_contacts(db_session: Session) -> None:
    entity_id = uuid4()
    row = _version(
        entity_id,
        1,
        snapshot={"name": "Gone", "email": "gone@example.com", "phone_number": "555"},
    )
    db_session.add(row)
    db_session.flush()

    forget_removed_baseline(db_session, "activity", entity_id)
    db_session.flush()
    db_session.refresh(row)

    assert row.reason == "forgotten"
    assert "email" not in (row.snapshot or {})
    assert "phone_number" not in (row.snapshot or {})
    assert row.snapshot["name"] == "Gone"


def test_forget_leaves_a_merged_baseline(db_session: Session) -> None:
    entity_id = uuid4()
    created = _version(
        entity_id,
        1,
        entity_type="organization",
        org_id=entity_id,
        snapshot={"name": "Merged", "email": "gone@example.com"},
    )
    deleted = _version(
        entity_id,
        2,
        entity_type="organization",
        org_id=entity_id,
        snapshot={"name": "Merged", "email": "gone@example.com"},
        reason="merged",
    )
    deleted.action = "deleted"
    db_session.add_all([created, deleted])
    db_session.flush()

    forget_removed_baseline(db_session, "organization", entity_id)
    db_session.flush()
    db_session.refresh(created)
    db_session.refresh(deleted)

    assert created.reason is None
    assert deleted.reason == "merged"
    assert "email" not in (created.snapshot or {})
    assert "email" not in (deleted.snapshot or {})


def test_forget_route_rejects_get() -> None:
    response = handle_versions({}, "GET", str(uuid4()), "forget")
    assert response["statusCode"] == 405
