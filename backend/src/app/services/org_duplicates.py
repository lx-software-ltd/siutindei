"""Find organizations that look like the same provider."""

from __future__ import annotations

import base64
import json
import time
from uuid import UUID

from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from app.db.audit import AuditService
from app.db.models import (
    Activity,
    Location,
    Organization,
    OrganizationDuplicateDismissal,
)
from app.exceptions import NotFoundError, ValidationError
from app.services.name_sanitizer import organization_name_key
from app.services.org_duplicate_scoring import score_pairs

DEFAULT_MIN_SCORE = 0.6
_MAX_ORGS = 5000
_CACHE_TTL_SECONDS = 30
_cache: dict[tuple, tuple[float, list, bool]] = {}
_cache_token = 0


def invalidate_duplicate_cache() -> None:
    """Drop scored groups after a merge or dismissal."""
    global _cache_token
    _cache_token += 1
    _cache.clear()


def list_duplicate_groups(
    session: Session,
    *,
    min_score: float = DEFAULT_MIN_SCORE,
    signal: str | None = None,
    source: str | None = None,
    review_status: str | None = None,
    query: str | None = None,
    org_id: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> dict:
    """Return scored groups. Dismissed pairs stay apart, including transitively."""
    groups, truncated = _cached_groups(session, min_score)
    filtered = [
        group
        for group in groups
        if _group_matches(group, signal, source, review_status, query, org_id)
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


def get_duplicate_group(session: Session, group_id: str) -> dict:
    """Load one group by its comma-joined organization ids."""
    parsed = _group_ids(group_id)
    orgs = list(
        session.scalars(select(Organization).where(Organization.id.in_(parsed))).all()
    )
    if len(orgs) < 2:
        raise NotFoundError("org_duplicates", group_id)
    cached = _cached_group_by_id(group_id)
    if cached is not None:
        _attach_counts(session, [cached])
        return cached
    dismissed = _dismissed_pairs(session)
    scores = score_pairs(session, orgs, dismissed)
    groups = _build_groups(orgs, scores, 0.0, dismissed)
    match = next((group for group in groups if group["id"] == group_id), None)
    if match is None:
        from app.services.org_merge import suggest_survivor_id

        ordered = sorted(orgs, key=lambda org: str(org.id))
        match = {
            "id": ",".join(str(org.id) for org in ordered),
            "score": 0.0,
            "signals": [],
            "suggested_survivor_id": suggest_survivor_id(ordered),
            "organizations": [_org_summary(org) for org in ordered],
        }
    _attach_counts(session, [match])
    return match


def search_organizations(session: Session, query: str, limit: int = 20) -> list[dict]:
    """Name search used by the merge picker."""
    pattern = f"%{query.replace('%', '').replace('_', '')}%"
    rows = session.scalars(
        select(Organization)
        .where(Organization.name.ilike(pattern))
        .order_by(Organization.name)
        .limit(limit)
    ).all()
    return [_org_summary(row) for row in rows]


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
    if created:
        AuditService(session, user_id=dismissed_by).log_custom(
            "organization_duplicate_dismissals",
            UUID(unique[0]),
            "DISMISS_DUPLICATE",
            new_values={"org_ids": unique},
        )
    invalidate_duplicate_cache()
    return created


def orgs_with_duplicate_signals(
    session: Session,
    organizations: list[Organization],
) -> set[str]:
    """Page ids that share a name key, phone, email, or source id."""
    if not organizations:
        return set()
    page_ids = {str(org.id) for org in organizations}
    dismissed = _dismissed_pairs(session)
    rows = session.execute(
        select(
            Organization.id,
            Organization.name,
            Organization.name_key,
            Organization.phone_country_code,
            Organization.phone_number,
            Organization.email,
            Organization.source_id,
        )
        .order_by(Organization.id)
        .limit(_MAX_ORGS)
    ).all()
    buckets: dict[tuple[str, str], list[str]] = {}

    def put(kind: str, key: str, org_id: str) -> None:
        if not key:
            return
        buckets.setdefault((kind, key), []).append(org_id)

    for row in rows:
        org_id = str(row.id)
        put("name", row.name_key or organization_name_key(row.name or ""), org_id)
        if _text(row.phone_number):
            put(
                "phone",
                f"{_text(row.phone_country_code)}:{_text(row.phone_number)}",
                org_id,
            )
        put("email", _text(row.email).casefold(), org_id)
        put("source_id", _text(row.source_id), org_id)
    flagged: set[str] = set()
    for members in buckets.values():
        unique = list(dict.fromkeys(members))
        if len(unique) < 2:
            continue
        for index, left in enumerate(unique):
            for right in unique[index + 1 :]:
                if frozenset((left, right)) in dismissed:
                    continue
                if left in page_ids:
                    flagged.add(left)
                if right in page_ids:
                    flagged.add(right)
    return flagged


def _cached_groups(session: Session, min_score: float) -> tuple[list, bool]:
    stamp = _data_stamp(session)
    key = (stamp, round(min_score, 4), _cache_token)
    now = time.monotonic()
    cached = _cache.get(key)
    if cached is not None and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1], cached[2]
    orgs = list(
        session.scalars(
            select(Organization).order_by(Organization.name, Organization.id)
        ).all()
    )
    truncated = len(orgs) > _MAX_ORGS
    orgs = orgs[:_MAX_ORGS]
    dismissed = _dismissed_pairs(session)
    groups = _build_groups(
        orgs, score_pairs(session, orgs, dismissed), min_score, dismissed
    )
    _cache[key] = (now, groups, truncated)
    return groups, truncated


def _cached_group_by_id(group_id: str) -> dict | None:
    now = time.monotonic()
    for stored_at, groups, _truncated in _cache.values():
        if now - stored_at >= _CACHE_TTL_SECONDS:
            continue
        for group in groups:
            if group["id"] == group_id:
                return group
    return None


def _data_stamp(session: Session) -> tuple:
    count = int(session.scalar(select(func.count()).select_from(Organization)) or 0)
    updated = session.scalar(select(func.max(Organization.updated_at)))
    dismissals = int(
        session.scalar(select(func.count()).select_from(OrganizationDuplicateDismissal))
        or 0
    )
    newest = session.scalar(select(func.max(cast(Organization.id, String))))
    updated_text = updated.isoformat() if updated is not None else ""
    return (count, updated_text, dismissals, str(newest or ""))


def _group_ids(group_id: str) -> list[UUID]:
    parsed: list[UUID] = []
    for part in group_id.split(","):
        text = part.strip()
        if not text:
            continue
        try:
            parsed.append(UUID(text))
        except ValueError as exc:
            raise ValidationError("id must be a UUID", field="id") from exc
    unique = list(dict.fromkeys(parsed))
    if len(unique) < 2:
        raise NotFoundError("org_duplicates", group_id)
    return unique


def _dismissed_pairs(session: Session) -> set[frozenset[str]]:
    rows = session.execute(
        select(
            OrganizationDuplicateDismissal.org_id_low,
            OrganizationDuplicateDismissal.org_id_high,
        )
    ).all()
    return {frozenset((str(low), str(high))) for low, high in rows}


def _build_groups(orgs, scores, min_score: float, dismissed) -> list[dict]:
    parent = {str(org.id): str(org.id) for org in orgs}
    members: dict[str, set[str]] = {str(org.id): {str(org.id)} for org in orgs}

    def find(org_id: str) -> str:
        while parent[org_id] != org_id:
            parent[org_id] = parent[parent[org_id]]
            org_id = parent[org_id]
        return org_id

    def blocked(left_root: str, right_root: str) -> bool:
        for left in members[left_root]:
            for right in members[right_root]:
                if frozenset((left, right)) in dismissed:
                    return True
        return False

    ranked = sorted(scores.items(), key=lambda item: item[1][0], reverse=True)
    for (left, right), (score, _signals) in ranked:
        if score < min_score or left not in parent or right not in parent:
            continue
        left_root, right_root = find(left), find(right)
        if left_root == right_root or blocked(left_root, right_root):
            continue
        parent[right_root] = left_root
        members[left_root].update(members.pop(right_root))
    grouped_orgs: dict[str, list[Organization]] = {}
    for org in orgs:
        grouped_orgs.setdefault(find(str(org.id)), []).append(org)
    groups = []
    for grouped in grouped_orgs.values():
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
                "organizations": [_org_summary(org) for org in ordered],
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


def _group_matches(group, signal, source, review_status, query, org_id) -> bool:
    if signal and signal not in group["signals"]:
        return False
    orgs = group["organizations"]
    if org_id and not any(org["id"] == org_id for org in orgs):
        return False
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


def _org_summary(org: Organization) -> dict:
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
        "location_count": 0,
        "activity_count": 0,
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


def _text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()
