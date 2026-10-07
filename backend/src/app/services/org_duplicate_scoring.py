"""Pair scores for organizations that look like the same provider."""

from __future__ import annotations

from difflib import SequenceMatcher
from urllib.parse import urlparse

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import Location, Organization
from app.services.name_sanitizer import organization_name_key
from app.utils.logging import get_logger

logger = get_logger(__name__)

_SOCIALS = (
    "whatsapp",
    "facebook",
    "instagram",
    "tiktok",
    "twitter",
    "xiaohongshu",
    "wechat",
)


def score_pairs(
    session,
    orgs,
    dismissed,
) -> dict[tuple[str, str], tuple[float, list[str]]]:
    """Score unordered pairs. Dismissed pairs receive no score."""
    by_id = {str(org.id): org for org in orgs}
    scores: dict[tuple[str, str], dict[str, float]] = {}

    def add(left: str, right: str, signal: str, amount: float) -> None:
        if left == right:
            return
        low, high = sorted((left, right))
        pair = (low, high)
        if frozenset(pair) in dismissed:
            return
        bucket = scores.setdefault(pair, {})
        bucket[signal] = max(bucket.get(signal, 0.0), amount)

    _bucket_pairs(orgs, add)
    _similarity_pairs(session, orgs, add)
    _location_boost(session, by_id, scores)
    scored: dict[tuple[str, str], tuple[float, list[str]]] = {}
    for pair, parts in scores.items():
        base = max(
            (amount for signal, amount in parts.items() if signal != "location"),
            default=0.0,
        )
        boost = 0.15 if "location" in parts else 0.0
        scored[pair] = (min(1.0, base + boost), sorted(parts))
    return scored


def _bucket_pairs(orgs, add) -> None:
    buckets: dict[tuple[str, str], list[str]] = {}

    def put(kind: str, key: str, org_id: str) -> None:
        if not key:
            return
        buckets.setdefault((kind, key), []).append(org_id)

    for org in orgs:
        org_id = str(org.id)
        put("name", organization_name_key(org.name), org_id)
        put("source_id", _text(org.source_id), org_id)
        if _text(org.phone_number):
            put(
                "phone",
                f"{_text(org.phone_country_code)}:{_text(org.phone_number)}",
                org_id,
            )
        put("email", _text(org.email).casefold(), org_id)
        for field in _SOCIALS:
            value = _text(getattr(org, field)).casefold()
            if value:
                put("social", f"{field}:{value}", org_id)
        put("website", _host(org.source_url), org_id)
        for value in _translation_values(org):
            put("translation", value, org_id)
            put("name", organization_name_key(value), org_id)
    weights = {
        "name": 1.0,
        "source_id": 0.95,
        "phone": 0.75,
        "email": 0.75,
        "social": 0.65,
        "website": 0.45,
        "translation": 0.85,
    }
    for (kind, _key), members in buckets.items():
        unique = list(dict.fromkeys(members))
        if len(unique) < 2:
            continue
        for index, left in enumerate(unique):
            for right in unique[index + 1 :]:
                add(left, right, kind, weights[kind])


def _similarity_pairs(session, orgs, add) -> None:
    ids = {str(org.id) for org in orgs}
    for left, right, sim in _trgm_pairs(session):
        if left in ids and right in ids and sim >= 0.55:
            add(left, right, "name", sim)
    bind = session.get_bind()
    if len(orgs) > 400 and bind is not None and bind.dialect.name == "postgresql":
        return
    keys = [(str(org.id), organization_name_key(org.name)) for org in orgs]
    for index, (left_id, left_key) in enumerate(keys):
        if not left_key:
            continue
        for right_id, right_key in keys[index + 1 :]:
            if not right_key or left_key == right_key:
                continue
            if len(orgs) > 400 and left_key[:4] != right_key[:4]:
                continue
            sim = SequenceMatcher(None, left_key, right_key).ratio()
            if sim >= 0.55:
                add(left_id, right_id, "name", sim)


def _trgm_pairs(session: Session) -> list[tuple[str, str, float]]:
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return []
    try:
        with session.begin_nested():
            session.execute(text("SELECT set_limit(0.45)"))
            rows = session.execute(
                text(
                    """
                    SELECT a.id::text, b.id::text,
                           similarity(lower(a.name), lower(b.name))
                    FROM organizations a
                    JOIN organizations b ON a.id < b.id
                    WHERE lower(a.name) % lower(b.name)
                    """
                )
            ).all()
    except Exception:
        logger.warning("pg_trgm similarity lookup failed", exc_info=True)
        return []
    return [(left, right, float(score)) for left, right, score in rows]


def _location_boost(session, by_id, scores) -> None:
    if not scores:
        return
    rows = list(
        session.scalars(select(Location).where(Location.org_id.in_(list(by_id)))).all()
    )
    points: dict[str, list[tuple[float, float]]] = {}
    for row in rows:
        if row.lat is None or row.lng is None:
            continue
        points.setdefault(str(row.org_id), []).append((float(row.lat), float(row.lng)))
    for pair, parts in scores.items():
        if max(parts.values()) < 0.35:
            continue
        left, right = pair
        if _points_close(points.get(left, []), points.get(right, [])):
            parts["location"] = max(parts.get("location", 0.0), 0.15)


def _points_close(left, right) -> bool:
    for lat1, lng1 in left:
        for lat2, lng2 in right:
            lat_m = (lat1 - lat2) * 111_000
            lng_m = (lng1 - lng2) * 111_000 * 0.85
            if (lat_m * lat_m + lng_m * lng_m) ** 0.5 <= 50:
                return True
    return False


def _translation_values(org: Organization) -> list[str]:
    values: list[str] = []
    raw = org.name_translations or {}
    if isinstance(raw, dict):
        values.extend(_text(value) for value in raw.values())
    name_key = organization_name_key(org.name)
    return [
        value for value in values if value and organization_name_key(value) != name_key
    ]


def _host(value: str | None) -> str:
    text_value = _text(value)
    if not text_value:
        return ""
    parsed = urlparse(text_value if "://" in text_value else f"https://{text_value}")
    return (parsed.netloc or "").casefold().removeprefix("www.")


def _text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()
