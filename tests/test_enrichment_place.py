"""Neighbourhoods, categories, names, and logos from website enrichment."""

from __future__ import annotations

import json
import time
from decimal import Decimal

import pytest
from app.db.models import (
    Activity,
    ActivityCategory,
    GeographicArea,
    Location,
    Organization,
)
from app.db.models.category_suggestion import PENDING_CATEGORY_ID, CategorySuggestion
from app.db.models.import_settings import ImportSettings
from app.db.models.org_enrichment import OrgEnrichmentProposal, OrgEnrichmentRun
from app.exceptions import ValidationError
from app.services.aws_proxy import AwsProxyError
from app.services.enrichment.apply import apply_proposals
from app.services.enrichment.apply_rows import apply_one
from app.services.enrichment.extract import proposals_from_pages, validate_model_sheet
from app.services.enrichment.logos import media_proposals, social_logo_proposals
from app.services.enrichment.parse import parse_html
from app.services.enrichment.prompt import instructions_for
from app.services.enrichment.refine import annotate, catalog_names
from app.services.enrichment.run import process_enrichment
from app.services.location_fix_geocode import AddressLookupFailed
from sqlalchemy import select

_PAGE = "https://club.test/"


def _org(session, **fields) -> Organization:
    values = {"name": "North Club", "manager_id": "mgr-1"}
    values.update(fields)
    org = Organization(**values)
    session.add(org)
    session.flush()
    return org


def _area(session, **fields) -> GeographicArea:
    values: dict = {"active": True, "name_translations": {}}
    values.update(fields)
    row = GeographicArea(**values)
    session.add(row)
    session.flush()
    return row


def _kowloon(session) -> tuple[GeographicArea, GeographicArea]:
    country = _area(session, name="Hong Kong", level="country")
    region = _area(session, name="Kowloon", level="region", parent_id=country.id)
    district = _area(
        session, name="Yau Tsim Mong", level="district", parent_id=region.id
    )
    tai = _area(
        session,
        name="Tai Kok Tsui",
        level="neighbourhood",
        parent_id=district.id,
        display_order=0,
        lat=22.322,
        lng=114.161,
        name_translations={"zh-HK": "大角咀"},
    )
    mong = _area(
        session,
        name="Mong Kok",
        level="neighbourhood",
        parent_id=district.id,
        display_order=1,
        lat=22.319,
        lng=114.169,
        name_translations={"zh-HK": "旺角"},
    )
    return mong, tai


def _location(address: str, **proposed: object) -> dict:
    return {
        "section": "Locations",
        "kind": "create_location",
        "field": None,
        "label": "Location",
        "proposed": {"address": address, **proposed},
    }


def _one(session, org, item, **kwargs) -> dict:
    found = annotate(session, org, [item], **kwargs)
    assert len(found) == 1
    return found[0]["proposed"]


def test_chinese_neighbourhood_matches_the_catalog_row(db_session) -> None:
    mong, _tai = _kowloon(db_session)
    org = _org(db_session)
    calls: list[str] = []
    proposed = _one(
        db_session,
        org,
        _location("1 Nathan Road", neighbourhood="旺角"),
        geocode=lambda address: calls.append(address),
    )
    assert proposed["area_id"] == str(mong.id)
    assert proposed["area_match"] == "neighbourhood"
    assert proposed["area_path"] == "Kowloon · Yau Tsim Mong · Mong Kok"
    assert calls == []


def test_legacy_area_name_matches_a_neighbourhood(db_session) -> None:
    mong, _tai = _kowloon(db_session)
    proposed = _one(
        db_session,
        _org(db_session),
        _location("1 Nathan Road", area_name="旺角"),
        geocode=lambda _address: None,
    )
    assert proposed["area_id"] == str(mong.id)
    assert proposed["area_match"] == "neighbourhood"


