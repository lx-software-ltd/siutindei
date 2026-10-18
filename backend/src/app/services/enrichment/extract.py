"""Build proposals from parsed pages and a checked model sheet."""

from __future__ import annotations

import json
import re
from typing import Any

import phonenumbers

from app.services.enrichment.logos import media_proposals
from app.services.enrichment.parse import quote_supported
from app.services.enrichment.sheet import checked_value, schedule_entries, section_rows

_AMOUNT_RE = re.compile(r"\d+(?:[.,]\d+)?")
_PRICING_TYPES = {"per_class", "per_sessions", "per_hour", "per_day", "free"}


def proposals_from_pages(
    pages: list[dict[str, Any]],
    org: dict[str, Any],
) -> list[dict[str, Any]]:
    """Facts read off the page without a model."""
    found: list[dict[str, Any]] = []
    for page in pages:
        url = str(page.get("final_url") or page.get("url") or "")
        lang = str(page.get("lang") or "").lower()
        og: dict[str, Any] = raw if isinstance(raw := page.get("og"), dict) else {}
        description = str(og.get("og:description") or og.get("description") or "")
        if description:
            field = "description_zh" if lang.startswith("zh") else "description"
            found.append(_fact(field, description, url, description[:180], org))
        for email in page.get("mailtos") or []:
            found.append(_fact("email", str(email).lower(), url, str(email), org))
        for phone in page.get("tels") or []:
            found.extend(_phone_facts(str(phone), url, org))
        for item in page.get("social") or []:
            if isinstance(item, dict) and item.get("field") and item.get("url"):
                found.append(
                    _fact(
                        str(item["field"]), str(item["url"]), url, str(item["url"]), org
                    )
                )
        site_name = str(og.get("og:site_name") or "").strip()
        if site_name:
            found.append(_fact("name", site_name, url, site_name, org))
        found.extend(_jsonld_facts(page, url, org))
    found.extend(media_proposals(pages))
    return _dedupe(found)


def validate_model_sheet(
    sheet: dict[str, Any],
    pages: list[dict[str, Any]],
    org: dict[str, Any],
) -> list[dict[str, Any]]:
    """Keep model values whose quote is on a fetched page."""
    found: list[dict[str, Any]] = []
    organization = sheet.get("organization")
    if isinstance(organization, dict):
        for field, raw in organization.items():
            value = checked_value(raw, pages)
            if value is None or field not in _ORG_MODEL_FIELDS:
                continue
            if field == "phone":
                found.extend(
                    _phone_facts(value["value"], value["url"], org, value, pages=pages)
                )
                continue
            found.append(
                _fact(
                    field,
                    value["value"],
                    value["url"],
                    value["quote"],
                    org,
                    value["confidence"],
                    pages=pages,
                )
            )
    for row in section_rows(sheet, "locations"):
        address = checked_value(row.get("address"), pages)
        if address is None:
            continue
        proposed_location: dict[str, Any] = {"address": address["value"]}
        for key in ("area_name", "region", "district", "neighbourhood"):
            checked = checked_value(row.get(key), pages)
            if checked:
                proposed_location[key] = checked["value"]
        found.append(
            _record(
                "Locations",
                "create_location",
                f"Location · {address['value'][:80]}",
                proposed_location,
                address,
            )
        )
    for row in section_rows(sheet, "activities"):
        name = checked_value(row.get("name"), pages)
        if name is None:
            continue
        proposed: dict[str, Any] = {"name": name["value"]}
        for key in ("description", "category_name", "category_words", "name_zh"):
            checked = checked_value(row.get(key), pages)
            if checked:
                proposed[key] = checked["value"]
        for key in ("age_min", "age_max"):
            checked = checked_value(row.get(key), pages)
            if checked and str(checked["value"]).isdigit():
                proposed[key] = int(checked["value"])
        found.append(
            _record(
                "Activities",
                "create_activity",
                f"Activity · {name['value'][:80]}",
                proposed,
                name,
            )
        )
    for row in section_rows(sheet, "pricing"):
        amount = checked_value(row.get("amount"), pages)
        activity = checked_value(row.get("activity_name"), pages)
        if amount is None or activity is None:
            continue
        if not _AMOUNT_RE.search(amount["quote"]):
            continue
        pricing_type = str((row.get("pricing_type") or {}).get("value") or "per_class")
        if pricing_type not in _PRICING_TYPES:
            pricing_type = "per_class"
        proposed = {
            "activity_name": activity["value"],
            "location_address": str(
                (row.get("location_address") or {}).get("value") or ""
            ),
            "pricing_type": pricing_type,
            "amount": amount["value"],
            "currency": str((row.get("currency") or {}).get("value") or "HKD")[:8]
            or "HKD",
        }
        found.append(
            _record(
                "Pricing",
                "create_pricing",
                f"Price · {activity['value'][:60]}",
                proposed,
                amount,
            )
        )
    for row in section_rows(sheet, "schedules"):
        activity = checked_value(row.get("activity_name"), pages)
        entries = schedule_entries(row.get("entries"), pages)
        if activity is None or not entries:
            continue
        found.append(
            _record(
                "Schedules",
                "create_schedule",
                f"Schedule · {activity['value'][:60]}",
                {
                    "activity_name": activity["value"],
                    "location_address": str(
                        (row.get("location_address") or {}).get("value") or ""
                    ),
                    "languages": ["zh-HK"],
                    "entries": entries,
                },
                activity,
            )
        )
    return _dedupe(found)


