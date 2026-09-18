"""Location resource handlers for admin APIs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.api.admin_imports_catalog import parse_place_id
from app.api.admin_request import _parse_uuid
from app.api.admin_validators import MAX_ADDRESS_LENGTH, _validate_string_length
from app.db.models import Location
from app.db.repositories import GeographicAreaRepository, LocationRepository
from app.exceptions import ValidationError


def _create_location(repo: LocationRepository, body: dict[str, Any]) -> Location:
    """Create a location."""
    org_id = body.get("org_id")
    if not org_id:
        raise ValidationError("org_id is required", field="org_id")

    area_id_raw = body.get("area_id")
    if not area_id_raw:
        raise ValidationError("area_id is required", field="area_id")
    area_uuid = _parse_uuid(area_id_raw)

    # Validate area_id exists
    geo_repo = GeographicAreaRepository(repo._session)
    if geo_repo.get_by_id(area_uuid) is None:
        raise ValidationError("area_id not found", field="area_id")

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
    """Update a location."""
    if "area_id" in body:
        area_uuid = _parse_uuid(body["area_id"])
        geo_repo = GeographicAreaRepository(repo._session)
        if geo_repo.get_by_id(area_uuid) is None:
            raise ValidationError("area_id not found", field="area_id")
        entity.area_id = area_uuid  # type: ignore[assignment]

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
        "address": entity.address,
        "lat": entity.lat,
        "lng": entity.lng,
        "place_id": entity.place_id,
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
    }
