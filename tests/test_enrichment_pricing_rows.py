"""Term prices keep their class count, and a reviewer can supply it."""

from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.db.models import (
    Activity,
    ActivityCategory,
    ActivityPricing,
    GeographicArea,
    Location,
)
from app.db.models.audit_log import AuditLog
from app.db.models.enums import PricingType
from app.db.models.import_settings import DataQualityRun
from app.db.models.org_enrichment import OrgEnrichmentProposal, OrgEnrichmentRun
from app.services.enrichment.apply import apply_proposals
from app.services.enrichment.extract import validate_model_sheet
from app.services.enrichment.match import prepare_proposals
from app.services.enrichment.row_blockers import (
    SESSIONS_REQUIRED,
    blocker_context,
    row_blockers,
)
from app.services.enrichment.store import serialize_proposal
from psycopg.types.range import Range
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tests.test_partner_org_enrichment import _cleanup, _enrich, _org, _patch_engines


def test_sheet_keeps_sessions_and_a_monthly_price() -> None:
    page = "https://club.test/fall-term"
    text = "Painting Workshops. Fee: HK$500 for 8 classes. Monthly plan HK$800."
    pages = [{"url": page, "final_url": page, "text": text}]
    sheet = {
        "pricing": [
            {
                "activity_name": "Painting Workshops",
                "pricing_type": "per_sessions",
                "sessions_count": 8,
                "amount": "500",
                "currency": "HKD",
                "confidence": 0.8,
                "evidence": [{"url": page, "quote": "Fee: HK$500 for 8 classes"}],
            },
            {
                "activity_name": "Painting Workshops",
                "pricing_type": "per_month",
                "amount": "800",
                "currency": "HKD",
                "confidence": 0.8,
                "evidence": [{"url": page, "quote": "Monthly plan HK$800"}],
            },
            {
                "activity_name": "Painting Workshops",
                "pricing_type": "per_term",
                "amount": "900",
                "currency": "HKD",
                "confidence": 0.8,
                "evidence": [{"url": page, "quote": "Fee: HK$500 for 8 classes"}],
            },
        ]
    }
    rows = [
        item["proposed"]
        for item in validate_model_sheet(sheet, pages, {})
        if item["kind"] == "create_pricing"
    ]
    assert rows[0]["sessions_count"] == 8
    assert rows[0]["pricing_type"] == "per_sessions"
    assert "sessions_count" not in rows[1]
    assert rows[1]["pricing_type"] == "per_month"
    assert rows[2]["pricing_type"] == "per_class"


def test_pending_activity_is_enough_for_the_price_note() -> None:
    activity = SimpleNamespace(
        status="pending",
        kind="create_activity",
        proposed_value={"name": "Painting Workshops"},
    )
    price = {
        "activity_name": "Painting Workshops",
        "pricing_type": "per_sessions",
        "amount": "500",
        "currency": "HKD",
        "location_address": "",
    }
    names, venues = blocker_context([activity], [], [])
    blockers = row_blockers(
        "create_pricing",
        price,
        status="pending",
        activity_names=names,
        venues=venues,
    )
    assert [item["field"] for item in blockers] == ["location_id", "sessions_count"]
    assert blockers[1]["message"] == SESSIONS_REQUIRED


def test_one_venue_and_a_class_count_leave_no_blocker(sample_location) -> None:
    blockers = row_blockers(
        "create_pricing",
        {
            "activity_name": "Swimming Class",
            "pricing_type": "per_class",
            "amount": "120",
            "currency": "HKD",
            "location_address": "",
        },
        status="pending",
        activity_names=["Swimming Class"],
        venues=[sample_location],
    )
    assert blockers == []
    schedule = row_blockers(
        "create_schedule",
        {"activity_name": "Missing", "location_address": ""},
        status="pending",
        activity_names=["Swimming Class"],
        venues=[sample_location],
    )
    assert schedule[0]["field"] == "activity_name"


def test_term_price_applies_from_the_override(
    db_session, sample_activity, sample_location
) -> None:
    org = sample_activity.organization
    run = OrgEnrichmentRun(org_id=org.id, status="ready", seed_url="https://ok.test/")
    db_session.add(run)
    db_session.flush()
    pricing = OrgEnrichmentProposal(
        run_id=run.id,
        org_id=org.id,
        section="Pricing",
        kind="create_pricing",
        label="Price · Swimming Class",
        proposed_value={
            "activity_name": "Swimming Class",
            "pricing_type": "per_sessions",
            "amount": "500",
            "currency": "USD",
            "location_address": "",
        },
        confidence=Decimal("0.500"),
        evidence=[],
        proposed_hash=uuid4().hex,
    )
    db_session.add(pricing)
    db_session.flush()
    payload = serialize_proposal(
        pricing,
        organization=org,
        venues=[sample_location],
        activity_names=[sample_activity.name],
    )
    assert payload["blockers"] == [
        {"field": "sessions_count", "message": SESSIONS_REQUIRED}
    ]
    refused, _quality = apply_proposals(
        db_session,
        org.id,
        [str(pricing.id)],
        {},
        user_id="admin",
        request_id="req-price",
    )
    assert refused[0]["status"] == "error"
    assert refused[0]["error"] == SESSIONS_REQUIRED
    assert pricing.status == "pending"
    applied, _quality = apply_proposals(
        db_session,
        org.id,
        [str(pricing.id)],
        {str(pricing.id): {"sessions_count": 8, "currency": "HKD"}},
        user_id="admin",
        request_id="req-price-2",
    )
    assert applied[0]["status"] == "applied"
    assert pricing.proposed_value["currency"] == "USD"
    assert "sessions_count" not in pricing.proposed_value
    row = db_session.scalars(select(ActivityPricing)).one()
    assert row.pricing_type == PricingType.PER_SESSIONS
    assert row.sessions_count == 8
    assert row.currency == "HKD"
    assert row.amount == Decimal("500.00")


