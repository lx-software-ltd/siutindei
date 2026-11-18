"""Pricing resource handlers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.api.admin_request import _parse_uuid
from app.api.admin_validators import _validate_currency
from app.db.models import ActivityPricing, PricingType
from app.db.models.enums import FREE_TRIAL_PRICING_TYPES
from app.db.repositories import ActivityPricingRepository
from app.exceptions import ValidationError


def _create_pricing(
    repo: ActivityPricingRepository, body: dict[str, Any]
) -> ActivityPricing:
    """Create activity pricing."""
    activity_id = body.get("activity_id")
    location_id = body.get("location_id")
    pricing_type = body.get("pricing_type")
    if not activity_id or not location_id or not pricing_type:
        raise ValidationError("activity_id, location_id, and pricing_type are required")

    pricing_enum = PricingType(pricing_type)
    amount = body.get("amount")
    if pricing_enum == PricingType.FREE:
        amount_value = Decimal("0")
        currency = _validate_currency("HKD")
    else:
        if amount is None:
            raise ValidationError(
                "amount is required unless pricing_type is free",
                field="amount",
            )
        _validate_pricing_amount(amount)
        amount_value = Decimal(str(amount))
        currency = _validate_currency(body.get("currency") or "HKD")
    amount_max = _amount_max_value(body.get("amount_max"), amount_value, pricing_enum)
    free_trial_class_offered = body.get("free_trial_class_offered", False)
    if not isinstance(free_trial_class_offered, bool):
        raise ValidationError(
            "free_trial_class_offered must be a boolean",
            field="free_trial_class_offered",
        )

    sessions_count = body.get("sessions_count")
    if pricing_enum == PricingType.PER_SESSIONS:
        if sessions_count is None:
            raise ValidationError("sessions_count is required for per_sessions pricing")
        _validate_sessions_count(sessions_count)
    else:
        sessions_count = None
    if pricing_enum not in FREE_TRIAL_PRICING_TYPES:
        free_trial_class_offered = False

    return ActivityPricing(
        activity_id=_parse_uuid(activity_id),
        location_id=_parse_uuid(location_id),
        pricing_type=pricing_enum,
        amount=amount_value,
        amount_max=amount_max,
        currency=currency,
        sessions_count=sessions_count,
        free_trial_class_offered=free_trial_class_offered,
    )


def _update_pricing(
    repo: ActivityPricingRepository,
    entity: ActivityPricing,
    body: dict[str, Any],
) -> ActivityPricing:
    """Update activity pricing."""
    del repo
    if "pricing_type" in body:
        entity.pricing_type = PricingType(body["pricing_type"])
    pricing_type = entity.pricing_type
    if pricing_type == PricingType.FREE:
        entity.amount = Decimal("0")
        entity.currency = _validate_currency("HKD")
        entity.amount_max = _amount_max_value(
            body.get("amount_max"), entity.amount, pricing_type
        )
    else:
        if "amount" in body:
            _validate_pricing_amount(body["amount"])
            entity.amount = Decimal(str(body["amount"]))
        if "currency" in body:
            entity.currency = _validate_currency(body["currency"])
        if "amount_max" in body:
            entity.amount_max = _amount_max_value(
                body.get("amount_max"), entity.amount, pricing_type
            )
        elif (
            "amount" in body
            and entity.amount_max is not None
            and entity.amount_max <= entity.amount
        ):
            # The new lower bound no longer fits the stored ceiling, and
            # this write did not send a replacement. Keep one price.
            entity.amount_max = None
        elif entity.amount_max is not None and entity.amount_max <= entity.amount:
            raise ValidationError(
                "amount_max must be greater than amount",
                field="amount_max",
            )
    if "sessions_count" in body:
        if body["sessions_count"] is not None:
            _validate_sessions_count(body["sessions_count"])
        entity.sessions_count = body["sessions_count"]
    if "free_trial_class_offered" in body:
        free_trial_class_offered = body["free_trial_class_offered"]
        if not isinstance(free_trial_class_offered, bool):
            raise ValidationError(
                "free_trial_class_offered must be a boolean",
                field="free_trial_class_offered",
            )
        entity.free_trial_class_offered = free_trial_class_offered
    if pricing_type != PricingType.PER_SESSIONS:
        entity.sessions_count = None
    if pricing_type not in FREE_TRIAL_PRICING_TYPES:
        entity.free_trial_class_offered = False
    return entity


def _amount_max_value(
    value: Any, amount: Decimal, pricing_type: PricingType
) -> Decimal | None:
    """Upper bound, or None when the fee is a single price.

    An empty value clears the bound. ``free`` rejects a bound. Any other
    bound must be a number above ``amount``.
    """
    if value is None or value == "":
        return None
    if pricing_type == PricingType.FREE:
        raise ValidationError(
            "free pricing has no upper bound",
            field="amount_max",
        )
    try:
        upper = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(
            "amount_max must be a valid number",
            field="amount_max",
        ) from exc
    if not upper.is_finite() or upper < 0:
        raise ValidationError(
            "amount_max must be at least 0",
            field="amount_max",
        )
    if upper <= amount:
        raise ValidationError(
            "amount_max must be greater than amount",
            field="amount_max",
        )
    return upper


def _validate_pricing_amount(amount: Any) -> None:
    """Validate pricing amount."""
    try:
        amount_val = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(
            "amount must be a valid number",
            field="amount",
        ) from exc

    if amount_val < 0:
        raise ValidationError(
            "amount must be at least 0",
            field="amount",
        )


def _validate_sessions_count(sessions_count: Any) -> None:
    """Validate sessions count."""
    try:
        count = int(sessions_count)
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            "sessions_count must be a valid integer",
            field="sessions_count",
        ) from exc

    if count <= 0:
        raise ValidationError(
            "sessions_count must be greater than 0",
            field="sessions_count",
        )


def _serialize_pricing(entity: ActivityPricing) -> dict[str, Any]:
    """Serialize pricing."""
    return {
        "id": str(entity.id),
        "activity_id": str(entity.activity_id),
        "location_id": str(entity.location_id),
        "pricing_type": entity.pricing_type.value,
        "amount": entity.amount,
        "amount_max": entity.amount_max,
        "currency": entity.currency,
        "sessions_count": entity.sessions_count,
        "free_trial_class_offered": entity.free_trial_class_offered,
        "version": entity.version,
    }