def test_address_text_matches_the_neighbourhood(db_session) -> None:
    mong, _tai = _kowloon(db_session)
    proposed = _one(
        db_session,
        _org(db_session),
        _location("123 Nathan Road, Mong Kok"),
        geocode=lambda _address: None,
    )
    assert proposed["area_id"] == str(mong.id)
    assert proposed["area_match"] == "address"


def test_confident_pin_picks_the_nearest_neighbourhood(db_session) -> None:
    mong, tai = _kowloon(db_session)
    proposed = _one(
        db_session,
        _org(db_session),
        _location("123 Nathan Road", district="Yau Tsim Mong"),
        geocode=lambda _address: {"lat": 22.319, "lng": 114.169},
    )
    assert proposed["area_id"] == str(mong.id)
    assert proposed["area_id"] != str(tai.id)
    assert proposed["area_match"] == "geocode"
    assert proposed["lat"] == 22.319


def test_far_or_missing_pin_does_not_snap_a_district(db_session) -> None:
    _mong, tai = _kowloon(db_session)
    org = _org(db_session)
    for pin in (None, {"lat": 22.0, "lng": 114.0}):
        proposed = _one(
            db_session,
            org,
            _location("123 Nathan Road", district="Yau Tsim Mong"),
            geocode=lambda _address, pin=pin: pin,
        )
        assert "area_id" not in proposed
        assert proposed["area_match"] == "district"
        assert "Yau Tsim Mong" in proposed["area_path"]
        assert tai.name not in proposed["area_path"]


def test_district_name_does_not_match_its_shorter_neighbourhood(db_session) -> None:
    district = _area(db_session, name="Central and Western", level="district")
    central = _area(
        db_session,
        name="Central",
        level="neighbourhood",
        parent_id=district.id,
    )
    proposed = _one(
        db_session,
        _org(db_session),
        _location("Shop 4, Central and Western"),
        geocode=lambda _address: None,
    )
    assert proposed.get("area_id") != str(central.id)
    assert "area_id" not in proposed
    assert proposed["area_match"] == "district"


def test_geocode_stops_after_five_calls(db_session) -> None:
    _kowloon(db_session)
    calls: list[str] = []
    slept: list[float] = []

    def lookup(address: str) -> dict[str, float]:
        calls.append(address)
        return {"lat": 22.319, "lng": 114.169}

    items = [
        _location(f"Venue {index} Road", district="Yau Tsim Mong") for index in range(6)
    ]
    found = annotate(
        db_session,
        _org(db_session),
        items,
        geocode=lookup,
        sleep=slept.append,
    )
    assert len(calls) == 5
    assert slept == [1.0, 1.0, 1.0, 1.0]
    assert "area_id" not in found[5]["proposed"]


def test_geocode_failure_does_not_fail_the_extract(db_session) -> None:
    _kowloon(db_session)

    def lookup(_address: str) -> None:
        raise AddressLookupFailed("down")

    proposed = _one(
        db_session,
        _org(db_session),
        _location("123 Nathan Road", district="Yau Tsim Mong"),
        geocode=lookup,
    )
    assert "area_id" not in proposed
    assert proposed["area_match"] == "district"


def test_category_match_uses_the_catalog_and_skips_pending(db_session) -> None:
    dance = ActivityCategory(
        name="Dance and ballet",
        name_translations={"zh": "舞蹈芭蕾"},
        display_order=1,
    )
    pending = ActivityCategory(
        id=PENDING_CATEGORY_ID,
        name="Pending categorisation",
        display_order=9999,
    )
    db_session.add_all([dance, pending])
    db_session.flush()
    org = _org(db_session)
    exact = _one(
        db_session,
        org,
        _activity("Dance and ballet"),
        geocode=lambda _address: None,
    )
    translated = _one(
        db_session,
        org,
        _activity("舞蹈芭蕾"),
        geocode=lambda _address: None,
    )
    unknown = _one(
        db_session,
        org,
        _activity("Ballet"),
        geocode=lambda _address: None,
    )
    suffixed = _one(
        db_session,
        org,
        _activity("Dance and ballet (舞蹈芭蕾)"),
        geocode=lambda _address: None,
    )
    assert exact["category_id"] == str(dance.id)
    assert translated["category_id"] == str(dance.id)
    assert suffixed["category_id"] == str(dance.id)
    assert "category_id" not in unknown
    assert catalog_names(db_session) == ["Dance and ballet (舞蹈芭蕾)"]
    assert "Pending" not in " ".join(catalog_names(db_session))


