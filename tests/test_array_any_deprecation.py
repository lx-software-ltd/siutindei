"""ARRAY membership must use any_() and must not warn."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path
from uuid import uuid4

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from sqlalchemy.dialects import postgresql  # noqa: E402
from sqlalchemy.exc import SADeprecationWarning  # noqa: E402

from app.db.models.feedback_label import FeedbackLabel  # noqa: E402
from app.db.queries import ActivitySearchFilters, build_search_query  # noqa: E402
from app.db.repositories.feedback_label import (  # noqa: E402
    FeedbackLabelRepository,
)
from app.db.repositories.schedule import ActivityScheduleRepository  # noqa: E402


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
        self.deleted = None
        self.flushed = False

    def execute(self, query):
        self.queries.append(query)
        return _Result()

    def delete(self, entity) -> None:
        self.deleted = entity

    def flush(self) -> None:
        self.flushed = True


def _compiled(query) -> str:
    return str(
        query.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def _array_deprecations(
    caught: list[warnings.WarningMessage],
) -> list[warnings.WarningMessage]:
    return [item for item in caught if issubclass(item.category, SADeprecationWarning)]


def test_language_search_uses_any_without_deprecation() -> None:
    """Search language filters compile to ANY and do not warn."""

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        query = build_search_query(ActivitySearchFilters(languages=("en", "zh")))
    sql = _compiled(query)
    assert "'en' = ANY (activity_schedule.languages)" in sql
    assert "'zh' = ANY (activity_schedule.languages)" in sql
    assert _array_deprecations(caught) == []


def test_schedule_repository_language_lookup_does_not_warn() -> None:
    """Schedule language lookup builds ANY without the ARRAY comparator."""

    session = _RecordingSession()
    repo = ActivityScheduleRepository(session)  # type: ignore[arg-type]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        repo.find_by_language("en")
    assert session.queries
    assert "'en' = ANY (activity_schedule.languages)" in _compiled(session.queries[0])
    assert _array_deprecations(caught) == []


def test_feedback_label_delete_checks_usage_without_deprecation() -> None:
    """Deleting a label checks membership with any_()."""

    session = _RecordingSession()
    repo = FeedbackLabelRepository(session)  # type: ignore[arg-type]
    label_id = uuid4()
    label = FeedbackLabel(id=label_id, name="Unused", name_translations={})
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        repo.delete(label)
    sql = "\n".join(_compiled(query) for query in session.queries)
    rendered = str(label_id)
    assert f"'{rendered}' = ANY (tickets.feedback_label_ids)" in sql
    assert f"'{rendered}' = ANY (organization_feedback.label_ids)" in sql
    assert session.deleted is label
    assert session.flushed is True
    assert _array_deprecations(caught) == []
