"""Attach one accepted enrichment image to the organization."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.api.admin_validators import MAX_MEDIA_URLS_COUNT, _validate_url
from app.db.models.organization import Organization
from app.exceptions import ValidationError
from app.services.aws_proxy import AwsProxyError
from app.utils.logging import get_logger

logger = get_logger(__name__)

CopyImage = Any


def apply_media(
    session: Session,
    org: Organization,
    proposed: dict[str, Any],
    *,
    copy_image: CopyImage | None,
) -> None:
    """Copy a website image, or attach a leaflet already in the bucket."""
    source = str(proposed.get("source_url") or "")
    if not source:
        raise ValidationError("image URL is missing", field="source_url")
    stored_leaflet = _stored_leaflet_url(str(org.id), proposed)
    if stored_leaflet:
        _append_media(org, stored_leaflet, logo=bool(proposed.get("logo")))
        return
    from app.services.enrichment.store import load_settings

    settings = load_settings(session)
    if settings.copy_media:
        if copy_image is None:
            from app.services.aws_proxy import crawl_invoke

            def copy_image(image_url: str, org_id: str) -> str:
                copied = crawl_invoke(
                    {"op": "image", "url": image_url, "org_id": org_id}
                )
                return str(copied.get("url") or "")

        try:
            stored = copy_image(source, str(org.id))
        except AwsProxyError as exc:
            logger.warning("Enrichment image was not copied")
            raise ValidationError(
                exc.message or "image could not be copied",
                field="source_url",
            ) from exc
    else:
        stored = _validate_url(source, "media_urls")
    _append_media(org, stored, logo=bool(proposed.get("logo")))


def _stored_leaflet_url(org_id: str, proposed: dict[str, Any]) -> str | None:
    """A leaflet file already in this organization's bucket."""
    from app.services.enrichment.leaflet_objects import publish_leaflet

    return publish_leaflet(org_id, str(proposed.get("object_key") or ""))


def _append_media(org: Organization, stored: str, *, logo: bool) -> None:
    urls = list(org.media_urls or [])
    if stored not in urls:
        if len(urls) >= MAX_MEDIA_URLS_COUNT:
            raise ValidationError("media_urls is full", field="media_urls")
        urls.append(stored)
        org.media_urls = urls
    if logo:
        org.logo_media_url = stored