def test_catalog_sentence_names_category_words() -> None:
    text = instructions_for(["Dance and ballet (舞蹈芭蕾)"])
    assert "category_name must be one of: Dance and ballet (舞蹈芭蕾)" in text
    assert "category_words" in text
    assert instructions_for([]) == ""


def test_name_is_proposed_only_while_under_review(db_session) -> None:
    pending = _org(db_session, review_status="pending_review")
    approved = _org(db_session, name="Approved Club", review_status="approved")
    changed = annotate(
        db_session,
        pending,
        [_name("HARBOUR STUDIO")],
        geocode=lambda _address: None,
    )
    same = annotate(
        db_session,
        pending,
        [_name("NORTH CLUB")],
        geocode=lambda _address: None,
    )
    blocked = annotate(
        db_session,
        approved,
        [_name("HARBOUR STUDIO")],
        geocode=lambda _address: None,
    )
    assert changed[0]["proposed"]["name"] == "Harbour Studio"
    assert same == []
    assert blocked == []


def test_sheet_keeps_place_category_and_name_fields() -> None:
    pages = [
        {
            "url": _PAGE,
            "final_url": _PAGE,
            "text": "Harbour Studio teaches Ballet at 123 Nathan Road, Mong Kok.",
            "jsonld_raw": [],
            "og": {},
        }
    ]
    sheet = {
        "locations": [
            {
                "address": "123 Nathan Road",
                "district": "Yau Tsim Mong",
                "neighbourhood": "Mong Kok",
                "area_name": "Hong Kong",
                "confidence": 0.9,
                "url": _PAGE,
                "quote": "123 Nathan Road, Mong Kok",
            }
        ],
        "activities": [
            {
                "name": "Ballet class",
                "category_name": "Dance and ballet",
                "category_words": "Ballet",
                "url": _PAGE,
                "quote": "teaches Ballet at 123",
            }
        ],
        "organization": {
            "name": {
                "value": "Harbour Studio",
                "confidence": 0.9,
                "evidence": [{"url": _PAGE, "quote": "Harbour Studio"}],
            }
        },
    }
    found = validate_model_sheet(sheet, pages, {"name": "North Club"})
    location = next(item for item in found if item["kind"] == "create_location")
    activity = next(item for item in found if item["kind"] == "create_activity")
    name = next(item for item in found if item["field"] == "name")
    assert location["proposed"]["district"] == "Yau Tsim Mong"
    assert location["proposed"]["neighbourhood"] == "Mong Kok"
    assert location["proposed"]["area_name"] == "Hong Kong"
    assert activity["proposed"]["category_words"] == "Ballet"
    assert name["proposed"]["name"] == "Harbour Studio"


def test_page_name_comes_from_the_site_title_and_jsonld() -> None:
    html = """
    <html><head>
      <meta property="og:site_name" content="Harbour Studio">
      <script type="application/ld+json">
        {"@type":"SportsOrganization","name":"Harbour Studio"}
      </script>
    </head><body><p>Classes for children every Saturday morning.</p></body></html>
    """
    page = parse_html(_PAGE, html)
    found = proposals_from_pages([page], {"name": "North Club"})
    names = [item for item in found if item["field"] == "name"]
    assert names
    assert names[0]["proposed"]["name"] == "Harbour Studio"


