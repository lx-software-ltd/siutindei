"""Categories hidden from public search, by their own flag or an ancestor's."""

from __future__ import annotations

from functools import cache
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.db.models import ActivityCategory


@cache
def _hidden_tree() -> Any:
    # One CTE object, so several references in one statement share a name.
    base = (
        select(ActivityCategory.id)
        .where(ActivityCategory.hidden_from_public.is_(True))
        .cte(name="hidden_category_tree", recursive=True)
    )
    categories = ActivityCategory.__table__
    return base.union_all(
        select(categories.c.id).where(categories.c.parent_id == base.c.id)
    )


def hidden_category_ids_subquery() -> Select[Any]:
    """Ids of hidden categories and every descendant."""
    return select(_hidden_tree().c.id)


def public_category_clause(category_column: Any) -> Any:
    """True when a category is not hidden from public search."""
    return category_column.notin_(hidden_category_ids_subquery())


def hidden_category_ids(session: Session) -> set[UUID]:
    """Hidden category ids, loaded once for Python-side checks."""
    rows = session.scalars(hidden_category_ids_subquery()).all()
    return {UUID(str(row)) for row in rows}
