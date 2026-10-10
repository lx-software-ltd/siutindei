"""Prompts that ask the model for a venue from a closed list."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Activity, GeographicArea, Location, Organization
from app.services.category_suggestions.prompt import redact_contacts

_MAX_DESCRIPTION = 300


def build_organization_prompt(
    session: Session, organizations: list[Organization]
) -> tuple[str, str]:
    areas = _area_choices(session)
    label = "neighbourhood" if areas and "district" in areas[0] else "district"
    system = (
        "You propose a venue address for organizations in Hong Kong. "
        "Reply with one JSON object only. Use an area_name from the "
        f"{label} list exactly. If the text does not support an address, "
        "set kind to unresolved. Do not invent an area."
    )
    user = {
        "areas": areas,
        "organizations": [
            {
                "entity_id": str(org.id),
                "name": redact_contacts(org.name or ""),
                "name_zh": redact_contacts(translation(org.name_translations, "zh")),
                "description": redact_contacts(_clip(org.description)),
                "source_host": _source_host(org.source_url),
            }
            for org in organizations
        ],
    }
    return system, json.dumps(user, ensure_ascii=False)


def build_activity_prompt(
    session: Session,
    activities: list[Activity],
    locations_by_org: dict[Any, list[Location]],
    area_names: dict[Any, str],
) -> tuple[str, str]:
    orgs = {
        org.id: org
        for org in session.scalars(
            select(Organization).where(
                Organization.id.in_({activity.org_id for activity in activities})
            )
        ).all()
    }
    system = (
        "You choose the venue for a children's activity in Hong Kong. "
        "Reply with one JSON object only. location_indexes lists every "
        "index from that activity's locations list that fits. One index "
        "links that venue. More than one, or none, is unresolved. "
        "Do not invent venues."
    )
    rows = []
    for activity in activities:
        org = orgs.get(activity.org_id)
        venues = []
        for index, location in enumerate(locations_by_org.get(activity.org_id, [])):
            venues.append(
                {
                    "index": index,
                    "address": redact_contacts(location.address or ""),
                    "area": area_names.get(location.area_id, ""),
                }
            )
        rows.append(
            {
                "entity_id": str(activity.id),
                "name": redact_contacts(activity.name or ""),
                "description": redact_contacts(_clip(activity.description)),
                "org_name": redact_contacts(org.name if org else ""),
                "locations": venues,
            }
        )
    return system, json.dumps({"activities": rows}, ensure_ascii=False)


def translation(values: dict[str, str] | None, language: str) -> str:
    if not values:
        return ""
    return str(values.get(language) or "")


def _area_choices(session: Session) -> list[dict[str, str]]:
    """Neighbourhoods when Hong Kong has them, otherwise leaf districts."""
    rows = session.scalars(
        select(GeographicArea)
        .where(
            GeographicArea.level == "neighbourhood",
            GeographicArea.active.is_(True),
        )
        .order_by(GeographicArea.name)
    ).all()
    if not rows:
        districts = session.scalars(
            select(GeographicArea)
            .where(GeographicArea.level == "district", GeographicArea.active.is_(True))
            .order_by(GeographicArea.name)
        ).all()
        return [
            {
                "name": area.name,
                "name_zh": translation(area.name_translations, "zh"),
            }
            for area in districts
        ]
    parent_ids = {area.parent_id for area in rows if area.parent_id}
    parents = {}
    if parent_ids:
        parents = {
            parent.id: parent.name
            for parent in session.scalars(
                select(GeographicArea).where(GeographicArea.id.in_(parent_ids))
            ).all()
        }
    return [
        {
            "name": area.name,
            "name_zh": translation(area.name_translations, "zh-HK")
            or translation(area.name_translations, "zh"),
            "district": parents.get(area.parent_id, ""),
        }
        for area in rows
    ]


def _clip(value: str | None) -> str:
    return (value or "")[:_MAX_DESCRIPTION]


def _source_host(url: str | None) -> str:
    if not url:
        return ""
    host = urlparse(url).hostname or ""
    return host.removeprefix("www.")