def test_jsonld_logo_beats_the_open_graph_image() -> None:
    html = """
    <html><head>
      <meta property="og:image" content="https://club.test/og.png">
      <link rel="apple-touch-icon" href="/icon.png">
      <script type="application/ld+json">
        {"@type":"Organization","logo":"https://club.test/brand.png"}
      </script>
    </head><body>
      <img src="https://club.test/mark.png" class="site-logo" alt="mark" width="500" height="500">
    </body></html>
    """
    page = parse_html(_PAGE, html)
    assert page["icons"][0]["href"] == "https://club.test/icon.png"
    assert any(image.get("class") == "site-logo" for image in page["images"])
    found = media_proposals([page])
    logo = next(item for item in found if item["proposed"]["logo"])
    assert logo["proposed"]["source_url"] == "https://club.test/brand.png"
    photos = [
        item["proposed"]["source_url"] for item in found if not item["proposed"]["logo"]
    ]
    assert "https://club.test/og.png" in photos


def test_logo_class_beats_the_open_graph_image() -> None:
    found = media_proposals(
        [
            {
                "url": _PAGE,
                "images": [
                    {"src": "https://club.test/og.png", "alt": "og:image", "class": ""},
                    {
                        "src": "https://club.test/mark.png",
                        "alt": "mark",
                        "class": "site-logo",
                    },
                ],
                "jsonld": [],
                "icons": [],
            }
        ]
    )
    logo = next(item for item in found if item["proposed"]["logo"])
    assert logo["proposed"]["source_url"] == "https://club.test/mark.png"


def test_open_graph_image_is_the_logo_when_nothing_else_is() -> None:
    found = media_proposals(
        [
            {
                "url": _PAGE,
                "images": [
                    {"src": "https://club.test/og.png", "alt": "og:image", "class": ""}
                ],
                "jsonld": [],
                "icons": [],
            }
        ]
    )
    assert found[0]["field"] == "logo"
    assert found[0]["proposed"]["logo"] is True
    assert found[0]["proposed"]["source_url"] == "https://club.test/og.png"


def test_social_logo_is_skipped_without_a_token(monkeypatch) -> None:
    monkeypatch.delenv("META_GRAPH_API_KEY", raising=False)
    org = Organization(
        name="North Club", manager_id="mgr-1", facebook="https://facebook.com/northclub"
    )
    assert social_logo_proposals(org, []) == []


def test_social_logo_sends_the_token_as_a_bearer_header(monkeypatch) -> None:
    monkeypatch.setenv("META_GRAPH_API_KEY", "meta-secret")
    seen: dict[str, object] = {}

    def fake(_method, url, headers=None, timeout=10):
        del timeout
        seen["url"] = url
        seen["headers"] = headers
        body = json.dumps(
            {"data": {"url": "https://cdn.example/logo.jpg", "is_silhouette": False}}
        )
        return {"status": 200, "body": body}

    monkeypatch.setattr("app.services.enrichment.logos.http_invoke", fake)
    org = Organization(name="North Club", manager_id="mgr-1")
    found = social_logo_proposals(
        org,
        [
            {
                "kind": "update_organization",
                "field": "facebook",
                "proposed": {"facebook": "https://www.facebook.com/northclub"},
            }
        ],
    )
    assert found[0]["label"] == "Logo · Facebook"
    assert found[0]["proposed"]["source_url"] == "https://cdn.example/logo.jpg"
    assert seen["headers"]["Authorization"] == "Bearer meta-secret"
    assert "meta-secret" not in str(seen["url"])
    assert str(seen["url"]).startswith(
        "https://graph.facebook.com/v21.0/northclub/picture?"
    )


def test_social_logo_failure_adds_nothing(monkeypatch) -> None:
    monkeypatch.setenv("META_GRAPH_API_KEY", "meta-secret")

    def fake(_method, _url, headers=None, timeout=10):
        del headers, timeout
        raise AwsProxyError("URLNotAllowed", "blocked")

    monkeypatch.setattr("app.services.enrichment.logos.http_invoke", fake)
    org = Organization(
        name="North Club",
        manager_id="mgr-1",
        facebook="https://www.facebook.com/northclub",
    )
    assert social_logo_proposals(org, []) == []


