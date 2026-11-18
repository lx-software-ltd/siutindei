"""A free trial class is stored on per-class, per-term, and monthly prices."""

from __future__ import annotations

from app.api.admin_resource_pricing import _create_pricing, _update_pricing
from app.db.models import ActivityPricing, PricingType
from app.db.models.enums import FREE_TRIAL_PRICING_TYPES
from app.db.repositories import ActivityPricingRepository
from app.services.enrichment.apply_rows import _apply_pricing
from sqlalchemy import select


def _body(
    sample_activity,
    sample_location,
    pricing_type: str,
    *,
    offered: bool = True,
    **extra: object,
) -> dict:
    body: dict = {
        "activity_id": str(sample_activity.id),
        "location_id": str(sample_location.id),
        "pricing_type": pricing_type,
        "amount": "200",
        "currency": "HKD",
        "free_trial_class_offered": offered,
    }
    body.update(extra)
    return body


def test_free_trial_is_stored_for_class_term_and_month(
    db_session, sample_activity, sample_location
) -> None:
    repo = ActivityPricingRepository(db_session)
    stored = {
        pricing_type: _create_pricing(
            repo,
            _body(
                sample_activity,
                sample_location,
                pricing_type,
                sessions_count=8 if pricing_type == "per_sessions" else None,
            ),
        ).free_trial_class_offered
        for pricing_type in (
            "per_class",
            "per_sessions",
            "per_month",
            "per_hour",
            "per_day",
            "per_year",
            "free",
        )
    }
    assert stored["per_class"] is True
    assert stored["per_sessions"] is True
    assert stored["per_month"] is True
    assert stored["per_hour"] is False
    assert stored["per_day"] is False
    assert stored["per_year"] is False
    assert stored["free"] is False


def test_switching_type_keeps_or_clears_the_tick(
    db_session, sample_activity, sample_location
) -> None:
    repo = ActivityPricingRepository(db_session)
    row = _create_pricing(
        repo,
        _body(
            sample_activity,
            sample_location,
            "per_sessions",
            sessions_count=8,
        ),
    )
    _update_pricing(repo, row, {"pricing_type": "per_class"})
    assert row.pricing_type == PricingType.PER_CLASS
    assert row.sessions_count is None
    assert row.free_trial_class_offered is True

    _update_pricing(repo, row, {"pricing_type": "per_month"})
    assert row.free_trial_class_offered is True

    _update_pricing(repo, row, {"pricing_type": "per_hour"})
    assert row.sessions_count is None
    assert row.free_trial_class_offered is False


def test_update_can_tick_a_per_class_price(
    db_session, sample_activity, sample_location
) -> None:
    repo = ActivityPricingRepository(db_session)
    row = _create_pricing(
        repo,
        _body(sample_activity, sample_location, "per_class", offered=False),
    )
    assert row.free_trial_class_offered is False
    _update_pricing(repo, row, {"free_trial_class_offered": True})
    assert row.free_trial_class_offered is True
    _update_pricing(repo, row, {"amount": "240"})
    assert row.free_trial_class_offered is True


def test_enrichment_apply_uses_the_same_allowlist(
    db_session, sample_activity, sample_location
) -> None:
    org = sample_activity.organization
    override = {
        "activity_id": str(sample_activity.id),
        "location_id": str(sample_location.id),
    }
    for pricing_type in ("per_class", "per_month", "per_hour"):
        _apply_pricing(
            db_session,
            org,
            {
                "activity_name": sample_activity.name,
                "pricing_type": pricing_type,
                "amount": "90",
                "currency": "HKD",
                "free_trial_class_offered": True,
            },
            override,
        )
    db_session.flush()
    rows = db_session.scalars(select(ActivityPricing)).all()
    stored = {row.pricing_type: row.free_trial_class_offered for row in rows}
    assert stored[PricingType.PER_CLASS] is True
    assert stored[PricingType.PER_MONTH] is True
    assert stored[PricingType.PER_HOUR] is False
    assert FREE_TRIAL_PRICING_TYPES == frozenset(
        {
            PricingType.PER_CLASS,
            PricingType.PER_SESSIONS,
            PricingType.PER_MONTH,
        }
    )
