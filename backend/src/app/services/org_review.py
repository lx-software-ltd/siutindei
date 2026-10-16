"""Completeness checks for the organization review queue.

Blockers stop a release unless the admin passes force. Warnings are
shown and do not block. The same rules drive the queue, the detail
view, and approve/bulk actions.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.age_bounds import inclusive_age_bounds
from app.db.models import (
    Activity,
    ActivityPricing,
    ActivitySchedule,
    Location,
)
from app.db.models import Organization
from app.db.models.category_suggestion import PENDING_CATEGORY_ID
from app.services.name_sanitizer import NameSanitizeConfig
from app.services.org_review_children import (
    counts_by_activity,
    linked_activity_ids,
    pending_category_check_ids,
)
from app.services.translation_gaps import LANGUAGES, field_gap

REVIEW_STATUSES = ("pending_review", "approved", "rejected")
MAX_REVIEW_NOTES_LENGTH = 2000
BULK_ORG_LIMIT = 200

_CONTACT_FIELDS = (
    "phone_number",
    "email",
    "website",
    "whatsapp",
    "facebook",
    "instagram",
    "tiktok",
    "twitter",
    "xiaohongshu",
    "wechat",
)

_TRANSLATION_WARNINGS = {
    ("name", "en"): ("missing_en_name", "English name is missing"),
    ("name", "zh"): ("missing_zh_name", "Chinese name is missing"),
    ("name", "zh-HK"): ("missing_zh_hk_name", "Hong Kong name is missing"),
    ("description", "en"): (
        "missing_en_description",
        "English description is missing",
    ),
    ("description", "zh"): (
        "missing_zh_description",
        "Chinese description is missing",
    ),
    ("description", "zh-HK"): (
        "missing_zh_hk_description",
        "Hong Kong description is missing",
    ),
}


@dataclass(frozen=True)
class ReviewIssue:
    """One missing or weak detail on an organization or its children."""

    code: str
    severity: str
    entity_type: str
    entity_id: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "message": self.message,
        }


@dataclass
class OrgReviewSnapshot:
    """Organization plus the issues used by the review queue."""

    organization: Organization
    locations: list[Location]
    activities: list[Activity]
    pricing_counts: dict[str, int]
    schedule_counts: dict[str, int]
    issues: list[ReviewIssue]
    check_count: int

    @property
    def blocker_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "blocker")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "warning")

    @property
    def completeness(self) -> float:
        total = len(self.issues) + _passed_checks(self)
        if total <= 0:
            return 1.0
        return round(1 - (self.blocker_count / total), 4)


def collect_issues(
    organization: Organization,
    locations: list[Location],
    activities: list[Activity],
    pricing_counts: dict[str, int],
    schedule_counts: dict[str, int],
    pending_category_check_ids: set[str] | None = None,
    name_config: NameSanitizeConfig | None = None,
    duplicate_ids: set[str] | None = None,
    linked_activity_ids: set[str] | None = None,
    pending_name_fix_ids: set[str] | None = None,
) -> tuple[list[ReviewIssue], int]:
    """Return issues and how many checks ran, so completeness can reach 1."""
    org_id = str(organization.id)
    issues: list[ReviewIssue] = []
    checks = 0

    def note() -> None:
        nonlocal checks
        checks += 1

    def add(
        code: str,
        severity: str,
        entity_type: str,
        entity_id: str,
        message: str,
    ) -> None:
        issues.append(
            ReviewIssue(
                code=code,
                severity=severity,
                entity_type=entity_type,
                entity_id=entity_id,
                message=message,
            )
        )

    from app.services.org_review_names import note_names

    note_names(
        organization,
        activities,
        name_config,
        pending_name_fix_ids or set(),
        add,
        note,
    )
    note()
    if duplicate_ids and org_id in duplicate_ids:
        add(
            "possible_duplicate",
            "warning",
            "organization",
            org_id,
            "Another organization has the same name, phone, email, or source id",
        )
    note()
    if not _text(organization.description):
        add(
            "missing_description",
            "blocker",
            "organization",
            org_id,
            "Description is missing",
        )
    note()
    if organization.description_source == "template":
        add(
            "source_attribution",
            "warning",
            "organization",
            org_id,
            "Description is a template",
        )
    elif "Source:" in (organization.description or ""):
        add(
            "source_attribution",
            "warning",
            "organization",
            org_id,
            "Description still contains a source line",
        )
    note()
    _note_translation_gaps(organization, org_id, add, note)
    if not any(_text(getattr(organization, field)) for field in _CONTACT_FIELDS):
        add(
            "no_contact",
            "warning",
            "organization",
            org_id,
            "No phone, email, website, or social contact",
        )
    note()
    if not organization.media_urls:
        add(
            "no_media",
            "warning",
            "organization",
            org_id,
            "No photos",
        )
    note()
    if not _text(organization.logo_media_url):
        add(
            "no_logo",
            "warning",
            "organization",
            org_id,
            "No logo",
        )
    note()
    if not _text(organization.place_id):
        add(
            "no_place_id",
            "warning",
            "organization",
            org_id,
            "No Google place id",
        )
    note()
    if not locations:
        add(
            "no_locations",
            "blocker",
            "organization",
            org_id,
            "No locations",
        )
    note()
    if not activities:
        add(
            "no_activities",
            "blocker",
            "organization",
            org_id,
            "No activities",
        )

    for location in locations:
        note()
        if location.lat is None or location.lng is None:
            add(
                "missing_coordinates",
                "blocker",
                "location",
                str(location.id),
                "Location is missing a map pin",
            )
    for activity in activities:
        activity_id = str(activity.id)
        note()
        if pricing_counts.get(activity_id, 0) <= 0:
            add(
                "missing_pricing",
                "blocker",
                "activity",
                activity_id,
                "Activity has no price",
            )
        note()
        if schedule_counts.get(activity_id, 0) <= 0:
            add(
                "missing_schedule",
                "blocker",
                "activity",
                activity_id,
                "Activity has no schedule",
            )
        note()
        if str(activity.category_id) == str(PENDING_CATEGORY_ID):
            add(
                "pending_category",
                "blocker",
                "activity",
                activity_id,
                "Activity is waiting for a category",
            )
        note()
        if activity_id in (pending_category_check_ids or set()):
            add(
                "category_check_pending",
                "warning",
                "activity",
                activity_id,
                "Category check is waiting for a decision",
            )
        if linked_activity_ids is not None:
            note()
        if linked_activity_ids is not None and activity_id not in linked_activity_ids:
            add(
                "activity_no_location",
                "warning",
                "activity",
                activity_id,
                "Activity has no location",
            )
        note()
        if not _text(activity.description):
            add(
                "missing_activity_description",
                "warning",
                "activity",
                activity_id,
                "Activity description is missing",
            )
        note()
        lower, upper = _age_bounds(activity)
        if lower == 0 and upper == 18:
            add(
                "default_age_range",
                "warning",
                "activity",
                activity_id,
                "Activity age range is still the import default (0-18)",
            )
    return issues, checks


def load_snapshots(
    session: Session,
    organizations: list[Organization],
) -> list[OrgReviewSnapshot]:
    """Load children and issues for the given organizations."""
    if not organizations:
        return []
    org_ids = [organization.id for organization in organizations]
    locations = list(
        session.scalars(select(Location).where(Location.org_id.in_(org_ids))).all()
    )
    activities = list(
        session.scalars(select(Activity).where(Activity.org_id.in_(org_ids))).all()
    )
    activity_ids = [activity.id for activity in activities]
    pricing_counts = counts_by_activity(
        session, ActivityPricing.activity_id, activity_ids
    )
    schedule_counts = counts_by_activity(
        session, ActivitySchedule.activity_id, activity_ids
    )
    locations_by_org: dict[str, list[Location]] = defaultdict(list)
    activities_by_org: dict[str, list[Activity]] = defaultdict(list)
    for location in locations:
        locations_by_org[str(location.org_id)].append(location)
    for activity in activities:
        activities_by_org[str(activity.org_id)].append(activity)
    pending_checks = pending_category_check_ids(session, activity_ids)
    linked_ids = linked_activity_ids(session, activity_ids)
    from app.services.name_fixes import load_name_fix_config
    from app.services.org_duplicates import orgs_with_duplicate_signals

    from app.services.org_review_names import pending_name_fix_ids as load_name_ids

    name_config = load_name_fix_config(session)
    duplicate_ids = orgs_with_duplicate_signals(session, organizations)
    name_ids = load_name_ids(
        session,
        [organization.id for organization in organizations],
        activity_ids,
    )

    snapshots: list[OrgReviewSnapshot] = []
    for organization in organizations:
        org_key = str(organization.id)
        org_locations = locations_by_org.get(org_key, [])
        org_activities = activities_by_org.get(org_key, [])
        org_pricing = {
            str(activity.id): pricing_counts.get(str(activity.id), 0)
            for activity in org_activities
        }
        org_schedules = {
            str(activity.id): schedule_counts.get(str(activity.id), 0)
            for activity in org_activities
        }
        issues, check_count = collect_issues(
            organization,
            org_locations,
            org_activities,
            org_pricing,
            org_schedules,
            pending_checks,
            name_config,
            duplicate_ids,
            {
                str(activity.id)
                for activity in org_activities
                if str(activity.id) in linked_ids
            },
            name_ids,
        )
        snapshots.append(
            OrgReviewSnapshot(
                organization=organization,
                locations=org_locations,
                activities=org_activities,
                pricing_counts=org_pricing,
                schedule_counts=org_schedules,
                issues=issues,
                check_count=check_count,
            )
        )
    return snapshots


def summarize_snapshots(snapshots: list[OrgReviewSnapshot]) -> dict[str, Any]:
    """Python summary used to check the SQL aggregate stays equivalent."""
    by_review = {status: 0 for status in REVIEW_STATUSES}
    by_source: dict[str, int] = {}
    by_status_source: dict[str, int] = {}
    by_issue: dict[str, int] = {}
    with_blockers = 0
    for snapshot in snapshots:
        org = snapshot.organization
        by_review[org.review_status] = by_review.get(org.review_status, 0) + 1
        source_key = org.source or "unknown"
        by_source[source_key] = by_source.get(source_key, 0) + 1
        status_source_key = org.status_source or "unknown"
        by_status_source[status_source_key] = (
            by_status_source.get(status_source_key, 0) + 1
        )
        if snapshot.blocker_count:
            with_blockers += 1
        seen: set[str] = set()
        for issue in snapshot.issues:
            if issue.code in seen:
                continue
            seen.add(issue.code)
            by_issue[issue.code] = by_issue.get(issue.code, 0) + 1
    return {
        "total": len(snapshots),
        "by_review_status": by_review,
        "by_source": by_source,
        "by_status_source": by_status_source,
        "by_issue": by_issue,
        "with_blockers": with_blockers,
    }


def snapshot_for_org(
    session: Session,
    organization: Organization,
) -> OrgReviewSnapshot:
    """Load one organization snapshot."""
    loaded = load_snapshots(session, [organization])
    return loaded[0]


def _passed_checks(snapshot: OrgReviewSnapshot) -> int:
    """Checks that did not produce an issue, so completeness can reach 1."""
    return max(snapshot.check_count - len(snapshot.issues), 0)


def _note_translation_gaps(organization, org_id, add, note) -> None:
    for field in ("name", "description"):
        gap = field_gap(
            getattr(organization, field),
            getattr(organization, f"{field}_translations"),
        )
        missing = set(gap["missing"]) if gap else set()
        for language in LANGUAGES:
            note()
            if language not in missing:
                continue
            code, message = _TRANSLATION_WARNINGS[(field, language)]
            add(code, "warning", "organization", org_id, message)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _age_bounds(activity: Activity) -> tuple[int | None, int | None]:
    return inclusive_age_bounds(activity.age_range)


def parse_org_uuid(value: str) -> UUID:
    """Parse an organization id or raise ValueError."""
    return UUID(str(value))