def test_apply_saves_the_neighbourhood_and_pin(db_session) -> None:
    mong, _tai = _kowloon(db_session)
    org = _org(db_session)
    apply_one(
        db_session,
        org,
        _proposal(
            "create_location",
            "Locations",
            {
                "address": "123 Nathan Road",
                "area_id": str(mong.id),
                "lat": 22.319,
                "lng": 114.169,
            },
        ),
        {},
        copy_image=None,
    )
    row = db_session.scalars(select(Location)).one()
    assert str(row.area_id) == str(mong.id)
    assert row.lat == Decimal("22.319000")
    assert row.lng == Decimal("114.169000")


def test_unmatched_category_wording_becomes_a_suggestion(db_session) -> None:
    org = _org(db_session, review_status="pending_review")
    apply_one(
        db_session,
        org,
        _proposal(
            "create_activity",
            "Activities",
            {
                "name": "Beginner ballet",
                "category_words": "Ballet",
                "age_min": 6,
                "age_max": 12,
            },
        ),
        {},
        copy_image=None,
    )
    activity = db_session.scalars(select(Activity)).one()
    assert str(activity.category_id) == str(PENDING_CATEGORY_ID)
    suggestion = db_session.scalars(select(CategorySuggestion)).one()
    assert suggestion.requested_name == "Ballet"
    assert suggestion.source == "import"


def test_approved_activity_still_needs_a_category(db_session) -> None:
    org = _org(db_session, review_status="approved")
    with pytest.raises(ValidationError) as exc:
        apply_one(
            db_session,
            org,
            _proposal(
                "create_activity",
                "Activities",
                {
                    "name": "Beginner ballet",
                    "category_name": "Ballet",
                    "age_min": 6,
                    "age_max": 12,
                },
            ),
            {},
            copy_image=None,
        )
    assert exc.value.field == "category_id"
    assert db_session.scalars(select(Activity)).all() == []


def test_name_apply_updates_only_an_organization_under_review(db_session) -> None:
    pending = _org(db_session, review_status="pending_review")
    apply_one(
        db_session,
        pending,
        _proposal(
            "update_organization",
            "Organization",
            {"name": "HARBOUR STUDIO"},
            field="name",
            current_value={"name": "North Club"},
        ),
        {},
        copy_image=None,
    )
    assert pending.name == "Harbour Studio"

    taken = _org(db_session, name="Taken Club", review_status="pending_review")
    second = _org(db_session, name="Second Club", review_status="pending_review")
    with pytest.raises(ValidationError):
        apply_one(
            db_session,
            second,
            _proposal(
                "update_organization",
                "Organization",
                {"name": "TAKEN CLUB"},
                field="name",
                current_value={"name": "Second Club"},
            ),
            {},
            copy_image=None,
        )
    assert second.name == "Second Club"
    assert taken.name == "Taken Club"

    approved = _org(db_session, name="Approved Club", review_status="approved")
    with pytest.raises(ValidationError) as exc:
        apply_one(
            db_session,
            approved,
            _proposal(
                "update_organization",
                "Organization",
                {"name": "HARBOUR STUDIO"},
                field="name",
                current_value={"name": "Approved Club"},
            ),
            {},
            copy_image=None,
        )
    assert exc.value.field == "name"
    assert approved.name == "Approved Club"


def test_a_logo_image_beats_a_favicon() -> None:
    found = media_proposals(
        [
            {
                "url": _PAGE,
                "images": [
                    {
                        "src": "https://club.test/mark.png",
                        "alt": "mark",
                        "class": "site-logo",
                    }
                ],
                "jsonld": [],
                "icons": [{"href": "https://club.test/favicon.ico", "rel": "icon"}],
            }
        ]
    )
    logo = next(item for item in found if item["proposed"]["logo"])
    assert logo["proposed"]["source_url"] == "https://club.test/mark.png"


