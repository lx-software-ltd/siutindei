"""Public search picks one entry per schedule without a window aggregate."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from app.db.queries import ActivitySearchFilters
from app.db.queries import build_search_query


def test_unfiltered_search_plan_is_not_window_agg(db_session) -> None:
    """EXPLAIN of the unfiltered search must not window over every entry."""

    query = build_search_query(ActivitySearchFilters())
    compiled = query.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True, "render_postcompile": True},
    )
    sql = str(compiled)
    lowered = sql.lower()
    assert "distinct on (activity_schedule_entries.schedule_id)" in lowered
    assert "row_number" not in lowered
    plan_rows = db_session.execute(text("EXPLAIN " + sql)).all()
    plan = "\n".join(str(row[0]) for row in plan_rows)
    assert "WindowAgg" not in plan
