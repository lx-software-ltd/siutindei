"""IAM database engines are reused inside the token lifetime."""

from __future__ import annotations

from sqlalchemy.pool import NullPool
from sqlalchemy.pool import QueuePool

from app.db import engine as engine_module


def test_get_engine_reuses_iam_engine_within_ttl(monkeypatch) -> None:
    """Two calls inside ten minutes return the same one-connection engine."""

    monkeypatch.setenv("DATABASE_IAM_AUTH", "true")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/backend_test",
    )
    engine_module.clear_engine_cache()
    clock = {"now": 1000.0}
    monkeypatch.setattr(engine_module.time, "monotonic", lambda: clock["now"])
    try:
        first = engine_module.get_engine()
        clock["now"] = 1100.0
        second = engine_module.get_engine()
        assert first is second
        assert isinstance(first.pool, QueuePool)
        assert not isinstance(first.pool, NullPool)
        assert first.pool.size() == 1
        clock["now"] = 1000.0 + engine_module._IAM_ENGINE_TTL_SECONDS
        third = engine_module.get_engine()
        assert third is not first
    finally:
        engine_module.clear_engine_cache()