def merge_proposals(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Earlier groups win when the field key is the same."""
    merged: dict[str, dict[str, Any]] = {}
    for group in groups:
        for item in group:
            key = _key(item)
            if key not in merged:
                merged[key] = item
    return list(merged.values())


_ORG_MODEL_FIELDS = {
    "name",
    "name_zh",
    "description",
    "description_zh",
    "email",
    "phone",
    "whatsapp",
    "facebook",
    "instagram",
    "tiktok",
    "twitter",
    "xiaohongshu",
    "wechat",
    "website",
}

_FIELD_LABELS = {
    "name": "Name",
    "name_zh": "Name (Chinese)",
    "description": "Description",
    "description_zh": "Description (Chinese)",
    "email": "Email",
    "phone": "Phone",
    "whatsapp": "WhatsApp",
    "facebook": "Facebook",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "twitter": "X",
    "xiaohongshu": "Xiaohongshu",
    "wechat": "WeChat",
    "website": "Website",
}


def _fact(
    field: str,
    value: str,
    url: str,
    quote: str,
    org: dict[str, Any],
    confidence: float = 0.95,
    pages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cleaned = str(value).strip()
    proposed = _proposed_for(field, cleaned)
    current = _current_for(field, org)
    corpus = pages or [
        {"final_url": url, "url": url, "text": quote, "jsonld_raw": [], "og": {}}
    ]
    unverified = False
    if not quote_supported(corpus, url, quote):
        if pages is not None or (
            quote and quote not in cleaned and cleaned not in quote
        ):
            unverified = True
            confidence = min(confidence, 0.5)
    if field == "description_zh":
        current = {
            "description_translations": {
                "zh": (org.get("description_translations") or {}).get("zh")
            }
        }
    if field == "name_zh":
        current = {
            "name_translations": {"zh": (org.get("name_translations") or {}).get("zh")}
        }
    stored_field = {
        "description_zh": "description_translations",
        "name_zh": "name_translations",
    }.get(field, field)
    return {
        "section": "Organization",
        "kind": "update_organization",
        "field": stored_field,
        "label": _FIELD_LABELS.get(field, field),
        "current": current,
        "proposed": proposed,
        "confidence": confidence,
        "unverified": unverified,
        "evidence": [{"url": url, "quote": quote[:300]}],
    }


def _proposed_for(field: str, value: str) -> dict[str, Any]:
    if field == "description_zh":
        return {"description_translations": {"zh": value[:5000]}}
    if field == "name_zh":
        return {"name_translations": {"zh": value[:200]}}
    if field == "description":
        return {"description": value[:5000]}
    if field == "name":
        return {"name": value[:200]}
    return {field: value[:400]}


def _current_for(field: str, org: dict[str, Any]) -> dict[str, Any] | None:
    if field == "description_zh":
        return None
    column = "description" if field == "description" else field
    stored = org.get(column)
    if stored in (None, "", [], {}):
        return None
    return {column: stored}


def _phone_facts(
    raw: str,
    url: str,
    org: dict[str, Any],
    checked: dict[str, Any] | None = None,
    pages: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    try:
        parsed = phonenumbers.parse(raw, "HK")
    except phonenumbers.NumberParseException:
        return []
    if not phonenumbers.is_valid_number(parsed):
        return []
    region = phonenumbers.region_code_for_number(parsed) or ""
    national = str(parsed.national_number)
    quote = (checked or {}).get("quote") or raw
    confidence = float((checked or {}).get("confidence") or 0.95)
    fact = _fact("phone", national, url, str(quote), org, confidence, pages=pages)
    fact["proposed"] = {"phone_country_code": region, "phone_number": national}
    fact["field"] = "phone"
    fact["current"] = {
        "phone_country_code": org.get("phone_country_code"),
        "phone_number": org.get("phone_number"),
    }
    return [fact]


def _jsonld_facts(
    page: dict[str, Any], url: str, org: dict[str, Any]
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for block in page.get("jsonld") or []:
        for node in _nodes(block):
            if not isinstance(node, dict):
                continue
            email = node.get("email")
            if isinstance(email, str):
                found.append(_fact("email", email, url, email, org))
            phone = node.get("telephone")
            if isinstance(phone, str):
                found.extend(_phone_facts(phone, url, org))
            description = node.get("description")
            if isinstance(description, str) and len(description) > 40:
                found.append(
                    _fact("description", description, url, description[:180], org)
                )
            name = _organization_name(node)
            if name:
                found.append(_fact("name", name, url, name, org))
    return found


def _organization_name(node: dict[str, Any]) -> str:
    name = node.get("name")
    if not isinstance(name, str) or not name.strip():
        return ""
    raw = node.get("@type")
    types = raw if isinstance(raw, list) else [raw]
    blob = " ".join(str(item) for item in types if item).casefold()
    if any(token in blob for token in ("product", "event", "offer", "review")):
        return ""
    if blob and not any(
        token in blob
        for token in ("organization", "localbusiness", "school", "sportsclub")
    ):
        return ""
    return name.strip()


def _nodes(block: object) -> list[object]:
    if isinstance(block, list):
        return block
    if isinstance(block, dict) and isinstance(block.get("@graph"), list):
        return list(block["@graph"])
    if isinstance(block, dict):
        return [block]
    return []


def _record(
    section: str,
    kind: str,
    label: str,
    proposed: dict[str, Any],
    evidence_value: dict[str, Any],
) -> dict[str, Any]:
    return {
        "section": section,
        "kind": kind,
        "field": None,
        "label": label,
        "current": None,
        "proposed": proposed,
        "confidence": evidence_value["confidence"],
        "unverified": bool(evidence_value.get("unverified")),
        "evidence": [
            {"url": evidence_value["url"], "quote": evidence_value["quote"][:300]}
        ],
    }


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    kept: list[dict[str, Any]] = []
    for item in items:
        key = _key(item)
        if key in seen:
            continue
        seen.add(key)
        kept.append(item)
    return kept


def _key(item: dict[str, Any]) -> str:
    return json.dumps(
        {
            "section": item.get("section"),
            "kind": item.get("kind"),
            "field": item.get("field"),
            "label": item.get("label"),
            "proposed": item.get("proposed"),
        },
        sort_keys=True,
        default=str,
    )
