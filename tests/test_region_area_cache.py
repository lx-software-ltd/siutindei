"""The region area map is reused for ten minutes outside pytest."""

from __future__ import annotations

import app.api.search as search


def test_region_area_cache_reuses_map_for_ten_minutes(monkeypatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    search._region_area_cache = None
    calls = {"count": 0}

    def fake_build(_session):
        calls["count"] += 1
        return {"area": "region"}

    clock = {"now": 50.0}
    monkeypatch.setattr(search, "_build_region_area_map", fake_build)
    monkeypatch.setattr(search.time, "monotonic", lambda: clock["now"])
    try:
        assert search._load_region_area_cache(None) == {"area": "region"}
        clock["now"] = 100.0
        assert search._load_region_area_cache(None) == {"area": "region"}
        assert calls["count"] == 1
        clock["now"] = 50.0 + search._REGION_CACHE_TTL_SECONDS
        assert search._load_region_area_cache(None) == {"area": "region"}
        assert calls["count"] == 2
    finally:
        search._region_area_cache = None
