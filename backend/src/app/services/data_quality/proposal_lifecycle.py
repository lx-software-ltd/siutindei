"""Shared proposal lifecycle for translation, name, and location sweeps.

``ProposalKind`` order is translations, then names, then locations.
Kind-specific query and apply rules stay in the existing service modules.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.category_suggestions.events import (
    enqueue_location_batches,
    enqueue_translation_batches,
)
from app.services.location_fix_query import (
    get_proposal as get_location_proposal,
)
from app.services.location_fix_query import (
    list_proposals as list_location_proposals,
)
from app.services.location_fix_query import (
    settings_payload as location_settings,
)
from app.services.location_fix_query import (
    summarize_proposals as summarize_locations,
)
from app.services.location_fix_query import (
    update_settings as update_location_settings,
)
from app.services.location_fix_scan import LocationScanBusy, start_location_scan
from app.services.location_fixes import (
    decide_bulk as decide_locations_bulk,
)
from app.services.location_fixes import (
    decide_proposal as decide_location,
)
from app.services.name_fix_scan import scan_names
from app.services.name_fixes import (
    decide_bulk as decide_names_bulk,
)
from app.services.name_fixes import (
    decide_proposal as decide_name,
)
from app.services.name_fixes import (
    get_proposal as get_name_proposal,
)
from app.services.name_fixes import (
    list_proposals as list_name_proposals,
)
from app.services.name_fixes import (
    settings_payload as name_settings,
)
from app.services.name_fixes import (
    summarize_proposals as summarize_names,
)
from app.services.name_fixes import (
    update_settings as update_name_settings,
)
from app.services.translation_fix_query import (
    get_proposal as get_translation_proposal,
)
from app.services.translation_fix_query import (
    list_proposals as list_translation_proposals,
)
from app.services.translation_fix_query import (
    settings_payload as translation_settings,
)
from app.services.translation_fix_query import (
    summarize_proposals as summarize_translations,
)
from app.services.translation_fix_query import (
    update_settings as update_translation_settings,
)
from app.services.translation_fix_scan import (
    TranslationScanBusy,
    start_translation_scan,
)
from app.services.translation_fixes import (
    decide_bulk as decide_translations_bulk,
)
from app.services.translation_fixes import (
    decide_proposal as decide_translation,
)


class ProposalKind(Enum):
    """Which proposal table a lifecycle call addresses."""

    TRANSLATIONS = "translations"
    NAMES = "names"
    LOCATIONS = "locations"


PROPOSAL_KIND_ORDER: tuple[ProposalKind, ...] = (
    ProposalKind.TRANSLATIONS,
    ProposalKind.NAMES,
    ProposalKind.LOCATIONS,
)


class ScanBusy(Exception):
    """A sweep of this kind is already queued or running."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class ScanStarted:
    """Result of starting a sweep, including batches to enqueue after commit."""

    payload: dict[str, Any]
    batches: list[dict[str, Any]]
    run_model: type | None
    enqueue: Callable[[str, list[dict[str, Any]]], None] | None
    enqueue_error: str
    enqueue_log: str


@dataclass(frozen=True)
class _KindOps:
    list_proposals: Callable[..., dict[str, Any]]
    get_proposal: Callable[..., dict[str, Any]]
    summarize: Callable[[Session], dict[str, Any]]
    settings_payload: Callable[[Session], dict[str, Any]]
    update_settings: Callable[[Session, dict[str, Any]], dict[str, Any]]
    start_scan: Callable[..., Any]
    decide: Callable[..., dict[str, Any]]
    bulk_decide: Callable[..., dict[str, Any]]
    busy_type: type[Exception] | None
    busy_message: str
    enqueue: Callable[[str, list[dict[str, Any]]], None] | None
    run_model: type | None
    enqueue_error: str
    enqueue_log: str


def _translation_ops() -> _KindOps:
    from app.db.models.translation_fix import TranslationScanRun

    return _KindOps(
        list_proposals=list_translation_proposals,
        get_proposal=get_translation_proposal,
        summarize=summarize_translations,
        settings_payload=translation_settings,
        update_settings=update_translation_settings,
        start_scan=start_translation_scan,
        decide=decide_translation,
        bulk_decide=decide_translations_bulk,
        busy_type=TranslationScanBusy,
        busy_message="A translation sweep is already running",
        enqueue=enqueue_translation_batches,
        run_model=TranslationScanRun,
        enqueue_error="Translation sweep could not be queued",
        enqueue_log="Translation sweep enqueue failed",
    )


