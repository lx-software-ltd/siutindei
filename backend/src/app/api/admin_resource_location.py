"""Location resource handlers for admin APIs."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Literal, overload
from uuid import UUID

from app.api.admin_imports_catalog import parse_place_id
from app.api.admin_request import _parse_uuid
from app.api.admin_validators import (
    MAX_ADDRESS_LENGTH,
    MAX_NAME_LENGTH,
    _validate_string_length,
)
from app.db.models import Location
from app.db.repositories import LocationRepository
from app.exceptions import ValidationError
from app.services.area_assignment import get_leaf

LOCATION_STATUSES = (
    "open",
    "temporarily_closed",
    "permanently_closed",
)
DEFAULT_LOCATION_STATUS = "open"
CLOSED_LOCATION_STATUSES = ("temporarily_closed", "permanently_closed")
FROZEN_LOCATION_FIELDS = ("area_id", "address", "lat", "lng", "place_id")
_CLOSED_LOCATION_MESSAGE = "Closed locations keep their address, area, and map pin"


def location_is_closed(status: str | None) -> bool:
    """True when address, area, and the map pin must stay as stored."""
    return status in CLOSED_LOCATION_STATUSES


def _create_location(repo: LocationRepository, body: dict[str, Any]) -> Location:
    """Create a location."""
    org_id = body.get("org_id")
    if not org_id:
        raise ValidationError("org_id is required", field="org_id")

    area_id_raw = body.get("area_id")
    if not area_id_raw:
        raise ValidationError("area_id is required", field="area_id")
    area_uuid = _parse_uuid(area_id_raw)

    _require_leaf_area(repo._session, area_uuid)

    name = _validate_string_length(body.get("name"), "name", MAX_NAME_LENGTH)
    status = _parse_location_status(body.get("status")) or DEFAULT_LOCATION_STATUS
    address = _validate_string_length(
        body.get("address"), "address", MAX_ADDRESS_LENGTH
    )
    if address:
        _ensure_unique_location_address(
            repo, _parse_uuid(org_id), address, current_id=None
        )

    lat = body.get("lat")
    lng = body.get("lng")
    _validate_coordinates(lat, lng)

    return Location(
        org_id=_parse_uuid(org_id),
        area_id=area_uuid,
        name=name,
        status=status,
        address=address,
        lat=lat,
        lng=lng,
        place_id=parse_place_id(body.get("place_id")),
    )


def _update_location(
    repo: LocationRepository,
    entity: Location,
    body: dict[str, Any],
) -> Location:
    """Update a location.

    Admins and managers share this handler and may set status. A closed
    location, including one this request closes, keeps its address, area,
    coordinates, and place id.
    """
    next_status = _next_status(entity, body)
    if location_is_closed(next_status):
        reject_frozen_location_edits(entity, body)

    if "area_id" in body:
        area_uuid = _parse_uuid(body["area_id"])
        _require_leaf_area(repo._session, area_uuid)
        entity.area_id = area_uuid  # type: ignore[assignment]

    if "name" in body:
        entity.name = _validate_string_length(body["name"], "name", MAX_NAME_LENGTH)

    if "status" in body:
        entity.status = next_status

    if "address" in body:
        address = _validate_string_length(
            body["address"], "address", MAX_ADDRESS_LENGTH
        )
        if address:
            _ensure_unique_location_address(
                repo,
                _parse_uuid(str(entity.org_id)),
                address,
                current_id=str(entity.id),
            )
        entity.address = address

    lat = body.get("lat", entity.lat) if "lat" in body else entity.lat
    lng = body.get("lng", entity.lng) if "lng" in body else entity.lng

    if "lat" in body or "lng" in body:
        _validate_coordinates(lat, lng)

    if "lat" in body:
        entity.lat = body["lat"]
    if "lng" in body:
        entity.lng = body["lng"]
    if "place_id" in body:
        entity.place_id = parse_place_id(body.get("place_id"))
    return entity


def _next_status(entity: Location, body: dict[str, Any]) -> str:
    """Status after this update. A missing key keeps the stored value."""
    if "status" not in body:
        return entity.status
    return _parse_location_status(body.get("status"), required=True)


def reject_frozen_location_edits(entity: Location, body: dict[str, Any]) -> None:
    """Reject a change to address, area, or the map pin on a closed venue."""
    for field in FROZEN_LOCATION_FIELDS:
        if field not in body:
            continue
        if _frozen_field_matches(entity, field, body[field]):
            continue
        raise ValidationError(_CLOSED_LOCATION_MESSAGE, field=field)


def omit_frozen_location_edits(
    entity: Location,
    body: dict[str, Any],
    warnings: list[str] | None,
) -> None:
    """Drop frozen edits so a reimport of a closed venue still succeeds."""
    if not location_is_closed(entity.status):
        return
    removed = False
    for field in FROZEN_LOCATION_FIELDS:
        if field not in body or _frozen_field_matches(entity, field, body[field]):
            continue
        body.pop(field)
        removed = True
    if removed and warnings is not None:
        warnings.append("Closed location kept its address, area, and map pin.")


def _frozen_field_matches(entity: Location, field: str, value: Any) -> bool:
    current = getattr(entity, field)
    if field in {"lat", "lng"}:
        return _coords_equal(current, value)
    if field == "area_id":
        return str(current) == str(value).strip()
    return _blank_to_none(current) == _blank_to_none(value)


def _blank_to_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coords_equal(left: Any, right: Any) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    try:
        quantum = Decimal("0.000001")
        return Decimal(str(left)).quantize(quantum) == Decimal(str(right)).quantize(
            quantum
        )
    except (InvalidOperation, ValueError):
        return False


@overload
def _parse_location_status(value: Any, *, required: Literal[True]) -> str: ...


@overload
def _parse_location_status(
    value: Any, *, required: Literal[False] = False
) -> str | None: ...


def _parse_location_status(value: Any, *, required: bool = False) -> str | None:
    """Validate an optional location status. Blank is open on create."""
    if value is None or (isinstance(value, str) and value.strip() == ""):
        if required:
            raise ValidationError("status is required", field="status")
        return None
    status = str(value).strip()
    if status not in LOCATION_STATUSES:
        raise ValidationError("Invalid status", field="status")
    return status


def _require_leaf_area(session: Any, area_id: Any) -> None:
    """Reject a missing area or one that still has smaller areas under it."""
    if get_leaf(session, area_id) is None:
        raise ValidationError(
            "area_id must be a neighbourhood or other area with no smaller areas",
            field="area_id",
        )


def _validate_coordinates(lat: Any, lng: Any) -> None:
    """Validate latitude and longitude values."""
    if lat is not None:
        try:
            lat_val = float(lat)
            if not -90 <= lat_val <= 90:
                raise ValidationError(
                    "lat must be between -90 and 90",
                    field="lat",
                )
        except (ValueError, TypeError) as exc:
            raise ValidationError("lat must be a valid number", field="lat") from exc

    if lng is not None:
        try:
            lng_val = float(lng)
            if not -180 <= lng_val <= 180:
                raise ValidationError(
                    "lng must be between -180 and 180",
                    field="lng",
                )
        except (ValueError, TypeError) as exc:
            raise ValidationError("lng must be a valid number", field="lng") from exc


def _ensure_unique_location_address(
    repo: LocationRepository,
    org_id: str | UUID,
    address: str,
    current_id: str | None,
) -> None:
    """Ensure location address is unique within an organization."""
    existing = repo.find_by_org_and_address_case_insensitive(
        _parse_uuid(str(org_id)),
        address,
    )
    if existing is None:
        return
    if current_id is not None and str(existing.id) == str(current_id):
        return
    raise ValidationError(
        "Location address already exists for organization",
        field="address",
    )


def _serialize_location(entity: Location) -> dict[str, Any]:
    """Serialize a location."""
    return {
        "id": str(entity.id),
        "org_id": str(entity.org_id),
        "area_id": str(entity.area_id),
        "name": entity.name,
        "status": entity.status,
        "address": entity.address,
        "lat": entity.lat,
        "lng": entity.lng,
        "place_id": entity.place_id,
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
        "version": entity.version,
    }
