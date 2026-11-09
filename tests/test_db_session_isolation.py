"""The test session must not publish rows outside its transaction."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.feedback_label import FeedbackLabel


def test_rollback_then_commit_stays_inside_the_fixture(db_session, test_engine) -> None:
    """A commit after rollback is still undone for other connections."""

    name = f"isolation-{uuid4()}"
    db_session.add(FeedbackLabel(name=name, name_translations={}))
    db_session.flush()
    db_session.rollback()

    db_session.add(FeedbackLabel(name=name, name_translations={}))
    db_session.commit()

    with Session(test_engine) as other:
        found = other.scalars(
            select(FeedbackLabel).where(FeedbackLabel.name == name)
        ).all()
    assert found == []
