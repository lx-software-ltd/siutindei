"""Repositories for category suggestions and settings."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.category_suggestion import (
    SETTINGS_SINGLETON_ID,
    CategorySuggestion,
    CategorySuggestionActivity,
    CategorySuggestionSettings,
)
from app.db.repositories.base import BaseRepository


class CategorySuggestionSettingsRepository:
    """Read and update the singleton settings row."""

    def __init__(self, session: Session):
        self._session = session

    def get_or_create(self) -> CategorySuggestionSettings:
        """Return the singleton, inserting defaults when it is missing."""
        row = self._session.get(
            CategorySuggestionSettings,
            SETTINGS_SINGLETON_ID,
        )
        if row is not None:
            return row
        row = CategorySuggestionSettings(id=SETTINGS_SINGLETON_ID)
        self._session.add(row)
        self._session.flush()
        return row


class CategorySuggestionRepository(BaseRepository[CategorySuggestion]):
    """Lookup and count helpers for category suggestions."""

    def __init__(self, session: Session):
        super().__init__(session, CategorySuggestion)

    def get_by_fingerprint(self, fingerprint: str) -> CategorySuggestion | None:
        """Return the suggestion for a normalised name."""
        query = select(CategorySuggestion).where(
            CategorySuggestion.fingerprint == fingerprint
        )
        return self._session.execute(query).scalar_one_or_none()

    def refresh_activity_count(self, suggestion: CategorySuggestion) -> int:
        """Set activity_count from the evidence links."""
        count = self._session.scalar(
            select(func.count())
            .select_from(CategorySuggestionActivity)
            .where(CategorySuggestionActivity.suggestion_id == suggestion.id)
        )
        suggestion.activity_count = int(count or 0)
        suggestion.updated_at = datetime.now(timezone.utc)
        return suggestion.activity_count