def test_instagram_logo_uses_business_discovery(monkeypatch) -> None:
    monkeypatch.setenv("META_GRAPH_API_KEY", "meta-secret")
    monkeypatch.setenv("META_INSTAGRAM_USER_ID", "17841400000000021")
    seen: dict[str, object] = {}

    def fake(_method, url, headers=None, timeout=10):
        del timeout
        seen["url"] = url
        seen["headers"] = headers
        body = json.dumps(
            {
                "business_discovery": {
                    "profile_picture_url": "https://cdn.example/ig.jpg"
                }
            }
        )
        return {"status": 200, "body": body}

    monkeypatch.setattr("app.services.enrichment.logos.http_invoke", fake)
    org = Organization(
        name="North Club",
        manager_id="mgr-1",
        instagram="https://www.instagram.com/northclub/",
    )
    found = social_logo_proposals(org, [])
    assert found[0]["proposed"]["source_url"] == "https://cdn.example/ig.jpg"
    assert "17841400000000021" in str(seen["url"])
    assert "business_discovery.username" in str(seen["url"])
    assert "meta-secret" not in str(seen["url"])
    assert seen["headers"]["Authorization"] == "Bearer meta-secret"


def test_a_facebook_silhouette_is_not_a_logo(monkeypatch) -> None:
    monkeypatch.setenv("META_GRAPH_API_KEY", "meta-secret")

    def fake(_method, _url, headers=None, timeout=10):
        del headers, timeout
        body = json.dumps(
            {"data": {"url": "https://cdn.example/default.jpg", "is_silhouette": True}}
        )
        return {"status": 200, "body": body}

    monkeypatch.setattr("app.services.enrichment.logos.http_invoke", fake)
    org = Organization(
        name="North Club",
        manager_id="mgr-1",
        facebook="https://www.facebook.com/northclub",
    )
    assert social_logo_proposals(org, []) == []


def test_social_logo_is_skipped_when_the_time_budget_is_spent(monkeypatch) -> None:
    monkeypatch.setenv("META_GRAPH_API_KEY", "meta-secret")
    called: list[str] = []

    def fake(_method, url, headers=None, timeout=10):
        del headers, timeout
        called.append(url)
        return {"status": 200, "body": "{}"}

    monkeypatch.setattr("app.services.enrichment.logos.http_invoke", fake)
    org = Organization(
        name="North Club",
        manager_id="mgr-1",
        facebook="https://www.facebook.com/northclub",
    )
    assert social_logo_proposals(org, [], deadline=time.monotonic() - 1) == []
    assert called == []


def test_a_pin_matches_when_the_page_names_no_district(db_session) -> None:
    mong, _tai = _kowloon(db_session)
    calls: list[str] = []

    def geocode(address: str) -> dict[str, float]:
        calls.append(address)
        return {"lat": 22.3192, "lng": 114.1694}

    proposed = _one(
        db_session,
        _org(db_session),
        _location("123 Nathan Road"),
        geocode=geocode,
        sleep=lambda _seconds: None,
    )
    assert calls == ["123 Nathan Road"]
    assert proposed["area_id"] == str(mong.id)
    assert proposed["area_match"] == "geocode"


def test_a_neighbourhood_outside_the_named_district_is_flagged(db_session) -> None:
    _kowloon(db_session)
    country = _area(db_session, name="Hong Kong Island Country", level="country")
    region = _area(
        db_session, name="Hong Kong Island", level="region", parent_id=country.id
    )
    district = _area(
        db_session,
        name="Central and Western",
        level="district",
        parent_id=region.id,
    )
    _area(
        db_session,
        name="Central",
        level="neighbourhood",
        parent_id=district.id,
        display_order=0,
    )
    proposed = _one(
        db_session,
        _org(db_session),
        _location("Shop 1", district="Yau Tsim Mong", neighbourhood="Central"),
        geocode=lambda _address: None,
    )
    assert "area_id" not in proposed
    assert proposed["area_match"] == "district"
    assert "Yau Tsim Mong" in proposed["area_path"]
    assert "outside" in proposed["area_note"]


