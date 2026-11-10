"""Public search limited to selected Hong Kong neighbourhoods."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from app.data.hk_neighbourhoods import (
    NEIGHBOURHOODS,
    neighbourhoods_for_scope_token,
    resolve_search_area_scope,
)
from app.db.queries import (
    ActivitySearchFilters,
    build_search_query,
    clear_search_area_scope_cache,
    configured_search_area_ids,
)

ROOT = Path(__file__).resolve().parents[1]
WIZARD_GROUP = UUID("c1111111-1111-1111-1111-111111111201")


@pytest.fixture(autouse=True)
def _clear_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SEARCH_AREA_SCOPE", raising=False)
    clear_search_area_scope_cache()


def _ids_for(token: str) -> frozenset:
    leaves = neighbourhoods_for_scope_token(token)
    assert leaves is not None
    return frozenset(item.id for item in leaves)


def test_blank_scope_is_unrestricted() -> None:
    assert resolve_search_area_scope("  , ") == (None, ())
    assert configured_search_area_ids() is None


def test_region_district_and_neighbourhood_slugs_combine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "SEARCH_AREA_SCOPE",
        " Kowloon, yau-tsim-mong, central-and-western-kennedy-town ",
    )
    clear_search_area_scope_cache()
    resolved = configured_search_area_ids()
    assert resolved is not None
    kennedy = _ids_for("central-and-western-kennedy-town")
    assert kennedy <= resolved
    assert _ids_for("kowloon") <= resolved
    assert _ids_for("yau-tsim-mong") <= resolved
    assert kennedy.isdisjoint(_ids_for("kowloon"))


def test_islands_region_matches_the_islands_district() -> None:
    region = neighbourhoods_for_scope_token("islands")
    district = tuple(item for item in NEIGHBOURHOODS if item.district == "Islands")
    assert region == district
    assert region is not None
    assert len(region) > 1


def test_unknown_slug_is_ignored_until_every_token_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolved, unknown = resolve_search_area_scope("kowloon,atlantis")
    assert unknown == ("atlantis",)
    assert resolved == _ids_for("kowloon")

    monkeypatch.setenv("SEARCH_AREA_SCOPE", "atlantis,narnia")
    clear_search_area_scope_cache()
    assert configured_search_area_ids() == frozenset()


def test_search_sql_intersects_the_requested_area_with_the_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEARCH_AREA_SCOPE", "kowloon")
    clear_search_area_scope_cache()
    query = build_search_query(
        ActivitySearchFilters(area_id=UUID("a1111111-1111-1111-1111-111111111102"))
    )
    compiled = str(query).lower()
    assert "geographic_areas" in compiled
    assert "locations.area_id in" in compiled

    blocked = str(
        build_search_query(ActivitySearchFilters(category_ids=[WIZARD_GROUP]))
    ).lower()
    assert blocked.count("locations.area_id") >= 2


def test_activity_lookup_and_partner_flag_skip_the_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEARCH_AREA_SCOPE", "not-a-place")
    clear_search_area_scope_cache()
    direct = str(
        build_search_query(ActivitySearchFilters(activity_id=UUID(int=1)))
    ).lower()
    partner = str(
        build_search_query(
            ActivitySearchFilters(apply_area_scope=False),
        )
    ).lower()
    assert "locations.area_id in" not in direct
    assert " false" not in direct
    assert "locations.area_id in" not in partner
    assert " false" not in partner

    closed = str(build_search_query(ActivitySearchFilters())).lower()
    assert " false" in closed


def test_validate_script_accepts_blank_and_rejects_unknown() -> None:
    script = ROOT / "scripts" / "deploy" / "validate_search_area_scope.py"
    blank = subprocess.run(
        [sys.executable, str(script)],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "SEARCH_AREA_SCOPE": "  "},
    )
    assert blank.returncode == 0
    assert "not limited" in blank.stdout

    known = subprocess.run(
        [sys.executable, str(script)],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "SEARCH_AREA_SCOPE": "yau-tsim-mong"},
    )
    assert known.returncode == 0
    assert "yau-tsim-mong:" in known.stdout

    unknown = subprocess.run(
        [sys.executable, str(script)],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "SEARCH_AREA_SCOPE": "kowloon,atlantis"},
    )
    assert unknown.returncode == 1
    assert "atlantis" in unknown.stderr


def test_public_search_hides_other_areas_and_partner_search_does_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.partner_auth import SCOPE_READ
    from app.api.search import lambda_handler

    monkeypatch.setenv("STAGING_SEARCH_DATA_ENABLED", "true")
    monkeypatch.setenv("SEARCH_AREA_SCOPE", "not-a-place")
    clear_search_area_scope_cache()
    from app.services import staging_search_store

    staging_search_store._FIXTURE_CACHE = None
    staging_search_store._SORTED_PUBLISHED_ITEMS = None

    def event(path: str, authorizer: dict | None = None) -> dict:
        return {
            "path": path,
            "headers": {},
            "queryStringParameters": {"limit": "2"},
            "multiValueQueryStringParameters": {"limit": ["2"]},
            "requestContext": {
                "requestId": "req-scope",
                "authorizer": authorizer or {},
            },
        }

    public = json.loads(lambda_handler(event("/v1/activities/search"), None)["body"])
    partner = json.loads(
        lambda_handler(
            event(
                "/v1/partner/activities/search",
                {"apiKeyId": "key-1", "scope": SCOPE_READ},
            ),
            None,
        )["body"]
    )
    assert public["items"] == []
    assert public["area_scope"] == []
    assert partner["area_scope"] == []
    assert partner["items"]

    activity_id = partner["items"][0]["activity"]["id"]
    direct_event = event("/v1/activities/search")
    direct_event["queryStringParameters"] = {"activity_id": activity_id, "limit": "1"}
    direct_event["multiValueQueryStringParameters"] = {
        "activity_id": [activity_id],
        "limit": ["1"],
    }
    direct = json.loads(lambda_handler(direct_event, None)["body"])
    assert direct["items"][0]["activity"]["id"] == activity_id
