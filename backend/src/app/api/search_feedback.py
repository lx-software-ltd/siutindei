"""Approved parent feedback for public search results.

``organization_feedback`` holds only feedback an admin approved, so
every row is public. The submitter id and email never leave this module.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas import (
    FeedbackLabelSchema,
    FeedbackRatingSchema,
    FeedbackReviewSchema,
)
from app.db.models import FeedbackLabel, OrganizationFeedback
from app.utils.translations import build_translation_map

MAX_PUBLIC_REVIEWS = 20
_ONE_DECIMAL = Decimal("0.1")


def load_ratings(
    session: Session,
    organization_ids: Iterable[str],
) -> dict[str, FeedbackRatingSchema]:
    """Feedback count and mean stars per organization with any feedback."""

    ids = sorted({str(value) for value in organization_ids})
    if not ids:
        return {}
    rows = session.execute(
        select(
            OrganizationFeedback.organization_id,
            func.count(OrganizationFeedback.id),
            func.avg(OrganizationFeedback.stars),
        )
        .where(OrganizationFeedback.organization_id.in_(ids))
        .group_by(OrganizationFeedback.organization_id)
    ).all()
    return {
        str(org_id): FeedbackRatingSchema(
            count=int(count),
            average_stars=Decimal(str(average)).quantize(
                _ONE_DECIMAL, rounding=ROUND_HALF_UP
            ),
        )
        for org_id, count, average in rows
        if count
    }


def load_reviews(
    session: Session,
    organization_id: str,
    limit: int = MAX_PUBLIC_REVIEWS,
) -> list[FeedbackReviewSchema]:
    """Newest approved feedback for one organization."""

    feedback = (
        session.execute(
            select(OrganizationFeedback)
            .where(OrganizationFeedback.organization_id == organization_id)
            .order_by(
                OrganizationFeedback.created_at.desc(),
                OrganizationFeedback.id,
            )
            .limit(limit)
        )
        .scalars()
        .all()
    )
    label_ids = {str(label) for row in feedback for label in row.label_ids or []}
    labels = _load_labels(session, label_ids)
    return [
        FeedbackReviewSchema(
            id=str(row.id),
            stars=int(row.stars),
            description=(row.description or "").strip() or None,
            labels=[
                labels[str(label)]
                for label in row.label_ids or []
                if str(label) in labels
            ],
            created_at=row.created_at,
        )
        for row in feedback
    ]


def _load_labels(
    session: Session,
    label_ids: set[str],
) -> dict[str, FeedbackLabelSchema]:
    if not label_ids:
        return {}
    rows = (
        session.execute(
            select(FeedbackLabel).where(FeedbackLabel.id.in_(sorted(label_ids)))
        )
        .scalars()
        .all()
    )
    return {
        str(row.id): FeedbackLabelSchema(
            id=str(row.id),
            name=row.name,
            name_translations=build_translation_map(row.name, row.name_translations),
        )
        for row in rows
    }
