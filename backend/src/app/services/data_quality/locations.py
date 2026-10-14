"""Fingerprint for one location proposal."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.services.data_quality.fingerprint import fingerprint

LOCATION_CHECK_VERSION = "locations-1"


def location_input_hash(
    *,
    entity_type: str,
    entity_id: str | UUID,
    kind: str,
    source: str,
    proposed_location: dict[str, Any] | None,
    target_location_id: str | UUID | None,
    confidence: Any,
    rationale: str | None,
) -> str:
    """Hash the fields that decide a location proposal."""
    return fingerprint(
        {
            "version": LOCATION_CHECK_VERSION,
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "kind": kind,
            "source": source,
            "proposed_location": proposed_location or {},
            "target_location_id": (
                None if target_location_id is None else str(target_location_id)
            ),
            "confidence": None if confidence is None else str(confidence),
            "rationale": rationale or "",
        }
    )
