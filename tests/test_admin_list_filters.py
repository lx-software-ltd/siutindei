"""Catalog list filters and organization-scoped child lists."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.api.admin_list_filters import (
    OrganizationListFilters,
    cognito_email_prefix_filter,
    list_organizations,
    parse_organization_list_filters,
    resolve_list_org_scope,
)
from app.db.models import Location, Organization
from app.exceptions import ValidationError


def _org(name: str, **kwargs) -> Organization:
    return Organization(
        name=name,
        manager_id="00000000-0000-0000-0000-000000000001",
        **kwargs,
    )


def test_list_organizations_filters_name_review_and_scope(db_session) -> None:
    pending = _org("Harbour Studio", review_status="pending_review", source="lcsd")
    live = _org("Harbour Live", review_status="approved", source="places")
    other = _org("Inland Club", review_status="pending_review", source="lcsd")
    db_session.add_all([pending, live, other])
    db_session.flush()

    matches = list_organizations(
        db_session,
        None,
        OrganizationListFilters(query="harbour", review_status="pending_review"),
        limit=20,
        cursor=None,
    )
    assert [item.name for item in matches] == ["Harbour Studio"]

    scoped = list_organizations(
        db_session,
        {str(live.id)},
        OrganizationListFilters(),
        limit=20,
        cursor=None,
    )
    assert [item.id for item in scoped] == [live.id]


def test_parse_organization_filters_rejects_unknown_review_status() -> None:
    with pytest.raises(ValidationError) as exc_info:
        parse_organization_list_filters(
            {"queryStringParameters": {"review_status": "published"}}
        )
    assert exc_info.value.field == "review_status"


def test_org_scope_rejects_a_manager_looking_outside_their_orgs() -> None:
    foreign = str(uuid4())
    scope, denied = resolve_list_org_scope(
        {"queryStringParameters": {"org_id": foreign}},
        managed_org_ids={str(uuid4())},
    )
    assert scope is None
    assert denied is not None
    assert denied["statusCode"] == 403


def test_org_scope_narrows_an_admin_list() -> None:
    org_id = str(uuid4())
    scope, denied = resolve_list_org_scope(
        {"queryStringParameters": {"org_id": org_id}},
        managed_org_ids=None,
    )
    assert denied is None
    assert scope == {org_id}


def test_child_list_scope_limits_locations(db_session, sample_geographic_area) -> None:
    from app.api.admin_crud import _get_all_filtered_by_org
    from app.api.admin_resources import _RESOURCE_CONFIG

    first = _org("First Org")
    second = _org("Second Org")
    db_session.add_all([first, second])
    db_session.flush()
    db_session.add(
        Location(
            org_id=first.id,
            area_id=sample_geographic_area.id,
            address="1 First Street",
        )
    )
    db_session.add(
        Location(
            org_id=second.id,
            area_id=sample_geographic_area.id,
            address="2 Second Street",
        )
    )
    db_session.flush()

    rows = _get_all_filtered_by_org(
        db_session,
        _RESOURCE_CONFIG["locations"],
        {str(first.id)},
        limit=10,
        cursor=None,
    )
    assert [row.address for row in rows] == ["1 First Street"]


def test_cognito_email_prefix_filter() -> None:
    assert cognito_email_prefix_filter("  ") is None
    assert cognito_email_prefix_filter("ada@example.com") == (
        'email ^= "ada@example.com"'
    )
    with pytest.raises(ValidationError):
        cognito_email_prefix_filter("ada example")
