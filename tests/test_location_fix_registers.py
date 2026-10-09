"""EDB school-register matches during a venue sweep."""

from __future__ import annotations

from app.db.models import (
    Activity,
    ActivityLocation,
    GeographicArea,
    Location,
    LocationFixProposal,
    Organization,
)
from app.services.aws_proxy import AwsProxyError
from app.services.location_fix_registers import (
    clear_edb_cache,
    edb_register,
    name_similarity,
    parse_edb_csv,
)
from app.services.location_fix_scan import start_location_scan
from psycopg.types.range import Range
from sqlalchemy import select

_MANAGER = "00000000-0000-0000-0000-000000000001"
_CSV = """SCHOOL NO.,ENGLISH NAME,中文名稱,ENGLISH ADDRESS,中文地址,LATITUDE,LONGITUDE,DISTRICT,ENGLISH CATEGORY,TELEPHONE
100000000001,HARBOUR KINDERGARTEN,海港幼稚園,8 HARBOUR ROAD,海港道8號,22.280,114.150,CENTRAL AND WESTERN,KINDERGARTEN,55550001
100000000002,HARBOUR KINDERGARTEN,海港幼稚園,9 HARBOUR ROAD,海港道9號,22.281,114.151,CENTRAL AND WESTERN,KINDERGARTEN,55550002
100000000003,HARBOUR KINDERGARTEN,海港幼稚園,10 HARBOUR ROAD,海港道10號,22.282,114.152,CENTRAL AND WESTERN,KINDERGARTEN,55550003
"""


def _register(monkeypatch) -> None:
    rows = parse_edb_csv(_CSV)
    monkeypatch.setattr(
        "app.services.location_fix_registers.edb_register",
        lambda: rows,
    )


def _org(db_session, name: str, source_id: str | None) -> Organization:
    org = Organization(
        name=name,
        manager_id=_MANAGER,
        review_status="pending_review",
        source="edb" if source_id else None,
        source_id=source_id,
    )
    db_session.add(org)
    db_session.flush()
    return org


def _activity(db_session, org, category) -> Activity:
    activity = Activity(
        org_id=org.id,
        category_id=category.id,
        name="Harbour Class",
        age_range=Range(3, 6, bounds="[]"),
    )
    db_session.add(activity)
    db_session.flush()
    return activity


def test_parse_drops_phones_and_pins_outside_hong_kong() -> None:
    rows = parse_edb_csv(
        _CSV
        + "100000000009,FAR SCHOOL,,1 Other Road,,39.9,116.4,CENTRAL AND WESTERN,KINDERGARTEN,55550009\n"
    )
    assert set(rows) == {"100000000001", "100000000002", "100000000003"}
    assert "telephone" not in rows["100000000001"]
    assert "55550001" not in str(rows["100000000001"])


def test_register_similarity_bands() -> None:
    assert name_similarity("Harbour Kindergarten", "HARBOUR KINDERGARTEN") == 1
    annex = name_similarity("Harbour Kindergarten Annex", "HARBOUR KINDERGARTEN")
    assert 0.8 <= annex < 0.95
    assert name_similarity("Harbour", "HARBOUR KINDERGARTEN") < 0.8


def test_confident_register_match_creates_the_venue(
    db_session, monkeypatch, sample_activity_category
) -> None:
    _register(monkeypatch)
    db_session.add(
        GeographicArea(name="Central and Western", level="district", active=True)
    )
    org = _org(db_session, "Harbour Kindergarten", "100000000001")
    activity = _activity(db_session, org, sample_activity_category)
    db_session.flush()
    result, batches = start_location_scan(
        db_session, review_scope="pending_review", org_id=org.id
    )
    assert result["auto_applied"] == 1
    assert batches == []
    proposal = db_session.scalars(
        select(LocationFixProposal).where(LocationFixProposal.org_id == org.id)
    ).one()
    assert proposal.status == "applied"
    assert proposal.source == "rule:open_data"
    venue = db_session.scalars(select(Location).where(Location.org_id == org.id)).one()
    assert venue.address == "8 Harbour Road"
    assert venue.place_id is None
    assert db_session.get(ActivityLocation, (activity.id, venue.id)) is not None


def test_near_match_stays_pending(db_session, monkeypatch) -> None:
    _register(monkeypatch)
    db_session.add(
        GeographicArea(name="Central and Western", level="district", active=True)
    )
    org = _org(db_session, "Harbour Kindergarten Annex", "100000000002")
    db_session.flush()
    result, batches = start_location_scan(
        db_session, review_scope="pending_review", org_id=org.id
    )
    assert result["auto_applied"] == 0
    assert batches == []
    proposal = db_session.scalars(
        select(LocationFixProposal).where(LocationFixProposal.org_id == org.id)
    ).one()
    assert proposal.status == "pending"
    assert proposal.kind == "create_location"
    assert proposal.source == "rule:open_data"
    assert (
        db_session.scalars(select(Location).where(Location.org_id == org.id)).first()
        is None
    )


