"""Fingerprints for category checks."""

from __future__ import annotations

from typing import Any

from app.services.data_quality.fingerprint import fingerprint

CATEGORY_PROMPT_VERSION = "verify-1"
CATEGORY_CHECK_VERSION = "category-verify-1"


def category_input_hash(
    activity: Any,
    *,
    model: str,
    threshold: float | None,
) -> str:
    """Hash the activity text, category, prompt, model, and threshold."""
    return fingerprint(
        {
            "version": CATEGORY_CHECK_VERSION,
            "prompt_version": CATEGORY_PROMPT_VERSION,
            "name": activity.name or "",
            "description": activity.description or "",
            "category_id": ""
            if activity.category_id is None
            else str(activity.category_id),
            "source_category_name": activity.source_category_name or "",
            "model": model or "",
            "auto_assign_threshold": None if threshold is None else str(threshold),
        }
    )
