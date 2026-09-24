"""Resolve an imported category_name to an existing category or capture."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import ActivityCategory
from app.db.models.category_suggestion import (
    PENDING_CATEGORY_ID,
    CategorySuggestion,
)
from app.exceptions import ValidationError
from app.services.category_suggestions.settings import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


@dataclass
class CategoryResolution:
    """Outcome of resolving one imported category name."""

    category_id: UUID | None = None
    capture: bool = False


@dataclass
class CaptureBatch:
    """Per-import state shared by category resolution."""

    enabled: bool
    auto_enrich: bool
    seen: set[str] = field(default_factory=set)
    enqueue: set[str] = field(default_factory=set)
    index: dict[str, set[UUID]] | None = None


_batch: CaptureBatch | None = None
_last_enqueue: list[str] = []


def normalize_category_key(value: str) -> str:
    """Casefold, strip punctuation, and collapse whitespace."""
    text = unicodedata.normalize("NFKC", value).casefold()
    text = _PUNCT_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    return text


def begin_capture_batch(session: Session) -> None:
    """Load settings once for the current import batch."""
    global _batch, _last_enqueue
    settings = get_settings(session)
    _batch = CaptureBatch(
        enabled=bool(settings.on_import_enabled),
        auto_enrich=bool(settings.auto_enrich_enabled),
    )
    _last_enqueue = []


def finish_capture_batch(summary: dict, session: Session | None = None) -> None:
    """Record suggestions from this batch that are still in the transaction.

    A per-row savepoint can roll back after the id was noted. Those ids
    are dropped so the summary and the enqueue list match committed rows.
    """
    global _batch, _last_enqueue
    batch = _batch
    _batch = None
    if batch is None:
        summary.setdefault("captured_categories", 0)
        _last_enqueue = []
        return
    surviving = _surviving_ids(session, batch.seen)
    summary["captured_categories"] = len(surviving)
    _last_enqueue = [item for item in batch.enqueue if item in surviving]


def take_import_category_enqueues() -> list[str]:
    """Return and clear suggestion ids that should be enriched."""
    global _last_enqueue
    ids = _last_enqueue
    _last_enqueue = []
    return ids


def import_enrichment_ids(*, dry_run: bool) -> list[str]:
    """Ids to enqueue after a committed import. Dry runs enqueue nothing."""
    ids = take_import_category_enqueues()
    if dry_run:
        return []
    return ids


def capture_enabled(session: Session) -> bool:
    """True when unknown names should be captured instead of failing."""
    if _batch is not None:
        return _batch.enabled
    return bool(get_settings(session).on_import_enabled)


def current_batch() -> CaptureBatch | None:
    """Return the active import batch, if one is open."""
    return _batch


def note_suggestion(suggestion_id: UUID, *, enqueue: bool) -> None:
    """Remember a suggestion touched by the current import batch."""
    if _batch is None:
        return
    _batch.seen.add(str(suggestion_id))
    if enqueue:
        _batch.enqueue.add(str(suggestion_id))


def resolve_category_name(session: Session, category_name: str) -> CategoryResolution:
    """Map a category name to an id, or ask the caller to capture it."""
    if not isinstance(category_name, str) or not category_name.strip():
        raise ValidationError("unknown category_name", field="category_name")
    name = category_name.strip()
    exact = _exact_ids(session, name)
    if len(exact) > 1:
        if capture_enabled(session):
            return CategoryResolution(capture=True)
        raise ValidationError("unknown category_name", field="category_name")
    if len(exact) == 1:
        return CategoryResolution(category_id=exact[0])
    alias = _alias_category_id(session, name)
    if alias is not None:
        return CategoryResolution(category_id=alias)
    normalized = _normalized_ids(session, name)
    if len(normalized) == 1:
        return CategoryResolution(category_id=next(iter(normalized)))
    if capture_enabled(session):
        return CategoryResolution(capture=True)
    raise ValidationError("unknown category_name", field="category_name")


def _exact_ids(session: Session, name: str) -> list[UUID]:
    query = (
        select(ActivityCategory.id)
        .where(ActivityCategory.name == name)
        .where(ActivityCategory.id != PENDING_CATEGORY_ID)
        .limit(2)
    )
    return list(session.execute(query).scalars().all())


def _alias_category_id(session: Session, name: str) -> UUID | None:
    fingerprint = normalize_category_key(name)
    if not fingerprint:
        return None
    suggestion = session.execute(
        select(CategorySuggestion).where(CategorySuggestion.fingerprint == fingerprint)
    ).scalar_one_or_none()
    if suggestion is None:
        return None
    target = suggestion.created_category_id or suggestion.merged_into_category_id
    if target is None:
        return None
    if session.get(ActivityCategory, target) is None:
        return None
    if target == PENDING_CATEGORY_ID:
        return None
    return target


def _surviving_ids(session: Session | None, ids: set[str]) -> set[str]:
    """Keep ids that still exist. A failed transaction keeps the in-memory set."""
    if session is None or not ids or not session.is_active:
        return set(ids)
    try:
        found = session.scalars(
            select(CategorySuggestion.id).where(
                CategorySuggestion.id.in_([UUID(item) for item in ids])
            )
        ).all()
    except SQLAlchemyError:
        logger.warning("Could not confirm captured category suggestions")
        return set(ids)
    return {str(item) for item in found}


def _normalized_ids(session: Session, name: str) -> set[UUID]:
    key = normalize_category_key(name)
    if not key:
        return set()
    index = _category_index(session)
    return set(index.get(key, set()))


def _category_index(session: Session) -> dict[str, set[UUID]]:
    if _batch is not None and _batch.index is not None:
        return _batch.index
    index: dict[str, set[UUID]] = {}
    rows = session.scalars(select(ActivityCategory)).all()
    for row in rows:
        if row.id == PENDING_CATEGORY_ID:
            continue
        keys = {normalize_category_key(row.name)}
        translations = row.name_translations or {}
        if isinstance(translations, dict):
            for value in translations.values():
                if isinstance(value, str) and value.strip():
                    keys.add(normalize_category_key(value))
        for key in keys:
            if not key:
                continue
            index.setdefault(key, set()).add(row.id)
    if _batch is not None:
        _batch.index = index
    return index


def alias_target_clause():
    """SQL fragment used by tests that inspect alias eligibility."""
    return or_(
        CategorySuggestion.created_category_id.is_not(None),
        CategorySuggestion.merged_into_category_id.is_not(None),
    )