def _name_ops() -> _KindOps:
    return _KindOps(
        list_proposals=list_name_proposals,
        get_proposal=get_name_proposal,
        summarize=summarize_names,
        settings_payload=name_settings,
        update_settings=update_name_settings,
        start_scan=scan_names,
        decide=decide_name,
        bulk_decide=decide_names_bulk,
        busy_type=None,
        busy_message="",
        enqueue=None,
        run_model=None,
        enqueue_error="",
        enqueue_log="",
    )


def _location_ops() -> _KindOps:
    from app.db.models.location_fix import LocationScanRun

    return _KindOps(
        list_proposals=list_location_proposals,
        get_proposal=get_location_proposal,
        summarize=summarize_locations,
        settings_payload=location_settings,
        update_settings=update_location_settings,
        start_scan=start_location_scan,
        decide=decide_location,
        bulk_decide=decide_locations_bulk,
        busy_type=LocationScanBusy,
        busy_message="A location sweep is already running",
        enqueue=enqueue_location_batches,
        run_model=LocationScanRun,
        enqueue_error="Location sweep could not be queued",
        enqueue_log="Location sweep enqueue failed",
    )


_OPS: dict[ProposalKind, _KindOps] = {
    ProposalKind.TRANSLATIONS: _translation_ops(),
    ProposalKind.NAMES: _name_ops(),
    ProposalKind.LOCATIONS: _location_ops(),
}


def _ops(kind: ProposalKind) -> _KindOps:
    try:
        return _OPS[kind]
    except KeyError as exc:
        raise ValueError(f"Unknown proposal kind: {kind}") from exc


def list_proposals(
    kind: ProposalKind,
    session: Session,
    **filters: Any,
) -> dict[str, Any]:
    """List proposals for ``kind`` using that kind's existing filters."""
    return _ops(kind).list_proposals(session, **filters)


def get_proposal(
    kind: ProposalKind,
    session: Session,
    proposal_id: UUID,
) -> dict[str, Any]:
    """Return one proposal payload."""
    return _ops(kind).get_proposal(session, proposal_id)


def summarize_proposals(kind: ProposalKind, session: Session) -> dict[str, Any]:
    """Return the existing summary payload for ``kind``."""
    return _ops(kind).summarize(session)


def settings_payload(kind: ProposalKind, session: Session) -> dict[str, Any]:
    """Return the settings document for ``kind``."""
    return _ops(kind).settings_payload(session)


def update_settings(
    kind: ProposalKind,
    session: Session,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Update settings for ``kind``. The caller commits."""
    return _ops(kind).update_settings(session, body)


def start_scan(kind: ProposalKind, session: Session, **kwargs: Any) -> ScanStarted:
    """Start a sweep. Raises ``ScanBusy`` when that kind is already running."""
    ops = _ops(kind)
    try:
        result = ops.start_scan(session, **kwargs)
    except Exception as exc:
        if ops.busy_type is not None and isinstance(exc, ops.busy_type):
            raise ScanBusy(ops.busy_message) from exc
        raise
    if isinstance(result, tuple):
        payload, batches = result
    else:
        payload, batches = result, []
    return ScanStarted(
        payload=payload,
        batches=list(batches or []),
        run_model=ops.run_model,
        enqueue=ops.enqueue,
        enqueue_error=ops.enqueue_error,
        enqueue_log=ops.enqueue_log,
    )


def decide(
    kind: ProposalKind,
    session: Session,
    proposal_id: UUID,
    action: str,
    decided_by: str | None,
    **extras: Any,
) -> dict[str, Any]:
    """Apply or dismiss one proposal. The caller commits."""
    ops = _ops(kind)
    if kind is ProposalKind.NAMES:
        return ops.decide(
            session,
            proposal_id,
            action,
            extras.get("value"),
            decided_by,
        )
    if kind is ProposalKind.TRANSLATIONS:
        return ops.decide(
            session,
            proposal_id,
            action,
            decided_by,
            translations=extras.get("translations"),
        )
    return ops.decide(
        session,
        proposal_id,
        action,
        decided_by,
        address=extras.get("address"),
        area_id=extras.get("area_id"),
        target_location_id=extras.get("target_location_id"),
        lat=extras.get("lat"),
        lng=extras.get("lng"),
    )


def bulk_decide(
    kind: ProposalKind,
    session: Session,
    body: dict[str, Any],
    decided_by: str | None,
) -> dict[str, Any]:
    """Apply or dismiss a filtered set. The caller commits unless dry_run."""
    return _ops(kind).bulk_decide(session, body, decided_by)