def test_a_failed_lookup_drops_a_cached_neighbourhood(db_session) -> None:
    _mong, tai = _kowloon(db_session)
    proposed = _one(
        db_session,
        _org(db_session),
        _location(
            "1 Nathan Road",
            district="Yau Tsim Mong",
            area_id=str(tai.id),
            area_path="Kowloon · Yau Tsim Mong · Tai Kok Tsui",
            area_match="geocode",
            lat=22.322,
            lng=114.161,
        ),
        geocode=lambda _address: {"lat": 22.0, "lng": 114.0},
    )
    assert "area_id" not in proposed
    assert proposed["area_match"] == "district"
    assert "Tai Kok Tsui" not in proposed["area_path"]


def test_geocode_stops_when_the_lookup_budget_is_spent(db_session) -> None:
    _kowloon(db_session)
    calls: list[str] = []
    proposed = _one(
        db_session,
        _org(db_session),
        _location("123 Nathan Road", district="Yau Tsim Mong"),
        geocode=lambda address: calls.append(address),
        deadline=time.monotonic() - 1,
    )
    assert calls == []
    assert "area_id" not in proposed


def test_areas_are_loaded_once_per_extract(db_session, monkeypatch) -> None:
    _kowloon(db_session)
    from app.services.enrichment import places as places_mod

    loads: list[int] = []
    original = places_mod._Index.load.__func__

    def wrapped(cls, session):
        loads.append(1)
        return original(cls, session)

    monkeypatch.setattr(places_mod._Index, "load", classmethod(wrapped))
    annotate(
        db_session,
        _org(db_session),
        [_location("1 Nathan Road"), _location("2 Nathan Road")],
        geocode=lambda _address: None,
    )
    assert loads == [1]


def test_a_matched_category_does_not_capture_other_wording(db_session) -> None:
    dance = ActivityCategory(name="Dance and ballet", display_order=1)
    db_session.add_all(
        [
            dance,
            ActivityCategory(
                id=PENDING_CATEGORY_ID,
                name="Pending categorisation",
                display_order=9,
            ),
        ]
    )
    db_session.flush()
    org = _org(db_session, review_status="pending_review")
    apply_one(
        db_session,
        org,
        _proposal(
            "create_activity",
            "Activities",
            {
                "name": "Beginner ballet",
                "category_name": "Dance and ballet",
                "category_words": "Ballet",
                "age_min": 6,
                "age_max": 12,
            },
        ),
        {},
        copy_image=None,
    )
    activity = db_session.scalars(select(Activity)).one()
    assert str(activity.category_id) == str(dance.id)
    assert db_session.scalars(select(CategorySuggestion)).all() == []


def test_unknown_wording_is_not_captured_when_imports_reject_it(db_session) -> None:
    db_session.add(ImportSettings(id=1, unknown_categories="fail"))
    db_session.flush()
    org = _org(db_session, review_status="pending_review")
    apply_one(
        db_session,
        org,
        _proposal(
            "create_activity",
            "Activities",
            {
                "name": "Beginner ballet",
                "category_words": "Ballet",
                "age_min": 6,
                "age_max": 12,
            },
        ),
        {},
        copy_image=None,
    )
    activity = db_session.scalars(select(Activity)).one()
    assert str(activity.category_id) == str(PENDING_CATEGORY_ID)
    assert db_session.scalars(select(CategorySuggestion)).all() == []


