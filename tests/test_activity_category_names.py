"""Sibling category names stay unique even when only the case differs."""

from uuid import uuid4

import pytest
from app.api.admin_resource_activity_category import _update_activity_category
from app.db.repositories.activity_category import ActivityCategoryRepository
from app.exceptions import ValidationError
from app.services.activity_categories import create_activity_category


def test_create_rejects_a_case_variant_under_the_same_parent(db_session):
    repo = ActivityCategoryRepository(db_session)
    parent = create_activity_category(repo, {"name": f"Sport {uuid4()}"})
    db_session.add(parent)
    db_session.flush()
    child = create_activity_category(
        repo,
        {"name": "Kayaking", "parent_id": str(parent.id)},
    )
    db_session.add(child)
    db_session.flush()

    with pytest.raises(ValidationError, match="already exists under that parent"):
        create_activity_category(
            repo,
            {"name": " kayaking ", "parent_id": str(parent.id)},
        )


def test_the_same_name_is_allowed_under_a_different_parent(db_session):
    repo = ActivityCategoryRepository(db_session)
    sport = create_activity_category(repo, {"name": f"Sport {uuid4()}"})
    arts = create_activity_category(repo, {"name": f"Arts {uuid4()}"})
    db_session.add_all([sport, arts])
    db_session.flush()
    db_session.add(
        create_activity_category(
            repo,
            {"name": "Kayaking", "parent_id": str(sport.id)},
        )
    )
    db_session.flush()

    other = create_activity_category(
        repo,
        {"name": "Kayaking", "parent_id": str(arts.id)},
    )
    assert other.name == "Kayaking"


def test_rename_rejects_a_sibling_name(db_session):
    repo = ActivityCategoryRepository(db_session)
    parent = create_activity_category(repo, {"name": f"Sport {uuid4()}"})
    db_session.add(parent)
    db_session.flush()
    kayaking = create_activity_category(
        repo,
        {"name": "Kayaking", "parent_id": str(parent.id)},
    )
    canoeing = create_activity_category(
        repo,
        {"name": "Canoeing", "parent_id": str(parent.id)},
    )
    db_session.add_all([kayaking, canoeing])
    db_session.flush()

    with pytest.raises(ValidationError, match="already exists under that parent"):
        _update_activity_category(repo, canoeing, {"name": "KAYAKING"})