def test_a_different_class_count_is_still_proposed(
    db_session, sample_activity, sample_location, sample_pricing
) -> None:
    org = sample_activity.organization
    sample_pricing.pricing_type = PricingType.PER_SESSIONS
    sample_pricing.sessions_count = 8
    sample_pricing.amount = Decimal("500.00")
    db_session.flush()
    kept = prepare_proposals(
        db_session,
        org,
        [
            {
                "section": "Pricing",
                "kind": "create_pricing",
                "label": "Price",
                "proposed": {
                    "activity_name": sample_activity.name,
                    "location_address": sample_location.address,
                    "pricing_type": "per_sessions",
                    "amount": "500",
                    "currency": "HKD",
                    "sessions_count": 12,
                },
            }
        ],
    )
    assert len(kept) == 1


def test_partner_apply_accepts_a_term_length(monkeypatch, test_engine) -> None:
    _patch_engines(monkeypatch, test_engine)
    monkeypatch.setattr(
        "app.services.data_quality.runs.enqueue_staged_run", lambda run_id: None
    )
    token = uuid4().hex[:8]
    with Session(test_engine) as session:
        org = _org(session, f"Harbour Club {token}")
        area = GeographicArea(name=f"Harbour {token}", level="district", active=True)
        category = ActivityCategory(name=f"Art {token}", display_order=0)
        session.add_all([area, category])
        session.flush()
        session.add(Location(org_id=org.id, area_id=area.id, address="1 Harbour Road"))
        session.add(
            Activity(
                org_id=org.id,
                category_id=category.id,
                name="Painting Workshops",
                age_range=Range(1, 18, bounds="[]"),
            )
        )
        run = OrgEnrichmentRun(
            org_id=org.id, status="ready", seed_url="https://ok.test/", source="leaflet"
        )
        session.add(run)
        session.flush()
        proposal = OrgEnrichmentProposal(
            run_id=run.id,
            org_id=org.id,
            section="Pricing",
            kind="create_pricing",
            label="Price · Painting Workshops",
            proposed_value={
                "activity_name": "Painting Workshops",
                "pricing_type": "per_sessions",
                "amount": "500",
                "currency": "USD",
                "location_address": "",
            },
            confidence=Decimal("0.500"),
            evidence=[],
            proposed_hash=uuid4().hex,
        )
        session.add(proposal)
        session.commit()
        org_id = org.id
        proposal_id = proposal.id
        area_id = area.id
        category_id = category.id
    try:
        read = _enrich(org_id, "GET")
        body = json.loads(read["body"])
        assert body["proposals"][0]["blockers"][0]["message"] == SESSIONS_REQUIRED
        missing = _enrich(
            org_id,
            "POST",
            "/apply",
            body={"ids": [str(proposal_id)], "overrides": {}},
        )
        refused = json.loads(missing["body"])["results"][0]
        assert refused["error"] == SESSIONS_REQUIRED
        saved = _enrich(
            org_id,
            "POST",
            "/apply",
            body={
                "ids": [str(proposal_id)],
                "overrides": {
                    str(proposal_id): {"sessions_count": 8, "currency": "HKD"}
                },
            },
        )
        assert json.loads(saved["body"])["results"][0]["status"] == "applied"
        with Session(test_engine) as session:
            row = session.scalars(
                select(ActivityPricing)
                .join(Activity, ActivityPricing.activity_id == Activity.id)
                .where(Activity.org_id == org_id)
            ).one()
            assert row.sessions_count == 8
            assert row.currency == "HKD"
    finally:
        with Session(test_engine) as session:
            session.execute(delete(Activity).where(Activity.org_id == org_id))
            session.execute(delete(Location).where(Location.org_id == org_id))
            session.execute(
                delete(ActivityCategory).where(ActivityCategory.id == category_id)
            )
            session.execute(delete(GeographicArea).where(GeographicArea.id == area_id))
            session.execute(
                delete(DataQualityRun).where(
                    DataQualityRun.scope.contains({"organization_ids": [str(org_id)]})
                )
            )
            session.execute(delete(AuditLog).where(AuditLog.record_id == str(org_id)))
            session.commit()
        _cleanup(test_engine, org_id)