def test_low_similarity_is_left_for_the_model(db_session, monkeypatch) -> None:
    _register(monkeypatch)
    db_session.add(
        GeographicArea(name="Central and Western", level="district", active=True)
    )
    org = _org(db_session, "Harbour", "100000000003")
    db_session.flush()
    result, batches = start_location_scan(
        db_session, review_scope="pending_review", org_id=org.id
    )
    assert result["queued_for_model"] == 1
    assert batches[0]["entity_ids"] == [str(org.id)]
    rows = list(
        db_session.scalars(
            select(LocationFixProposal).where(LocationFixProposal.org_id == org.id)
        ).all()
    )
    assert rows == []


def test_auto_apply_cap_stores_the_rest_pending(
    db_session, monkeypatch, sample_activity_category
) -> None:
    monkeypatch.setattr("app.services.location_fix_registers._MAX_AUTO_APPLY", 1)
    monkeypatch.setattr(
        "app.services.location_fix_registers.name_similarity",
        lambda _left, _right: 1.0,
    )
    _register(monkeypatch)
    db_session.add(
        GeographicArea(name="Central and Western", level="district", active=True)
    )
    token = "Registercapfixture"
    first = _org(db_session, f"Aa {token} Harbour Kindergarten", "100000000001")
    second = _org(db_session, f"Bb {token} Harbour Kindergarten", "100000000001")
    activity = _activity(db_session, second, sample_activity_category)
    db_session.flush()
    result, _batches = start_location_scan(
        db_session, review_scope="pending_review", query=token
    )
    assert result["auto_applied"] == 1
    assert result["truncated"] is False
    activity_row = db_session.scalars(
        select(LocationFixProposal).where(LocationFixProposal.entity_id == activity.id)
    ).one()
    assert activity_row.source == "rule:no_venue"
    first_row = db_session.scalars(
        select(LocationFixProposal).where(LocationFixProposal.org_id == first.id)
    ).one()
    second_row = db_session.scalars(
        select(LocationFixProposal).where(
            LocationFixProposal.org_id == second.id,
            LocationFixProposal.entity_type == "organization",
        )
    ).one()
    assert first_row.status == "applied"
    assert second_row.status == "pending"
    assert second_row.source == "rule:open_data"


def test_create_budget_stores_a_confident_match_pending(
    db_session, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.services.location_fix_scan._SWEEP_CREATE_BUDGET_SECONDS",
        -1,
    )
    _register(monkeypatch)
    db_session.add(
        GeographicArea(name="Central and Western", level="district", active=True)
    )
    org = _org(db_session, "Harbour Kindergarten", "100000000001")
    db_session.flush()
    result, _batches = start_location_scan(
        db_session, review_scope="pending_review", org_id=org.id
    )
    assert result["auto_applied"] == 0
    assert result["truncated"] is False
    proposal = db_session.scalars(
        select(LocationFixProposal).where(LocationFixProposal.org_id == org.id)
    ).one()
    assert proposal.status == "pending"
    assert proposal.source == "rule:open_data"
    assert (
        db_session.scalars(select(Location).where(Location.org_id == org.id)).first()
        is None
    )


def test_failed_register_fetch_is_retried(monkeypatch) -> None:
    clear_edb_cache()
    calls = {"n": 0}

    def fake_invoke(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise AwsProxyError("Timeout", "timed out")
        return {"status": 200, "body": _CSV}

    monkeypatch.setattr("app.services.location_fix_registers.http_invoke", fake_invoke)
    try:
        assert edb_register() is None
        assert "100000000001" in edb_register()
        assert calls["n"] == 2
    finally:
        clear_edb_cache()


def test_register_outage_leaves_the_organization(db_session, monkeypatch) -> None:
    clear_edb_cache()

    def fake_invoke(*_args, **_kwargs):
        raise AwsProxyError("Timeout", "timed out")

    monkeypatch.setattr("app.services.location_fix_registers.http_invoke", fake_invoke)
    org = _org(db_session, "Harbour Kindergarten", "100000000001")
    db_session.flush()
    try:
        result, batches = start_location_scan(
            db_session, review_scope="pending_review", org_id=org.id
        )
    finally:
        clear_edb_cache()
    assert result["queued_for_model"] == 0
    assert result["error"] == "EDB school register could not be loaded"
    assert batches == []
    assert (
        db_session.scalars(
            select(LocationFixProposal).where(LocationFixProposal.org_id == org.id)
        ).first()
        is None
    )


def test_other_sources_do_not_fetch_the_register(
    db_session, monkeypatch, sample_activity_category
) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("register fetched")

    monkeypatch.setattr("app.services.location_fix_registers.http_invoke", boom)
    org = Organization(
        name="Harbour Club",
        manager_id=_MANAGER,
        review_status="pending_review",
    )
    db_session.add(org)
    db_session.flush()
    activity = Activity(
        org_id=org.id,
        category_id=sample_activity_category.id,
        name="Swim Class",
        age_range=Range(5, 12, bounds="[]"),
    )
    db_session.add(activity)
    db_session.flush()
    result, batches = start_location_scan(
        db_session, review_scope="pending_review", org_id=org.id
    )
    assert result["queued_for_model"] == 1
    assert batches
