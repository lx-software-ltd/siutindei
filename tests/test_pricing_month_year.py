"""Monthly and yearly prices are stored as their own pricing types."""

from __future__ import annotations

from decimal import Decimal

from app.api.admin_resource_pricing import _create_pricing
from app.db.models import PricingType
from app.db.repositories import ActivityPricingRepository


def test_create_monthly_and_yearly_prices(
    db_session, sample_activity, sample_location
) -> None:
    repo = ActivityPricingRepository(db_session)
    monthly = _create_pricing(
        repo,
        {
            "activity_id": str(sample_activity.id),
            "location_id": str(sample_location.id),
            "pricing_type": "per_month",
            "amount": "3800",
            "currency": "HKD",
        },
    )
    yearly = _create_pricing(
        repo,
        {
            "activity_id": str(sample_activity.id),
            "location_id": str(sample_location.id),
            "pricing_type": "per_year",
            "amount": "35000",
            "currency": "hkd",
        },
    )
    repo.create(monthly)
    repo.create(yearly)
    db_session.flush()
    assert monthly.pricing_type == PricingType.PER_MONTH
    assert monthly.amount == Decimal(3800)
    assert monthly.sessions_count is None
    assert yearly.pricing_type == PricingType.PER_YEAR
    assert yearly.amount == Decimal(35000)
    assert yearly.currency == "HKD"
