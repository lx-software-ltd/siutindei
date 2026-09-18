"""Admin listing status, place_id, and import-job lookup tests."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import select

from app.api.admin_crud import _lookup_organization
from app.api.admin_imports_jobs import store_import_job
from app.api.admin_resource_organization import (
    _serialize_organization,
    _update_organization,
)
from app.db.models import Organization
from app.db.repositories import OrganizationRepository


def test_patch_status_and_place_id(db_session, sample_organization) -> None:
    repo = OrganizationRepository(db_session)
    updated = _update_organization(
        repo,
        sample_organization,
        {
            "place_id": "ChIJ-owner-attach",
            "status": "closed_temporarily",
            "reason": "renovation",
        },
    )
    repo.update(updated)
    db_session.flush()
    db_session.refresh(sample_organization)
    assert sample_organization.place_id == "ChIJ-owner-attach"
    assert sample_organization.status == "closed_temporarily"
    assert sample_organization.status_source == "owner"
    assert sample_organization.status_changed_at is not None
    payload = _serialize_organization(sample_organization)
    assert payload["place_id"] == "ChIJ-owner-attach"
    assert payload["status"] == "closed_temporarily"


def test_lookup_organization_by_place_id_and_source_id(
    db_session,
    sample_organization,
) -> None:
    sample_organization.place_id = "ChIJ-lookup"
    sample_organization.source_id = "lcsd-99"
    db_session.flush()

    place_event = {"queryStringParameters": {"place_id": "ChIJ-lookup"}}
    response = _lookup_organization(db_session, place_event)
    assert response is not None
    assert response["statusCode"] == 200
    body = __import__("json").loads(response["body"])
    assert body["items"][0]["id"] == str(sample_organization.id)

    source_event = {"queryStringParameters": {"source_id": "lcsd-99"}}
    response = _lookup_organization(db_session, source_event)
    body = __import__("json").loads(response["body"])
    assert body["items"][0]["source_id"] == "lcsd-99"

    missing = _lookup_organization(
        db_session,
        {"queryStringParameters": {"place_id": "missing"}},
    )
    body = __import__("json").loads(missing["body"])
    assert body["items"] == []


def test_get_import_job_returns_stored_result(db_session) -> None:
    from app.api.admin_imports import _handle_get_import_job

    job = store_import_job(
        db_session,
        "admin/imports/progress.json",
        dry_run=False,
        summary={"organizations": {"created": 1, "failed": 0}},
        results=[{"type": "organizations", "key": "Park", "status": "created"}],
        file_warnings=["name truncated"],
    )
    db_session.flush()

    with patch("app.api.admin_imports.get_engine", return_value=db_session.get_bind()):
        with patch("app.api.admin_imports.Session", return_value=db_session):
            # Session() used as context manager; reuse db_session.
            class _Ctx:
                def __enter__(self):
                    return db_session

                def __exit__(self, *args):
                    return False

            with patch("app.api.admin_imports.Session", return_value=_Ctx()):
                response = _handle_get_import_job({}, str(job.id))
    assert response["statusCode"] == 200
    body = __import__("json").loads(response["body"])
    assert body["object_key"] == "admin/imports/progress.json"
    assert body["results"][0]["key"] == "Park"


def test_blank_zh_fields_do_not_fail(db_session) -> None:
    from app.api.admin_imports_importer import process_import_payload

    summary, results = process_import_payload(
        db_session,
        {
            "organizations": [
                {
                    "name": f"Blank Zh {uuid4()}",
                    "name_zh": "",
                    "description_zh": "",
                    "manager_id": "00000000-0000-0000-0000-000000000077",
                }
            ]
        },
        [],
        allow_org_updates=True,
    )
    assert results[0]["status"] == "created"
    assert summary["organizations"]["failed"] == 0
    org = db_session.execute(
        select(Organization).where(
            Organization.manager_id == "00000000-0000-0000-0000-000000000077"
        )
    ).scalar_one()
    assert org.name_translations == {} or "zh-HK" not in org.name_translations
