"""Organization resource handlers for admin APIs."""

from __future__ import annotations

from typing import Any, Optional

from app.api.admin_imports_catalog import (
    apply_listing_status,
    parse_description_source,
    parse_org_status,
    parse_place_id,
    parse_status_source,
)
from app.api.admin_validators import (
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    SOCIAL_FIELDS,
    _parse_media_urls,
    _validate_email,
    _validate_logo_media_url,
    _validate_manager_id,
    _validate_media_urls,
    _validate_phone_fields,
    _validate_social_value,
    _validate_string_length,
    _validate_translations_map,
)
from app.db.models import Organization
from app.db.repositories import OrganizationRepository
from app.exceptions import ValidationError
from app.utils.translations import build_translation_map


def _parse_organization_contact_fields(body: dict[str, Any]) -> dict[str, Any]:
    """Parse organization contact fields."""
    phone_country_code, phone_number = _validate_phone_fields(
        body.get("phone_country_code"),
        body.get("phone_number"),
    )
    return {
        "phone_country_code": phone_country_code,
        "phone_number": phone_number,
        "email": _validate_email(body.get("email")),
        "whatsapp": _validate_social_value(body.get("whatsapp"), "whatsapp"),
        "facebook": _validate_social_value(body.get("facebook"), "facebook"),
        "instagram": _validate_social_value(body.get("instagram"), "instagram"),
        "tiktok": _validate_social_value(body.get("tiktok"), "tiktok"),
        "twitter": _validate_social_value(body.get("twitter"), "twitter"),
        "xiaohongshu": _validate_social_value(
            body.get("xiaohongshu"),
            "xiaohongshu",
        ),
        "wechat": _validate_social_value(body.get("wechat"), "wechat"),
    }


def _apply_organization_contact_fields(
    entity: Organization,
    body: dict[str, Any],
) -> None:
    """Apply organization contact updates."""
    if "phone_country_code" in body or "phone_number" in body:
        country_code = body.get("phone_country_code", entity.phone_country_code)
        number = body.get("phone_number", entity.phone_number)
        country_code, number = _validate_phone_fields(country_code, number)
        entity.phone_country_code = country_code
        entity.phone_number = number
    if "email" in body:
        entity.email = _validate_email(body["email"])
    for field in SOCIAL_FIELDS:
        if field in body:
            setattr(
                entity,
                field,
                _validate_social_value(body[field], field),
            )


def _ensure_unique_organization_name(
    repo: OrganizationRepository,
    name: str,
    current_id: str | None = None,
) -> None:
    """Ensure organization name is unique (case-insensitive)."""
    existing = repo.find_by_name_case_insensitive(name)
    if existing is None:
        return
    if current_id is not None and str(existing.id) == str(current_id):
        return
    raise ValidationError("Organization name already exists", field="name")


def _update_organization_for_manager(
    repo: OrganizationRepository,
    entity: Organization,
    body: dict[str, Any],
) -> Organization:
    """Update an organization for a manager (limited fields)."""
    if "name" in body:
        name = _validate_string_length(
            body["name"], "name", MAX_NAME_LENGTH, required=True
        )
        if name is None:
            raise ValidationError("name is required", field="name")
        _ensure_unique_organization_name(repo, name, current_id=str(entity.id))
        entity.name = name  # type: ignore[assignment]
    if "description" in body:
        entity.description = _validate_string_length(
            body["description"], "description", MAX_DESCRIPTION_LENGTH
        )
    if "name_translations" in body:
        entity.name_translations = _validate_translations_map(
            body["name_translations"],
            "name_translations",
            MAX_NAME_LENGTH,
        )
    if "description_translations" in body:
        entity.description_translations = _validate_translations_map(
            body["description_translations"],
            "description_translations",
            MAX_DESCRIPTION_LENGTH,
        )
    updated_media_urls: Optional[list[str]] = None
    if "media_urls" in body:
        updated_media_urls = _parse_media_urls(body["media_urls"])
        if updated_media_urls:
            updated_media_urls = _validate_media_urls(updated_media_urls)
        entity.media_urls = updated_media_urls
    media_urls_for_logo = (
        updated_media_urls
        if updated_media_urls is not None
        else list(entity.media_urls or [])
    )
    if "logo_media_url" in body:
        entity.logo_media_url = _validate_logo_media_url(
            body.get("logo_media_url"),
            media_urls_for_logo,
        )
    elif updated_media_urls is not None:
        if entity.logo_media_url and entity.logo_media_url not in media_urls_for_logo:
            entity.logo_media_url = None
    _apply_organization_contact_fields(entity, body)
    _apply_organization_listing_fields(repo, entity, body)
    return entity


