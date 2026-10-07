"""Duplicate groups on the folded organization name."""

from __future__ import annotations

from uuid import UUID, uuid4

from app.db.models import AuditLog, Organization
from app.services.org_duplicates import (
    dismiss_pairs,
    list_duplicate_groups,
    orgs_with_duplicate_signals,
)
from sqlalchemy import select


def _org(db_session, name: str) -> Organization:
    org = Organization(
        name=name,
        manager_id="00000000-0000-0000-0000-0000000000bb",
        review_status="pending_review",
    )
    db_session.add(org)
    db_session.flush()
    return org


def test_limited_suffix_groups_with_the_short_name(db_session) -> None:
    token = uuid4().hex[:8]
    short = _org(db_session, f"Harbour Club {token}")
    limited = _org(db_session, f"Harbour Club {token} Limited")
    page = list_duplicate_groups(db_session, query=token)
    ids = {org["id"] for group in page["items"] for org in group["organizations"]}
    assert str(short.id) in ids
    assert str(limited.id) in ids


def test_blank_socials_do_not_group(db_session) -> None:
    left = f"Alpha {uuid4().hex[:8]} Pottery"
    _org(db_session, left)
    _org(db_session, f"Zebra {uuid4().hex[:8]} Kites")
    page = list_duplicate_groups(db_session, query=left)
    assert page["items"] == []


def test_dismissed_pair_is_not_grouped(db_session) -> None:
    token = uuid4().hex[:8]
    short = _org(db_session, f"Harbour Club {token}")
    limited = _org(db_session, f"Harbour Club {token} Limited")
    dismiss_pairs(db_session, [UUID(str(short.id)), UUID(str(limited.id))], "admin")
    page = list_duplicate_groups(db_session, query=token)
    assert page["items"] == []
    audit = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "DISMISS_DUPLICATE")
    ).one()
    assert str(short.id) in audit.new_values["org_ids"]


def test_dismissed_pair_is_not_joined_through_a_third_org(db_session) -> None:
    token = uuid4().hex[:8]
    left = _org(db_session, f"Harbour Club {token}")
    right = _org(db_session, f"Harbour Club {token} Limited")
    _org(db_session, f"Harbour Club {token} Ltd")
    dismiss_pairs(db_session, [UUID(str(left.id)), UUID(str(right.id))], "admin")
    page = list_duplicate_groups(db_session, query=token)
    pair = {str(left.id), str(right.id)}
    for group in page["items"]:
        ids = {org["id"] for org in group["organizations"]}
        assert not pair <= ids


def test_name_key_duplicate_signal_skips_dismissals(db_session) -> None:
    token = uuid4().hex[:8]
    short = _org(db_session, f"Harbour Club {token}")
    limited = _org(db_session, f"Harbour Club {token} Limited")
    flagged = orgs_with_duplicate_signals(db_session, [short])
    assert str(short.id) in flagged
    dismiss_pairs(db_session, [UUID(str(short.id)), UUID(str(limited.id))], "admin")
    flagged = orgs_with_duplicate_signals(db_session, [short])
    assert str(short.id) not in flagged
