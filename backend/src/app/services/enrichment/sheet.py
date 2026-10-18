"""Read the model sheet in the shapes models return, then check every quote."""

from __future__ import annotations

import json
import re
from typing import Any

from app.services.enrichment.parse import find_quote
from app.services.openrouter_json_parse import openrouter_json_text_candidates

SECTIONS = ("locations", "activities", "pricing", "schedules")

_ROW_FIELDS = {
    "locations": ("address", "area_name", "region", "district", "neighbourhood"),
    "activities": (
        "name",
        "name_zh",
        "description",
        "category_name",
        "category_words",
        "age_min",
        "age_max",
    ),
    "pricing": (
        "activity_name",
        "location_address",
        "pricing_type",
        "amount",
        "currency",
    ),
    "schedules": ("activity_name", "location_address"),
}

# Used when the model leaves confidence out. The quote check still caps an
# unverified value at 0.5.
_DEFAULT_CONFIDENCE = 0.7

_DAYS = {
    "sunday": 0,
    "sun": 0,
    "monday": 1,
    "mon": 1,
    "tuesday": 2,
    "tue": 2,
    "tues": 2,
    "wednesday": 3,
    "wed": 3,
    "thursday": 4,
    "thu": 4,
    "thur": 4,
    "thurs": 4,
    "friday": 5,
    "fri": 5,
    "saturday": 6,
    "sat": 6,
    "日": 0,
    "天": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
}
_CLOCK_RE = re.compile(r"^(\d{1,2})(?:[:.](\d{2}))?\s*(?:([ap])\.?\s*m\.?)?$", re.I)


def sheet_from_text(text: str) -> dict[str, Any]:
    """The first JSON object in the model reply, or an empty sheet."""
    return read_sheet(text)[0]


def read_sheet(text: str) -> tuple[dict[str, Any], str]:
    """The sheet, and whether it parsed ``whole``, was ``repaired``, or is ``empty``.

    A reply that hits the model's output limit stops mid-row. Every complete
    row before the cut is kept, and the cut row is dropped.
    """
    candidates = openrouter_json_text_candidates(text or "")
    for candidate in candidates:
        try:
            loaded = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        return (loaded, "whole") if isinstance(loaded, dict) else ({}, "empty")
    start = candidates[0].find("{")
    if start >= 0:
        try:
            loaded = json.loads(_close_cut_json(candidates[0][start:]))
        except json.JSONDecodeError:
            loaded = None
        if isinstance(loaded, dict) and any(loaded.values()):
            return loaded, "repaired"
    return {}, "empty"


def _close_cut_json(text: str) -> str:
    """Cut after the last whole row and close the brackets still open.

    Cuts only fall between sections, organization fields, or rows of a
    section list (depth two or less), so a row is never half kept.
    """
    stack: list[str] = []
    cut, closers = 0, ""
    in_string = escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append("}" if char == "{" else "]")
        elif char in "}]":
            if not stack:
                break
            stack.pop()
            if len(stack) <= 2:
                cut, closers = index + 1, "".join(reversed(stack))
            if not stack:
                break
        elif char == "," and len(stack) <= 2:
            cut, closers = index, "".join(reversed(stack))
    return text[:cut] + closers


def section_rows(sheet: dict[str, Any], section: str) -> list[dict[str, Any]]:
    """Rows where each field is a value object.

    Accepts evidence and confidence on the row, plain field values, a row
    wrapped in ``value``, and a single row instead of a list.
    """
    raw = sheet.get(section)
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    fields = _ROW_FIELDS[section]
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        base = item
        inner = item.get("value")
        if isinstance(inner, dict) and not any(field in item for field in fields):
            base = {**{k: v for k, v in item.items() if k != "value"}, **inner}
        evidence = _evidence(base.get("evidence")) or _evidence(
            {"url": base.get("url"), "quote": base.get("quote")}
        )
        confidence = base.get("confidence")
        row = dict(base)
        for field in fields:
            row[field] = _value_object(base.get(field), evidence, confidence)
        rows.append(row)
    return rows


def checked_value(raw: object, pages: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The value with the first quote found on a fetched page, or unverified."""
    if not isinstance(raw, dict):
        return None
    value = raw.get("value")
    if value is None or isinstance(value, (dict, list)) or str(value).strip() == "":
        return None
    evidence = _evidence(raw.get("evidence"))
    if not evidence:
        return None
    confidence = _confidence(raw.get("confidence"))
    for item in evidence:
        url = str(item.get("url") or "")
        quote = str(item.get("quote") or "")
        found = find_quote(pages, url, quote)
        if found is not None:
            return _checked(value, found, quote, confidence, unverified=False)
    first = evidence[0]
    return _checked(
        value,
        str(first.get("url") or ""),
        str(first.get("quote") or ""),
        min(confidence, 0.5),
        unverified=True,
    )


def schedule_entries(raw: object, pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    entries: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        day = _day(item.get("day_of_week", item.get("day")))
        start = _clock(item.get("start_time", item.get("start")))
        end = _clock(item.get("end_time", item.get("end")))
        if day is None or start is None or end is None:
            continue
        quote = str(item.get("quote") or "")
        if quote and find_quote(pages, str(item.get("url") or ""), quote) is None:
            continue
        entries.append({"day_of_week": day, "start_time": start, "end_time": end})
    return entries


def _checked(
    value: object, url: str, quote: str, confidence: float, *, unverified: bool
) -> dict[str, Any]:
    return {
        "value": str(value).strip(),
        "url": url,
        "quote": quote,
        "confidence": confidence,
        "unverified": unverified,
    }


def _value_object(
    raw: object, evidence: list[dict[str, Any]], confidence: object
) -> dict[str, Any] | None:
    if isinstance(raw, dict) and "value" in raw:
        wrapped = dict(raw)
        wrapped["evidence"] = _evidence(raw.get("evidence")) or evidence
        if wrapped.get("confidence") is None:
            wrapped["confidence"] = confidence
        return wrapped
    if raw is None or isinstance(raw, (dict, list)) or str(raw).strip() == "":
        return None
    return {"value": raw, "confidence": confidence, "evidence": evidence}


def _evidence(raw: object) -> list[dict[str, Any]]:
    if isinstance(raw, str):
        raw = [{"url": "", "quote": raw}]
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict) and item.get("quote")]


def _confidence(raw: object) -> float:
    if raw is None or raw == "" or isinstance(raw, bool):
        return _DEFAULT_CONFIDENCE
    try:
        number = float(str(raw))
    except ValueError:
        return _DEFAULT_CONFIDENCE
    return min(1.0, max(0.0, number))


def _day(raw: object) -> int | None:
    text = str(raw if raw is not None else "").strip().casefold()
    if text.isdigit():
        number = int(text)
        return 0 if number == 7 else number if 0 <= number <= 6 else None
    for prefix in ("星期", "禮拜", "週", "周"):
        text = text.removeprefix(prefix)
    return _DAYS.get(text.rstrip("s."))


def _clock(raw: object) -> str | None:
    match = _CLOCK_RE.match(str(raw if raw is not None else "").strip())
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    half = (match.group(3) or "").lower()
    if half:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if half == "p" else 0)
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"
