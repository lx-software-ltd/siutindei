"""Progress checks for the catalog backfill drain. No database required."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REVISION = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "db"
    / "alembic"
    / "versions"
    / "0049_catalog_version_fixes.py"
)


def _revision():
    spec = importlib.util.spec_from_file_location("rev0049", _REVISION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_drain_stops_when_the_same_id_comes_back() -> None:
    revision = _revision()
    calls = {"n": 0}

    def fetch_ids() -> list[str]:
        calls["n"] += 1
        return ["id-a", "id-b", "id-c", "id-d", "id-e", "id-f"]

    with pytest.raises(RuntimeError, match="made no progress for activity_pricing"):
        revision._drain_ids(
            "catalog_backfill_deleted_batch",
            "activity_pricing",
            fetch_ids,
        )
    assert calls["n"] == 2
    with pytest.raises(RuntimeError, match="sample ids: id-a, id-b, id-c, id-d, id-e"):
        revision._drain_ids(
            "catalog_backfill_deleted_batch",
            "activity_pricing",
            fetch_ids,
        )


def test_drain_returns_when_the_next_batch_is_empty() -> None:
    revision = _revision()
    pending = [["id-a"], []]

    def fetch_ids() -> list[str]:
        return pending.pop(0)

    revision._drain_ids("catalog_backfill_live_batch", "organizations", fetch_ids)


def test_drain_stops_at_the_cap_when_every_batch_moves() -> None:
    revision = _revision()
    step = {"n": 0}

    def fetch_ids() -> list[str]:
        step["n"] += 1
        return [f"id-{step['n']}"]

    with pytest.raises(RuntimeError, match="did not finish for organizations"):
        revision._drain_ids(
            "catalog_backfill_live_batch",
            "organizations",
            fetch_ids,
            cap=3,
        )
    assert step["n"] == 3
