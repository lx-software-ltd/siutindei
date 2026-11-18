"""Why an enrichment price or schedule cannot be saved yet."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.api.admin_validators import _validate_currency
from app.db.models.enums import PricingType
from app.exceptions import ValidationError

PRICE_ACTIVITY = "Pick the activity this price belongs to"
PRICE_VENUE = "Pick a venue for this price"
SCHEDULE_ACTIVITY = "Pick the activity this schedule belongs to"
SCHEDULE_VENUE = "Pick a venue for this schedule"
SESSIONS_REQUIRED = "Add the number of classes for this term price"
AMOUNT_INVALID = "Amount must be a number"
AMOUNT_MAX_INVALID = "Upper bound must be a number above the amount"
FREE_HAS_NO_RANGE = "Free pricing has no upper bound"
TYPE_UNSUPPORTED = "Pricing type is not supported"
CURRENCY_INVALID = "Currency must be an ISO code"

PRICING_TYPES = frozenset(item.value for item in PricingType)


def positive_sessions(value: object) -> int | None:
    """A whole class count greater than zero, or nothing.

    ``12`` and ``12.0`` count. ``8.5``, ``1e1``, and ``12 classes`` do not.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if text == "" or "e" in text.lower():
            return None
        if text.isdigit():
            number = int(text)
            return number if number > 0 else None
        try:
            parsed = Decimal(text)
        except InvalidOperation:
            return None
        return _whole_positive(parsed)
    if isinstance(value, Decimal):
        return _whole_positive(value)
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        if not value.is_integer():
            return None
        return _whole_positive(Decimal(str(value)))
    return None


def _whole_positive(number: Decimal) -> int | None:
    if not number.is_finite() or number != number.to_integral_value() or number <= 0:
        return None
    return int(number)


def pricing_fields(
    proposed: dict[str, Any], override: dict[str, Any]
) -> dict[str, Any]:
    """Pricing columns, with the reviewer's override winning when set."""
    raw_type = str(_pick(override, proposed, "pricing_type") or "per_class")
    try:
        kind = PricingType(raw_type)
    except ValueError as exc:
        raise ValidationError(TYPE_UNSUPPORTED, field="pricing_type") from exc
    amount_raw = _pick(override, proposed, "amount")
    if amount_raw is None or amount_raw == "":
        amount_raw = "0"
    try:
        amount = Decimal(str(amount_raw))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(AMOUNT_INVALID, field="amount") from exc
    if not amount.is_finite() or amount < 0:
        raise ValidationError(AMOUNT_INVALID, field="amount")
    amount_max = _amount_max(override, proposed, kind, amount)
    currency_raw = _pick(override, proposed, "currency") or "HKD"
    try:
        currency = _validate_currency(str(currency_raw))
    except ValidationError as exc:
        raise ValidationError(CURRENCY_INVALID, field="currency") from exc
    sessions = None
    if kind == PricingType.PER_SESSIONS:
        sessions = positive_sessions(_pick(override, proposed, "sessions_count"))
        if sessions is None:
            raise ValidationError(SESSIONS_REQUIRED, field="sessions_count")
    return {
        "pricing_type": kind,
        "amount": amount,
        "amount_max": amount_max,
        "currency": currency,
        "sessions_count": sessions,
    }


def row_blockers(
    kind: str,
    proposed: dict[str, Any],
    *,
    status: str,
    activity_names: list[str],
    venues: list[Any],
) -> list[dict[str, str]]:
    """Reasons apply would refuse this pending price or schedule."""
    if status != "pending" or kind not in {"create_pricing", "create_schedule"}:
        return []
    blockers: list[dict[str, str]] = []
    if kind == "create_pricing":
        activity_message, venue_message = PRICE_ACTIVITY, PRICE_VENUE
    else:
        activity_message, venue_message = SCHEDULE_ACTIVITY, SCHEDULE_VENUE
    if not _known_name(proposed.get("activity_name"), activity_names):
        blockers.append({"field": "activity_name", "message": activity_message})
    if not _known_venue(proposed, venues):
        blockers.append({"field": "location_id", "message": venue_message})
    if kind == "create_pricing":
        blockers.extend(_pricing_blockers(proposed))
    return blockers


def _pricing_blockers(proposed: dict[str, Any]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    raw_type = str(proposed.get("pricing_type") or "per_class")
    if raw_type not in PRICING_TYPES:
        found.append({"field": "pricing_type", "message": TYPE_UNSUPPORTED})
    raw_amount = proposed.get("amount")
    amount: Decimal | None = None
    if raw_amount not in (None, ""):
        try:
            amount = Decimal(str(raw_amount))
        except (InvalidOperation, ValueError):
            amount = None
        if amount is None or not amount.is_finite() or amount < 0:
            found.append({"field": "amount", "message": AMOUNT_INVALID})
            amount = None
    found.extend(_amount_max_blockers(proposed, raw_type, amount))
    if (
        raw_type == PricingType.PER_SESSIONS.value
        and positive_sessions(proposed.get("sessions_count")) is None
    ):
        found.append({"field": "sessions_count", "message": SESSIONS_REQUIRED})
    currency = proposed.get("currency") or "HKD"
    try:
        _validate_currency(str(currency))
    except ValidationError:
        found.append({"field": "currency", "message": CURRENCY_INVALID})
    return found


def _amount_max(
    override: dict[str, Any],
    proposed: dict[str, Any],
    kind: PricingType,
    amount: Decimal,
) -> Decimal | None:
    """Upper bound from the override, else the proposal.

    An empty override clears a proposed bound. ``free`` keeps none.
    """
    if "amount_max" in override:
        raw = override.get("amount_max")
    else:
        raw = proposed.get("amount_max")
    if raw in (None, ""):
        return None
    if kind == PricingType.FREE:
        raise ValidationError(FREE_HAS_NO_RANGE, field="amount_max")
    try:
        upper = Decimal(str(raw))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(AMOUNT_MAX_INVALID, field="amount_max") from exc
    if not upper.is_finite() or upper <= amount:
        raise ValidationError(AMOUNT_MAX_INVALID, field="amount_max")
    return upper


def _amount_max_blockers(
    proposed: dict[str, Any], raw_type: str, amount: Decimal | None
) -> list[dict[str, str]]:
    raw = proposed.get("amount_max")
    if raw in (None, ""):
        return []
    if raw_type == PricingType.FREE.value:
        return [{"field": "amount_max", "message": FREE_HAS_NO_RANGE}]
    try:
        upper = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        upper = None
    if amount is None or upper is None or not upper.is_finite() or upper <= amount:
        return [{"field": "amount_max", "message": AMOUNT_MAX_INVALID}]
    return []


def _pick(override: dict[str, Any], proposed: dict[str, Any], key: str) -> Any:
    if key in override:
        value = override[key]
        if value is not None and value != "":
            return value
    return proposed.get(key)


def _known_name(name: object, names: list[str]) -> bool:
    target = _folded(name)
    return bool(target) and any(_folded(item) == target for item in names)


def _known_venue(proposed: dict[str, Any], venues: list[Any]) -> bool:
    address = _folded(proposed.get("location_address"))
    if address and any(
        _folded(getattr(venue, "address", "")) == address for venue in venues
    ):
        return True
    return len(venues) == 1


def _folded(value: object) -> str:
    return " ".join(str(value or "").split()).casefold()
