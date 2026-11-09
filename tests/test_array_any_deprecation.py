"""ARRAY membership must use any_() and must not warn."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path
from uuid import uuid4

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from app.db.queries import ActivitySearchFilters, build_search_query
from app.db.repositories.feedback_label import FeedbackLabelRepository
from app.db.repositories.schedule import ActivityScheduleRepository
from sqlalchemy.dialects import postgresql


class _Scalars:
    def all(self):
        return []


class _Result:
    def scalars(self):
        return _Scalars()

    def scalar(self):
        return None


class _RecordingSession:
    def __init__(self) -> None:
        self.queries = []

    def execute(self, query):
        self.queries.append(query)
        return _Result()


def _compiled(query) -> str:
    return str(
        query.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def _unexpected(caught: list[warnings.WarningMessage]) -> list[warnings.WarningMessage]:
    return [item for item in caught if issubclass(item.category, Warning)]


def test_language_search_uses_any_without_deprecation() -> None:
    """Search language filters compile to ANY and do not warn."""

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        query = build_search_query(ActivitySearchFilters(languages=("en", "zh")))
    sql = _compiled(query)
    assert "'en' = ANY (activity_schedule.languages)" in sql
    assert "'zh' = ANY (activity_schedule.languages)" in sql
    assert _unexpected(caught) == []


def test_schedule_repository_language_lookup_does_not_warn() -> None:
    """Schedule language lookup builds ANY without the ARRAY comparator."""

    session = _RecordingSession()
    repo = ActivityScheduleRepository(session)  # type: ignore[arg-type]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        repo.find_by_language("en")
    assert session.queries
    assert "'en' = ANY (activity_schedule.languages)" in _compiled(session.queries[0])
    assert _unexpected(caught) == []


def test_feedback_label_usage_lookup_does_not_warn() -> None:
    """Label deletion checks membership with any_()."""

    session = _RecordingSession()
    repo = FeedbackLabelRepository(session)  # type: ignore[arg-type]
    label_id = uuid4()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert repo._is_used(label_id) is False
    sql = "\n".join(_compiled(query) for query in session.queries)
    rendered = str(label_id)
    assert f"'{rendered}' = ANY (tickets.feedback_label_ids)" in sql
    assert f"'{rendered}' = ANY (organization_feedback.label_ids)" in sql
    assert _unexpected(caught) == []
