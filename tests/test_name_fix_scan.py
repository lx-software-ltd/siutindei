"""Name-fix sweep scope and stale-proposal cleanup."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from psycopg.types.range import Range

from app.db.models import Activity, NameFixProposal, Organization
from app.exceptions import ValidationError
from app.services.name_fix_scan import scan_names


def _dirty_org(db_session, name: str, review_status: str = "pending_review"):
    org = Organization(
        name=name,
        manager_id="00000000-0000-0000-0000-000000000001",
        review_status=review_status,
    )
    db_session.add(org)
    db_session.flush()
    return org


def test_sweep_clears_stale_pending(db_session) -> None:
    org = _dirty_org(db_session, "Harbour Club")
    db_session.add(
        NameFixProposal(
            entity_type="organization",
            entity_id=org.id,
            current_value="HARBOUR CLUB",
            proposed_value="Harbour Club",
            rules=["title_case"],
        )
    )
    db_session.flush()
    result = scan_names(db_session, review_scope="pending_review")
    assert result["cleared"] == 1
    assert (
        db_session.scalars(
            select(NameFixProposal).where(NameFixProposal.entity_id == org.id)
        ).first()
        is None
    )


def test_sweep_pending_review_skips_approved_orgs(db_session) -> None:
    pending = _dirty_org(db_session, "HARBOUR CLUB", "pending_review")
    _dirty_org(db_session, "YWCA HARBOUR", "approved")
    result = scan_names(db_session, review_scope="pending_review")
    assert result["created"] == 1
    rows = list(db_session.scalars(select(NameFixProposal)).all())
    assert len(rows) == 1
    assert rows[0].entity_id == pending.id


def test_sweep_all_includes_approved_orgs(db_session) -> None:
    _dirty_org(db_session, "HARBOUR CLUB", "pending_review")
    _dirty_org(db_session, "YWCA HARBOUR", "approved")
    result = scan_names(db_session, review_scope="all")
    assert result["created"] == 2


def test_sweep_all_includes_approved_activity_names(
    db_session, sample_activity_category
) -> None:
    org = _dirty_org(db_session, "Clean Org Name", "approved")
    db_session.add(
        Activity(
            org_id=org.id,
            category_id=sample_activity_category.id,
            name="SWIM CLASS",
            age_range=Range(5, 12, bounds="[]"),
        )
    )
    db_session.flush()
    pending = scan_names(
        db_session, entity_type="activity", review_scope="pending_review"
    )
    assert pending["created"] == 0
    sweep = scan_names(db_session, entity_type="activity", review_scope="all")
    assert sweep["created"] == 1


def test_scan_rejects_unknown_review_scope(db_session) -> None:
    with pytest.raises(ValidationError) as exc_info:
        scan_names(db_session, review_scope="nope")
    assert exc_info.value.field == "review_scope"
