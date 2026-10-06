"""Find organizations that look like the same provider."""

from __future__ import annotations

import base64
import json
from difflib import SequenceMatcher
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.models import (
    Activity,
    Location,
    Organization,
    OrganizationDuplicateDismissal,
)
from app.services.name_sanitizer import organization_name_key

DEFAULT_MIN_SCORE = 0.6
_MAX_ORGS = 5000
_SOCIALS = (
    "whatsapp",
    "facebook",
    "instagram",
    "tiktok",
    "twitter",
    "xiaohongshu",
    "wechat",
)


def list_duplicate_groups(
    session: Session,
    *,
    min_score: float = DEFAULT_MIN_SCORE,
    signal: str | None = None,
    source: str | None = None,
    review_status: str | None = None,
    query: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> dict:
    """Return scored groups. Dismissed pairs stay apart."""
    orgs = list(
        session.scalars(
            select(Organization).order_by(Organization.name, Organization.id)
        ).all()
    )
    truncated = len(orgs) > _MAX_ORGS
    orgs = orgs[:_MAX_ORGS]
    dismissed = _dismissed_pairs(session)
    scores = _score_pairs(session, orgs, dismissed)
    groups = _build_groups(orgs, scores, min_score)
    filtered = [
        group
        for group in groups
        if _group_matches(group, signal, source, review_status, query)
    ]
    filtered.sort(key=lambda group: (-group["score"], group["id"]))
    start = _cursor_index(filtered, cursor)
    page = filtered[start : start + limit]
    next_cursor = None
    if start + limit < len(filtered) and page:
        last = page[-1]
        next_cursor = _encode_cursor(last["score"], last["id"])
    _attach_counts(session, page)
    return {"items": page, "next_cursor": next_cursor, "truncated": truncated}


def search_organizations(session: Session, query: str, limit: int = 20) -> list[dict]:
    """Name search used by the merge picker."""
    pattern = f"%{query.replace('%', '').replace('_', '')}%"
    rows = session.scalars(
        select(Organization)
        .where(Organization.name.ilike(pattern))
        .order_by(Organization.name)
        .limit(limit)
    ).all()
    return [_org_summary(row, {}, {}) for row in rows]


def dismiss_pairs(
    session: Session,
    org_ids: list[UUID],
    dismissed_by: str | None,
) -> int:
    """Remember every pair in the set as not duplicates."""
    unique = sorted({str(org_id) for org_id in org_ids})
    if len(unique) < 2:
        return 0
    created = 0
    for index, left in enumerate(unique):
        for right in unique[index + 1 :]:
            low, high = sorted((UUID(left), UUID(right)))
            exists = session.scalar(
                select(OrganizationDuplicateDismissal.id).where(
                    OrganizationDuplicateDismissal.org_id_low == low,
                    OrganizationDuplicateDismissal.org_id_high == high,
                )
            )
            if exists is not None:
                continue
            session.add(
                OrganizationDuplicateDismissal(
                    org_id_low=low,
                    org_id_high=high,
                    dismissed_by=dismissed_by,
                )
            )
            created += 1
    session.flush()
    return created


def orgs_with_duplicate_signals(
    session: Session,
    organizations: list[Organization],
) -> set[str]:
    """Ids in this page that exactly match another organization's identity fields."""
    if not organizations:
        return set()
    ids = [org.id for org in organizations]
    flagged: set[str] = set()
    flagged.update(
        _duplicate_column(session, ids, func.lower(func.trim(Organization.name)))
    )
    phone = func.concat(
        func.coalesce(Organization.phone_country_code, ""),
        ":",
        Organization.phone_number,
    )
    flagged.update(
        _duplicate_column(
            session,
            ids,
            phone,
            Organization.phone_number.is_not(None),
        )
    )
    flagged.update(
        _duplicate_column(
            session,
            ids,
            func.lower(Organization.email),
            Organization.email.is_not(None),
        )
    )
    flagged.update(
        _duplicate_column(
            session,
            ids,
            Organization.source_id,
            Organization.source_id.is_not(None),
        )
    )
    return flagged


def _duplicate_column(session, ids, expr, extra=None) -> set[str]:
    grouped = select(expr.label("key")).group_by(expr).having(func.count() > 1)
    if extra is not None:
        grouped = grouped.where(extra)
    keys = grouped.subquery()
    stmt = select(Organization.id).where(
        Organization.id.in_(ids),
        expr.in_(select(keys.c.key)),
    )
    if extra is not None:
        stmt = stmt.where(extra)
    return {str(item) for item in session.scalars(stmt).all()}


def _dismissed_pairs(session: Session) -> set[frozenset[str]]:
    rows = session.execute(
        select(
            OrganizationDuplicateDismissal.org_id_low,
            OrganizationDuplicateDismissal.org_id_high,
        )
    ).all()
    return {frozenset((str(low), str(high))) for low, high in rows}


def _score_pairs(
    session, orgs, dismissed
) -> dict[tuple[str, str], tuple[float, list[str]]]:
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
    if len(orgs) > 400 and session.get_bind().dialect.name == "postgresql":
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
    if session.get_bind().dialect.name != "postgresql":
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


def _build_groups(orgs, scores, min_score: float) -> list[dict]:
    parent = {str(org.id): str(org.id) for org in orgs}

    def find(org_id: str) -> str:
        while parent[org_id] != org_id:
            parent[org_id] = parent[parent[org_id]]
            org_id = parent[org_id]
        return org_id

    for (left, right), (score, _signals) in scores.items():
        if score < min_score or left not in parent or right not in parent:
            continue
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root
    members: dict[str, list[Organization]] = {}
    for org in orgs:
        members.setdefault(find(str(org.id)), []).append(org)
    groups = []
    for grouped in members.values():
        if len(grouped) < 2:
            continue
        ids = {str(org.id) for org in grouped}
        pair_scores = [
            item
            for pair, item in scores.items()
            if pair[0] in ids and pair[1] in ids and item[0] >= min_score
        ]
        if not pair_scores:
            continue
        signals: set[str] = set()
        best = 0.0
        for score, pair_signals in pair_scores:
            best = max(best, score)
            signals.update(pair_signals)
        ordered = sorted(grouped, key=lambda org: str(org.id))
        from app.services.org_merge import suggest_survivor_id

        groups.append(
            {
                "id": ",".join(str(org.id) for org in ordered),
                "score": round(best, 3),
                "signals": sorted(signals),
                "suggested_survivor_id": suggest_survivor_id(ordered),
                "organizations": [_org_summary(org, {}, {}) for org in ordered],
            }
        )
    return groups


def _attach_counts(session, groups: list[dict]) -> None:
    ids = [UUID(org["id"]) for group in groups for org in group["organizations"]]
    if not ids:
        return
    locations = dict(
        session.execute(
            select(Location.org_id, func.count())
            .where(Location.org_id.in_(ids))
            .group_by(Location.org_id)
        ).all()
    )
    activities = dict(
        session.execute(
            select(Activity.org_id, func.count())
            .where(Activity.org_id.in_(ids))
            .group_by(Activity.org_id)
        ).all()
    )
    for group in groups:
        for org in group["organizations"]:
            org["location_count"] = int(locations.get(UUID(org["id"]), 0))
            org["activity_count"] = int(activities.get(UUID(org["id"]), 0))


def _group_matches(group, signal, source, review_status, query) -> bool:
    if signal and signal not in group["signals"]:
        return False
    orgs = group["organizations"]
    if source and not any(
        (org.get("source") or "").casefold() == source.casefold() for org in orgs
    ):
        return False
    if review_status and not any(
        org.get("review_status") == review_status for org in orgs
    ):
        return False
    if query and not any(query.casefold() in org["name"].casefold() for org in orgs):
        return False
    return True


def _org_summary(org: Organization, locations, activities) -> dict:
    return {
        "id": str(org.id),
        "name": org.name,
        "review_status": org.review_status,
        "status": org.status,
        "source": org.source,
        "source_id": org.source_id,
        "place_id": org.place_id,
        "manager_id": org.manager_id,
        "phone_country_code": org.phone_country_code,
        "phone_number": org.phone_number,
        "email": org.email,
        "location_count": int(locations.get(org.id, 0)) if locations else 0,
        "activity_count": int(activities.get(org.id, 0)) if activities else 0,
    }


def _cursor_index(groups: list[dict], cursor: str | None) -> int:
    if not cursor:
        return 0
    payload = _decode_cursor(cursor)
    score = float(payload["score"])
    group_id = str(payload["id"])
    for index, group in enumerate(groups):
        if (group["score"], group["id"]) == (score, group_id):
            return index + 1
        if (-group["score"], group["id"]) > (-score, group_id):
            return index
    return len(groups)


def _encode_cursor(score: float, group_id: str) -> str:
    raw = json.dumps({"score": score, "id": group_id}).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _decode_cursor(value: str) -> dict:
    padded = value + "=" * (-len(value) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")))
    if "score" not in payload or "id" not in payload:
        raise ValueError("cursor")
    return payload


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