def test_apply_rejects_two_logos(db_session) -> None:
    org = _org(db_session)
    run = OrgEnrichmentRun(org_id=org.id, status="ready", seed_url=_PAGE)
    db_session.add(run)
    db_session.flush()
    rows = []
    for url, label in (
        ("https://cdn.example/site.jpg", "Logo"),
        ("https://cdn.example/facebook.jpg", "Logo · Facebook"),
    ):
        row = OrgEnrichmentProposal(
            run_id=run.id,
            org_id=org.id,
            section="Media",
            kind="add_media",
            field="logo",
            label=label,
            proposed_value={"source_url": url, "logo": True, "alt": label},
            confidence=Decimal("0.800"),
            evidence=[],
            proposed_hash=url,
        )
        db_session.add(row)
        rows.append(row)
    db_session.flush()
    results, _quality = apply_proposals(
        db_session,
        org.id,
        [str(row.id) for row in rows],
        {},
        user_id="admin",
        request_id="req-logos",
        copy_image=lambda url, _org_id: url,
    )
    assert [item["error"] for item in results] == ["Pick one logo", "Pick one logo"]
    assert org.logo_media_url in (None, "")


def test_extract_matches_a_catalog_category(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.enrichment.run.enqueue_enrichment",
        lambda run_id, *, stage: None,
    )
    dance = ActivityCategory(
        name="Dance and ballet",
        name_translations={"zh": "舞蹈芭蕾"},
        display_order=1,
    )
    db_session.add(dance)
    db_session.flush()
    org = _org(db_session, website="https://club.test")
    quote = "Beginner ballet classes for children every Saturday morning."
    pages = [
        {
            "url": "https://club.test/",
            "final_url": "https://club.test/",
            "text": quote,
            "jsonld_raw": [],
            "og": {},
            "images": [],
            "links": [],
            "icons": [],
        }
    ]

    def complete(prompt: str):
        assert "Dance and ballet (舞蹈芭蕾)" in prompt
        assert "before the parentheses" in prompt
        evidence = [{"url": "https://club.test/", "quote": quote}]
        sheet = {
            "activities": [
                {
                    "name": {
                        "value": "Beginner ballet",
                        "confidence": 0.9,
                        "evidence": evidence,
                    },
                    "category_name": {
                        "value": "Dance and ballet (舞蹈芭蕾)",
                        "confidence": 0.9,
                        "evidence": evidence,
                    },
                }
            ]
        }
        return sheet, Decimal("0.01"), "test/model"

    run = OrgEnrichmentRun(
        org_id=org.id, status="queued", seed_url="https://club.test/"
    )
    db_session.add(run)
    db_session.flush()
    process_enrichment(
        db_session,
        run.id,
        "m-crawl",
        receive_count=1,
        stage="crawl",
        crawl=lambda _row, _settings: {
            "status": "ok",
            "pages": pages,
            "pages_fetched": 1,
        },
        complete=complete,
    )
    process_enrichment(
        db_session,
        run.id,
        "m-extract",
        receive_count=1,
        stage="extract",
        complete=complete,
    )
    saved = db_session.scalars(
        select(OrgEnrichmentProposal).where(OrgEnrichmentProposal.run_id == run.id)
    ).all()
    activity = next(row for row in saved if row.kind == "create_activity")
    assert activity.proposed_value["category_id"] == str(dance.id)


def _activity(category_name: str) -> dict:
    return {
        "section": "Activities",
        "kind": "create_activity",
        "field": None,
        "label": "Activity",
        "proposed": {"name": "Beginner class", "category_name": category_name},
    }


def _name(value: str) -> dict:
    return {
        "section": "Organization",
        "kind": "update_organization",
        "field": "name",
        "label": "Name",
        "proposed": {"name": value},
    }


def _proposal(
    kind: str, section: str, proposed: dict, **fields
) -> OrgEnrichmentProposal:
    return OrgEnrichmentProposal(
        run_id="00000000-0000-0000-0000-000000000001",
        org_id="00000000-0000-0000-0000-000000000002",
        section=section,
        kind=kind,
        label=kind,
        proposed_value=proposed,
        confidence=Decimal("0.900"),
        evidence=[],
        proposed_hash=kind,
        **fields,
    )
