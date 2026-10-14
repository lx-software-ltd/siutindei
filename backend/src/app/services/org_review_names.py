"""Name checks on an organization review snapshot."""

from __future__ import annotations

from app.db.models import Activity, Organization
from app.services.name_sanitizer import NameSanitizeConfig, sanitize_name


def note_names(
    organization: Organization,
    activities: list[Activity],
    name_config: NameSanitizeConfig | None,
    pending_name_ids: set[str],
    add,
    note,
) -> None:
    """Record cleanup warnings and pending name-change blockers."""
    org_id = str(organization.id)
    note()
    cleaned = sanitize_name(
        organization.name or "",
        organization.name_translations or {},
        name_config,
    )
    if cleaned.changed:
        add(
            "name_needs_cleanup",
            "warning",
            "organization",
            org_id,
            "Name needs cleanup",
        )
    if org_id in pending_name_ids:
        add(
            "pending_name_fix",
            "blocker",
            "organization",
            org_id,
            "Name change waiting for a decision",
        )
    if organization.review_status != "pending_review":
        _note_activity_blockers(activities, pending_name_ids, add)
        return
    for activity in activities:
        note()
        cleaned_activity = sanitize_name(
            activity.name or "",
            activity.name_translations or {},
            name_config,
        )
        if cleaned_activity.changed:
            add(
                "name_needs_cleanup",
                "warning",
                "activity",
                str(activity.id),
                "Name needs cleanup",
            )
        if str(activity.id) in pending_name_ids:
            add(
                "pending_name_fix",
                "blocker",
                "activity",
                str(activity.id),
                "Name change waiting for a decision",
            )


def _note_activity_blockers(activities, pending_name_ids: set[str], add) -> None:
    for activity in activities:
        if str(activity.id) not in pending_name_ids:
            continue
        add(
            "pending_name_fix",
            "blocker",
            "activity",
            str(activity.id),
            "Name change waiting for a decision",
        )


def pending_name_fix_ids(session, org_ids: list, activity_ids: list) -> set[str]:
    """Entity ids with a name change still waiting for a decision."""
    from sqlalchemy import and_, or_, select

    from app.db.models import NameFixProposal

    clauses = []
    if org_ids:
        clauses.append(
            and_(
                NameFixProposal.entity_type == "organization",
                NameFixProposal.entity_id.in_(org_ids),
            )
        )
    if activity_ids:
        clauses.append(
            and_(
                NameFixProposal.entity_type == "activity",
                NameFixProposal.entity_id.in_(activity_ids),
            )
        )
    if not clauses:
        return set()
    rows = session.scalars(
        select(NameFixProposal.entity_id).where(
            or_(*clauses),
            NameFixProposal.status == "pending",
        )
    ).all()
    return {str(item) for item in rows}
