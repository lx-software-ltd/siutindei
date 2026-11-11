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


def test_search_sql_names_the_scope_neighbourhood(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "SEARCH_AREA_SCOPE",
        "central-and-western-kennedy-town",
    )
    clear_search_area_scope_cache()
    kennedy = str(next(iter(_ids_for("central-and-western-kennedy-town"))))

    def bound_text(filters: ActivitySearchFilters) -> str:
        compiled = build_search_query(filters).compile()
        return " ".join(str(value).lower() for value in compiled.params.values())

    assert kennedy in bound_text(ActivitySearchFilters())
    monkeypatch.delenv("SEARCH_AREA_SCOPE")
    clear_search_area_scope_cache()
    assert kennedy not in bound_text(ActivitySearchFilters())

    monkeypatch.setenv(
        "SEARCH_AREA_SCOPE",
        "central-and-western-kennedy-town",
    )
    clear_search_area_scope_cache()
    wizard = bound_text(ActivitySearchFilters(category_ids=[WIZARD_GROUP]))
    assert wizard.count(kennedy) >= 2


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


def test_cursor_page_omits_area_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.search import lambda_handler

    monkeypatch.setenv("STAGING_SEARCH_DATA_ENABLED", "true")
    monkeypatch.delenv("SEARCH_AREA_SCOPE", raising=False)
    clear_search_area_scope_cache()

    def event(params: dict[str, str]) -> dict:
        return {
            "path": "/v1/activities/search",
            "headers": {},
            "queryStringParameters": params,
            "multiValueQueryStringParameters": {
                key: [value] for key, value in params.items()
            },
            "requestContext": {"requestId": "req-scope", "authorizer": {}},
        }

    first = json.loads(lambda_handler(event({"limit": "1"}), None)["body"])
    assert "area_scope" in first
    assert first["area_scope"] is None
    assert first["next_cursor"]
    continued = json.loads(
        lambda_handler(
            event({"limit": "1", "cursor": first["next_cursor"]}),
            None,
        )["body"]
    )
    assert "area_scope" not in continued
    assert continued["items"]


def test_database_drops_schedules_outside_the_scope(
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from decimal import Decimal

    from app.db.models import (
        Activity,
        ActivityCategory,
        ActivityPricing,
        ActivitySchedule,
        ActivityScheduleEntry,
        GeographicArea,
        Location,
        Organization,
        PricingType,
        ScheduleType,
    )
    from psycopg.types.range import Range

    def publish(name: str, area_id: UUID) -> None:
        org = Organization(
            name=name,
            description="scope test",
            manager_id="00000000-0000-0000-0000-000000000001",
        )
        category = ActivityCategory(name=f"{name} category", display_order=0)
        db_session.add_all([org, category])
        db_session.flush()
        area = db_session.get(GeographicArea, area_id)
        if area is None:
            area = GeographicArea(
                id=area_id,
                name=name,
                level="neighbourhood",
                active=True,
            )
            db_session.add(area)
            db_session.flush()
        location = Location(org_id=org.id, area_id=area.id, address="1 Test Street")
        activity = Activity(
            org_id=org.id,
            category_id=category.id,
            name=name,
            description="class",
            age_range=Range(3, 6, bounds="[]"),
        )
        db_session.add_all([location, activity])
        db_session.flush()
        db_session.add(
            ActivityPricing(
                activity_id=activity.id,
                location_id=location.id,
                pricing_type=PricingType.PER_CLASS,
                amount=Decimal("100.00"),
                currency="HKD",
            )
        )
        db_session.add(
            ActivitySchedule(
                activity_id=activity.id,
                location_id=location.id,
                schedule_type=ScheduleType.WEEKLY,
                languages=["en"],
                entries=[
                    ActivityScheduleEntry(
                        day_of_week_utc=1,
                        start_minutes_utc=600,
                        end_minutes_utc=660,
                    )
                ],
            )
        )
        db_session.flush()

    kennedy = next(
        iter(neighbourhoods_for_scope_token("central-and-western-kennedy-town"))
    )
    mongkok = next(iter(neighbourhoods_for_scope_token("yau-tsim-mong-mong-kok")))
    publish("Kennedy class", kennedy.id)
    publish("Mong Kok class", mongkok.id)

    def names() -> set[str]:
        rows = db_session.execute(
            build_search_query(ActivitySearchFilters(limit=50))
        ).all()
        return {row._mapping[Activity].name for row in rows}

    monkeypatch.setenv("SEARCH_AREA_SCOPE", "yau-tsim-mong")
    clear_search_area_scope_cache()
    scoped = names()
    assert "Mong Kok class" in scoped
    assert "Kennedy class" not in scoped

    monkeypatch.delenv("SEARCH_AREA_SCOPE")
    clear_search_area_scope_cache()
    opened = names()
    assert {"Mong Kok class", "Kennedy class"} <= opened