def _create_organization(
    repo: OrganizationRepository, body: dict[str, Any]
) -> Organization:
    """Create an organization."""
    name = _validate_string_length(
        body.get("name"), "name", MAX_NAME_LENGTH, required=True
    )
    if name is None:
        raise ValidationError("name is required", field="name")
    _ensure_unique_organization_name(repo, name)
    description = _validate_string_length(
        body.get("description"), "description", MAX_DESCRIPTION_LENGTH
    )
    name_translations = _validate_translations_map(
        body.get("name_translations"),
        "name_translations",
        MAX_NAME_LENGTH,
    )
    description_translations = _validate_translations_map(
        body.get("description_translations"),
        "description_translations",
        MAX_DESCRIPTION_LENGTH,
    )
    manager_id = _validate_manager_id(body.get("manager_id"), required=True)
    media_urls = _parse_media_urls(body.get("media_urls"))
    if media_urls:
        media_urls = _validate_media_urls(media_urls)
    logo_media_url = _validate_logo_media_url(
        body.get("logo_media_url"),
        media_urls,
    )
    contact_fields = _parse_organization_contact_fields(body)
    place_id = parse_place_id(body.get("place_id"))
    if place_id and repo.find_by_place_id(place_id) is not None:
        raise ValidationError("place_id already exists", field="place_id")
    status = parse_org_status(body.get("status")) or "operational"
    status_source = parse_status_source(body.get("status_source"))
    if status != "operational" and not status_source:
        status_source = "owner"

    return Organization(
        name=name,
        description=description,
        name_translations=name_translations,
        description_translations=description_translations,
        manager_id=manager_id,
        media_urls=media_urls,
        logo_media_url=logo_media_url,
        place_id=place_id,
        status=status,
        status_source=status_source,
        source=body.get("source") or None,
        source_id=body.get("source_id") or None,
        description_source=parse_description_source(body.get("description_source")),
        **contact_fields,
    )


def _update_organization(
    repo: OrganizationRepository,
    entity: Organization,
    body: dict[str, Any],
) -> Organization:
    """Update an organization."""
    if "name" in body:
        name = _validate_string_length(
            body["name"], "name", MAX_NAME_LENGTH, required=True
        )
        if name is None:
            raise ValidationError("name is required", field="name")
        _ensure_unique_organization_name(repo, name, current_id=str(entity.id))
        entity.name = name  # type: ignore[assignment]
    if "description" in body:
        entity.description = _validate_string_length(
            body["description"], "description", MAX_DESCRIPTION_LENGTH
        )
    if "name_translations" in body:
        entity.name_translations = _validate_translations_map(
            body["name_translations"],
            "name_translations",
            MAX_NAME_LENGTH,
        )
    if "description_translations" in body:
        entity.description_translations = _validate_translations_map(
            body["description_translations"],
            "description_translations",
            MAX_DESCRIPTION_LENGTH,
        )
    if "manager_id" in body:
        entity.manager_id = _validate_manager_id(body["manager_id"], required=True)  # type: ignore[assignment]
    updated_media_urls: Optional[list[str]] = None
    if "media_urls" in body:
        updated_media_urls = _parse_media_urls(body["media_urls"])
        if updated_media_urls:
            updated_media_urls = _validate_media_urls(updated_media_urls)
        entity.media_urls = updated_media_urls
    media_urls_for_logo = (
        updated_media_urls
        if updated_media_urls is not None
        else list(entity.media_urls or [])
    )
    if "logo_media_url" in body:
        entity.logo_media_url = _validate_logo_media_url(
            body.get("logo_media_url"),
            media_urls_for_logo,
        )
    elif updated_media_urls is not None:
        if entity.logo_media_url and entity.logo_media_url not in media_urls_for_logo:
            entity.logo_media_url = None
    _apply_organization_contact_fields(entity, body)
    _apply_organization_listing_fields(repo, entity, body)
    return entity


def _apply_organization_listing_fields(
    repo: OrganizationRepository,
    entity: Organization,
    body: dict[str, Any],
) -> None:
    """Apply place_id, status, and catalog source fields."""
    if "place_id" in body:
        place_id = parse_place_id(body.get("place_id"))
        if place_id:
            existing = repo.find_by_place_id(place_id)
            if existing is not None and str(existing.id) != str(entity.id):
                raise ValidationError(
                    "place_id already exists",
                    field="place_id",
                )
        entity.place_id = place_id
    if "status" in body:
        status = parse_org_status(body.get("status")) or "operational"
        source = parse_status_source(body.get("status_source")) or "owner"
        apply_listing_status(entity, status, source)
    if "source" in body:
        entity.source = body.get("source") or None
    if "source_id" in body:
        entity.source_id = body.get("source_id") or None
    if "description_source" in body:
        entity.description_source = parse_description_source(
            body.get("description_source")
        )


def _serialize_organization(entity: Organization) -> dict[str, Any]:
    """Serialize an organization."""
    return {
        "id": str(entity.id),
        "name": entity.name,
        "description": entity.description,
        "name_translations": build_translation_map(
            entity.name, entity.name_translations
        ),
        "description_translations": build_translation_map(
            entity.description, entity.description_translations
        ),
        "manager_id": entity.manager_id,
        "phone_country_code": entity.phone_country_code,
        "phone_number": entity.phone_number,
        "email": entity.email,
        "whatsapp": entity.whatsapp,
        "facebook": entity.facebook,
        "instagram": entity.instagram,
        "tiktok": entity.tiktok,
        "twitter": entity.twitter,
        "xiaohongshu": entity.xiaohongshu,
        "wechat": entity.wechat,
        "media_urls": entity.media_urls or [],
        "logo_media_url": entity.logo_media_url,
        "place_id": entity.place_id,
        "status": entity.status,
        "status_changed_at": entity.status_changed_at,
        "status_source": entity.status_source,
        "source": entity.source,
        "source_id": entity.source_id,
        "description_source": entity.description_source,
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
    }
