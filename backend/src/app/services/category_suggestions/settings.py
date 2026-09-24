"""Admin settings for category capture and the OpenRouter model."""

from __future__ import annotations

import re
from datetime import datetime
from datetime import timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.category_suggestion import (
    DEFAULT_OPENROUTER_MODEL,
    CategorySuggestionSettings,
)
from app.db.repositories.category_suggestion import (
    CategorySuggestionSettingsRepository,
)
from app.exceptions import ValidationError

MODEL_SLUG_RE = re.compile(r"^[a-z0-9-]+/[a-z0-9._:-]+$")
MODEL_SLUG_MAX_LENGTH = 128
MAX_FALLBACKS = 3


def get_settings(session: Session) -> CategorySuggestionSettings:
    """Return the singleton settings row."""
    return CategorySuggestionSettingsRepository(session).get_or_create()


def load_model_name() -> str | None:
    """Return the stored model slug, or None when the default should apply."""
    from app.db.engine import get_engine

    with Session(get_engine()) as session:
        row = get_settings(session)
        raw = (row.openrouter_model or "").strip()
        return raw or None


def load_fallback_models() -> list[str]:
    """Return configured fallback model slugs."""
    from app.db.engine import get_engine

    with Session(get_engine()) as session:
        row = get_settings(session)
        values = row.fallback_models or []
        return [str(item).strip() for item in values if str(item).strip()]


def load_deny_data_collection() -> bool:
    """Return whether prompts must stay on non-retaining providers."""
    from app.db.engine import get_engine

    with Session(get_engine()) as session:
        return bool(get_settings(session).deny_data_collection)


def validate_model_slug(value: str, field: str) -> str:
    """Validate one OpenRouter model id."""
    slug = value.strip()
    if not slug:
        raise ValidationError(f"{field} is required", field=field)
    if len(slug) > MODEL_SLUG_MAX_LENGTH or MODEL_SLUG_RE.fullmatch(slug) is None:
        raise ValidationError(
            f"{field} must look like vendor/model",
            field=field,
        )
    return slug


def apply_settings_update(
    session: Session,
    body: dict[str, Any],
    *,
    updated_by: str | None,
) -> CategorySuggestionSettings:
    """Validate and store a settings update. Clears the model cache."""
    row = get_settings(session)
    if "on_import_enabled" in body:
        row.on_import_enabled = _parse_bool(
            body["on_import_enabled"], "on_import_enabled"
        )
    if "auto_enrich_enabled" in body:
        row.auto_enrich_enabled = _parse_bool(
            body["auto_enrich_enabled"],
            "auto_enrich_enabled",
        )
    if "deny_data_collection" in body:
        row.deny_data_collection = _parse_bool(
            body["deny_data_collection"],
            "deny_data_collection",
        )
    if "openrouter_model" in body:
        raw = body["openrouter_model"]
        if raw in (None, ""):
            row.openrouter_model = None
        else:
            row.openrouter_model = validate_model_slug(str(raw), "openrouter_model")
    if "fallback_models" in body:
        row.fallback_models = _parse_fallbacks(body["fallback_models"])
    if "max_evidence_items" in body:
        row.max_evidence_items = _parse_evidence(body["max_evidence_items"])
    row.updated_by = updated_by
    row.updated_at = datetime.now(timezone.utc)
    session.flush()
    from app.services.openrouter_client import clear_openrouter_model_cache

    clear_openrouter_model_cache()
    return row


def serialize_settings(row: CategorySuggestionSettings) -> dict[str, Any]:
    """Serialize settings for the admin API."""
    return {
        "on_import_enabled": bool(row.on_import_enabled),
        "auto_enrich_enabled": bool(row.auto_enrich_enabled),
        "openrouter_model": row.openrouter_model,
        "default_openrouter_model": DEFAULT_OPENROUTER_MODEL,
        "fallback_models": list(row.fallback_models or []),
        "max_evidence_items": int(row.max_evidence_items),
        "deny_data_collection": bool(row.deny_data_collection),
        "updated_by": row.updated_by,
        "updated_at": row.updated_at,
    }


def _parse_bool(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false", "1", "0"}:
        return value.strip().lower() in {"true", "1"}
    raise ValidationError(f"{field} must be a boolean", field=field)


def _parse_evidence(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            "max_evidence_items must be an integer",
            field="max_evidence_items",
        ) from exc
    if parsed < 5 or parsed > 50:
        raise ValidationError(
            "max_evidence_items must be between 5 and 50",
            field="max_evidence_items",
        )
    return parsed


def _parse_fallbacks(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError(
            "fallback_models must be a list",
            field="fallback_models",
        )
    if len(value) > MAX_FALLBACKS:
        raise ValidationError(
            f"fallback_models accepts at most {MAX_FALLBACKS} slugs",
            field="fallback_models",
        )
    return [validate_model_slug(str(item), "fallback_models") for item in value]
