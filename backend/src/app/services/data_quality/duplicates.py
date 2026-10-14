"""Deterministic duplicate groups for a data-quality run."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Organization, OrganizationDuplicateDismissal
from app.services.org_duplicate_scoring import score_pairs_stable
from app.services.org_merge import suggest_survivor_id

_MAX_ORGS = 5000
_MAX_GROUPS = 200
DEFAULT_MIN_SCORE = 0.6


def report_duplicates(
    session: Session,
    org_ids: list[str],
    *,
    min_score: float = DEFAULT_MIN_SCORE,
) -> dict:
    """Groups that touch ``org_ids``, ordered by score then id."""
    scope = {str(item) for item in org_ids}
    catalog, truncated = _catalog(session, scope)
    dismissed = _dismissed(session)
    scores = score_pairs_stable(session, catalog, dismissed, scope)
    groups = _groups(catalog, scores, min_score, dismissed)
    touching = [group for group in groups if scope.intersection(group["ids"])]
    touching.sort(key=lambda group: (-group["score"], group["id"]))
    stored = touching[:_MAX_GROUPS]
    return {
        "group_ids": [group["id"] for group in stored],
        "scores": {group["id"]: group["score"] for group in stored},
        "signals": {group["id"]: group["signals"] for group in stored},
        "count": len(touching),
        "truncated": truncated or len(touching) > _MAX_GROUPS,
    }


def _catalog(session: Session, scope: set[str]) -> tuple[list[Organization], bool]:
    rows = list(
        session.scalars(
            select(Organization).order_by(Organization.name, Organization.id)
        ).all()
    )
    truncated = len(rows) > _MAX_ORGS
    chosen = rows[:_MAX_ORGS]
    chosen_ids = {str(org.id) for org in chosen}
    if scope - chosen_ids:
        extra = [
            org
            for org in rows[_MAX_ORGS:]
            if str(org.id) in scope and str(org.id) not in chosen_ids
        ]
        chosen.extend(extra)
    return chosen, truncated


def _dismissed(session: Session) -> set[frozenset[str]]:
    rows = session.execute(
        select(
            OrganizationDuplicateDismissal.org_id_low,
            OrganizationDuplicateDismissal.org_id_high,
        )
    ).all()
    return {frozenset((str(low), str(high))) for low, high in rows}


def _groups(orgs, scores, min_score: float, dismissed) -> list[dict]:
    parent = {str(org.id): str(org.id) for org in orgs}
    members: dict[str, set[str]] = {str(org.id): {str(org.id)} for org in orgs}

    def find(org_id: str) -> str:
        while parent[org_id] != org_id:
            parent[org_id] = parent[parent[org_id]]
            org_id = parent[org_id]
        return org_id

    def blocked(left_root: str, right_root: str) -> bool:
        for left in sorted(members[left_root]):
            for right in sorted(members[right_root]):
                if frozenset((left, right)) in dismissed:
                    return True
        return False

    ranked = sorted(
        scores.items(),
        key=lambda item: (-item[1][0], item[0][0], item[0][1]),
    )
    for (left, right), (score, _signals) in ranked:
        if score < min_score or left not in parent or right not in parent:
            continue
        left_root, right_root = find(left), find(right)
        if left_root == right_root or blocked(left_root, right_root):
            continue
        if left_root > right_root:
            left_root, right_root = right_root, left_root
        parent[right_root] = left_root
        members[left_root].update(members.pop(right_root))
    by_id = {str(org.id): org for org in orgs}
    groups = []
    seen: set[str] = set()
    for org in orgs:
        root = find(str(org.id))
        if root in seen:
            continue
        seen.add(root)
        ids = sorted(members[root])
        if len(ids) < 2:
            continue
        pair_scores = [
            item
            for pair, item in scores.items()
            if pair[0] in members[root]
            and pair[1] in members[root]
            and item[0] >= min_score
        ]
        if not pair_scores:
            continue
        best = max(score for score, _signals in pair_scores)
        signals = sorted(
            {signal for _score, pair_signals in pair_scores for signal in pair_signals}
        )
        ordered = [by_id[item] for item in ids if item in by_id]
        groups.append(
            {
                "id": ",".join(ids),
                "ids": ids,
                "score": round(best, 3),
                "signals": signals,
                "suggested_survivor_id": suggest_survivor_id(ordered),
            }
        )
    return groups
