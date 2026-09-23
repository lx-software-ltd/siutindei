"""Organization review gate, import tagging, and bulk release."""

from __future__ import annotations

from uuid import uuid4

from app.api.admin_imports_importer import process_import_payload
from app.api.admin_org_review_actions import (
    ReviewBlockedError,
    _apply_decision,
    _apply_fields,
)
from app.api.admin_resource_organization import _create_organization
from app.db.models import Organization
from app.db.queries import ActivitySearchFilters, build_search_query
from app.db.repositories import OrganizationRepository
from app.services.org_review import collect_issues
from sqlalchemy import select


def test_collect_issues_flags_blockers() -> None:
    organization = Organization(
        id=uuid4(),
        name="Bare Org",
        manager_id="manager-1",
        description=None,
    )
    issues = collect_issues(organization, [], [], {}, {})
    codes = {issue.code for issue in issues}
    assert "missing_description" in codes
    assert "no_locations" in codes
    assert "no_activities" in codes
    assert any(issue.severity == "blocker" for issue in issues)


def test_import_create_is_pending_and_ignores_review_status(db_session) -> None:
    payload = {
        "organizations": [
            {
                "name": "Imported Pending Org",
                "manager_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "review_status": "approved",
                "description": "A class.",
            }
        ]
    }
    _summary, results = process_import_payload(db_session, payload, [])
    assert results[0]["status"] == "created"
    assert any(
        "review_status is ignored" in warning for warning in results[0]["warnings"]
    )
    org = db_session.execute(
        select(Organization).where(Organization.name == "Imported Pending Org")
    ).scalar_one()
    assert org.review_status == "pending_review"
    assert org.last_imported_at is not None


def test_import_update_keeps_approved_review(db_session, sample_organization) -> None:
    sample_organization.review_status = "approved"
    db_session.flush()
    payload = {
        "organizations": [
            {
                "name": sample_organization.name,
                "manager_id": sample_organization.manager_id,
                "description": "Updated copy",
            }
        ]
    }
    _summary, results = process_import_payload(
        db_session,
        payload,
        [],
        allow_org_updates=True,
    )
    assert results[0]["status"] == "updated"
    db_session.refresh(sample_organization)
    assert sample_organization.review_status == "approved"
    assert sample_organization.last_imported_at is not None


def test_admin_create_is_approved(db_session) -> None:
    repo = OrganizationRepository(db_session)
    created = _create_organization(
        repo,
        {
            "name": "Console Org",
            "manager_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
        },
    )
    assert created.review_status == "approved"


def test_approve_blocks_until_forced(db_session, sample_organization) -> None:
    sample_organization.review_status = "pending_review"
    db_session.flush()
    try:
        _apply_decision(
            db_session,
            sample_organization,
            "approve",
            force=False,
            notes=None,
            status=None,
            reviewer_sub="admin-sub",
            notes_provided=False,
        )
        raise AssertionError("expected blockers")
    except ReviewBlockedError as exc:
        assert exc.issues
    _apply_decision(
        db_session,
        sample_organization,
        "approve",
        force=True,
        notes="ship it",
        status=None,
        reviewer_sub="admin-sub",
        notes_provided=True,
    )
    assert sample_organization.review_status == "approved"
    assert sample_organization.reviewed_by == "admin-sub"
    assert sample_organization.review_notes == "ship it"


def test_bulk_fields_sets_email(db_session, sample_organization) -> None:
    repo = OrganizationRepository(db_session)
    _apply_fields(
        repo,
        sample_organization,
        {"email": "studio@example.com", "review_notes": "called them"},
    )
    assert sample_organization.email == "studio@example.com"
    assert sample_organization.review_notes == "called them"


def test_search_gate_is_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("ORG_REVIEW_GATE_ENABLED", raising=False)
    closed = str(build_search_query(ActivitySearchFilters()).whereclause)
    assert "review_status" not in closed
    monkeypatch.setenv("ORG_REVIEW_GATE_ENABLED", "true")
    opened = str(build_search_query(ActivitySearchFilters()).whereclause)
    assert "review_status" in opened
