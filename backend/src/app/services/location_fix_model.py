"""OpenRouter batches that propose a venue when rules cannot."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.engine import get_engine
from app.db.models import Activity, GeographicArea, Location, Organization
from app.db.models.location_fix import LocationScanRun
from app.services.category_suggestions.settings import (
    get_settings,
    resolved_fallback_models,
    resolved_model_name,
)
from app.services.location_fix_geocode import geocode_address
from app.services.location_fix_prompt import (
    build_activity_prompt,
    build_organization_prompt,
)
from app.services.location_fix_query import over_budget
from app.services.location_fixes import upsert_proposal
from app.services.openrouter_client import (
    OpenRouterError,
    extract_message_text,
    openrouter_chat_completion,
    usage_from_body,
)
from app.services.openrouter_json_parse import loads_openrouter_json
from app.utils.logging import get_logger

logger = get_logger(__name__)

WORKLOAD_LOCATION_FIX = "location-fix"


def process_location_batch(
    scan_run_id: UUID,
    entity_type: str,
    entity_ids: list[str],
    *,
    message_id: str = "",
    receive_count: int = 1,
) -> bool:
    """Propose venues for one batch. Return True when SQS can delete it."""
    prepared = _prepare(scan_run_id, entity_type, entity_ids, message_id)
    if prepared is None:
        return True
    system, user, model_name, fallbacks, deny = prepared
    try:
        body = openrouter_chat_completion(
            system_prompt=system,
            user_content=user,
            timeout=_timeout_seconds(),
            workload=WORKLOAD_LOCATION_FIX,
            temperature=0,
            max_attempts=1,
            model=model_name,
            fallback_models=fallbacks,
            deny_data_collection=deny,
        )
        parsed = loads_openrouter_json(
            extract_message_text(body),
            context="location sweep",
        )
        usage = usage_from_body(body)
    except OpenRouterError as exc:
        if receive_count >= 3:
            record_batch_failure(
                scan_run_id, entity_ids, str(exc), message_id=message_id
            )
        raise
    except Exception as exc:
        logger.exception(
            "Location sweep batch failed",
            extra={"scan_run_id": str(scan_run_id)},
        )
        record_batch_failure(
            scan_run_id,
            entity_ids,
            str(exc) or type(exc).__name__,
            message_id=message_id,
        )
        return True
    with Session(get_engine()) as session:
        store_model_items(
            session,
            scan_run_id,
            entity_type,
            entity_ids,
            parsed if isinstance(parsed, dict) else {},
        )
        _finish_batch(session, scan_run_id, usage, message_id, failed=False)
        session.commit()
    return True


def store_model_items(
    session: Session,
    scan_run_id: UUID,
    entity_type: str,
    entity_ids: list[str],
    payload: dict[str, Any],
) -> None:
    """Persist one model response. Omitted entities become unresolved."""
    wanted = []
    for raw in entity_ids:
        try:
            wanted.append(UUID(str(raw)))
        except ValueError:
            continue
    items = payload.get("items") if isinstance(payload, dict) else None
    by_id: dict[str, dict[str, Any]] = {}
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and item.get("entity_id"):
                by_id[str(item["entity_id"])] = item
    if entity_type == "organization":
        _store_organizations(session, scan_run_id, wanted, by_id)
        return
    if entity_type == "activity":
        _store_activities(session, scan_run_id, wanted, by_id)


def record_batch_failure(
    scan_run_id: UUID,
    entity_ids: list[str],
    message: str,
    *,
    message_id: str,
) -> None:
    with Session(get_engine()) as session:
        _finish_batch(
            session,
            scan_run_id,
            {},
            message_id,
            failed=True,
            failed_entities=len(entity_ids),
            error=message,
        )
        session.commit()


def _store_organizations(session, scan_run_id, org_ids, by_id) -> None:
    areas = _areas_by_label(session)
    orgs = {
        org.id: org
        for org in session.scalars(
            select(Organization).where(Organization.id.in_(org_ids))
        ).all()
    }
    for org_id in org_ids:
        org = orgs.get(org_id)
        if org is None:
            continue
        item = by_id.get(str(org_id), {})
        kind = item.get("kind")
        area = areas.get(_label_key(item.get("area_name")))
        address = str(item.get("address") or "").strip()
        if kind == "create_location" and area is not None and address:
            coords = geocode_address(address)
            proposed = {
                "address": address,
                "area_id": str(area.id),
                "area_name": area.name,
                "lat": None if coords is None else coords[0],
                "lng": None if coords is None else coords[1],
            }
            upsert_proposal(
                session,
                entity_type="organization",
                entity_id=org.id,
                org_id=org.id,
                kind="create_location",
                source="model",
                proposed_location=proposed,
                confidence=_confidence(item.get("confidence")),
                rationale=_rationale(item.get("rationale")),
                scan_run_id=scan_run_id,
            )
            continue
        upsert_proposal(
            session,
            entity_type="organization",
            entity_id=org.id,
            org_id=org.id,
            kind="unresolved",
            source="model",
            confidence=_confidence(item.get("confidence")),
            rationale=_rationale(item.get("rationale"))
            or "Model could not propose an address",
            scan_run_id=scan_run_id,
        )


def _store_activities(session, scan_run_id, activity_ids, by_id) -> None:
    activities = {
        activity.id: activity
        for activity in session.scalars(
            select(Activity).where(Activity.id.in_(activity_ids))
        ).all()
    }
    org_ids = {activity.org_id for activity in activities.values()}
    locations: dict[Any, list[Location]] = {}
    if org_ids:
        for location in session.scalars(
            select(Location)
            .where(Location.org_id.in_(org_ids))
            .order_by(Location.address, Location.id)
        ).all():
            locations.setdefault(location.org_id, []).append(location)
    for activity_id in activity_ids:
        activity = activities.get(activity_id)
        if activity is None:
            continue
        item = by_id.get(str(activity_id), {})
        venues = locations.get(activity.org_id, [])
        indexes = item.get("location_indexes")
        chosen = None
        if (
            item.get("kind") == "link_existing"
            and isinstance(indexes, list)
            and len(indexes) == 1
        ):
            try:
                index = int(indexes[0])
            except (TypeError, ValueError):
                index = -1
            if 0 <= index < len(venues):
                chosen = venues[index]
        if chosen is not None:
            upsert_proposal(
                session,
                entity_type="activity",
                entity_id=activity.id,
                org_id=activity.org_id,
                kind="link_existing",
                source="model",
                target_location_id=chosen.id,
                confidence=_confidence(item.get("confidence")),
                rationale=_rationale(item.get("rationale")),
                scan_run_id=scan_run_id,
            )
            continue
        upsert_proposal(
            session,
            entity_type="activity",
            entity_id=activity.id,
            org_id=activity.org_id,
            kind="unresolved",
            source="model",
            confidence=_confidence(item.get("confidence")),
            rationale=_rationale(item.get("rationale"))
            or "Model could not choose a venue",
            scan_run_id=scan_run_id,
        )


def _prepare(scan_run_id, entity_type, entity_ids, message_id):
    with Session(get_engine()) as session:
        run = session.get(LocationScanRun, scan_run_id)
        if run is None or run.status in {"done", "failed"}:
            return None
        seen = [str(item) for item in (run.processed_message_ids or [])]
        if message_id and message_id in seen:
            return None
        if over_budget(session):
            now = datetime.now(timezone.utc)
            run.status = "failed"
            run.error = "Monthly location-sweep budget is used"
            run.finished_at = now
            run.updated_at = now
            session.commit()
            return None
        ids = []
        for raw in entity_ids:
            try:
                ids.append(UUID(str(raw)))
            except ValueError:
                continue
        if entity_type == "organization":
            rows = list(
                session.scalars(
                    select(Organization).where(Organization.id.in_(ids))
                ).all()
            )
            if not rows:
                _finish_batch(session, scan_run_id, {}, message_id, failed=False)
                session.commit()
                return None
            system, user = build_organization_prompt(session, rows)
        elif entity_type == "activity":
            rows = list(
                session.scalars(select(Activity).where(Activity.id.in_(ids))).all()
            )
            if not rows:
                _finish_batch(session, scan_run_id, {}, message_id, failed=False)
                session.commit()
                return None
            org_ids = {row.org_id for row in rows}
            locations: dict[Any, list[Location]] = {}
            area_ids = set()
            for location in session.scalars(
                select(Location)
                .where(Location.org_id.in_(org_ids))
                .order_by(Location.address, Location.id)
            ).all():
                locations.setdefault(location.org_id, []).append(location)
                area_ids.add(location.area_id)
            area_names = {}
            if area_ids:
                area_names = {
                    area.id: area.name
                    for area in session.scalars(
                        select(GeographicArea).where(GeographicArea.id.in_(area_ids))
                    ).all()
                }
            system, user = build_activity_prompt(session, rows, locations, area_names)
        else:
            return None
        settings = get_settings(session)
        return (
            system,
            user,
            resolved_model_name(settings.openrouter_model),
            resolved_fallback_models(settings.fallback_models),
            bool(settings.deny_data_collection),
        )


def _finish_batch(
    session: Session,
    scan_run_id: UUID,
    usage: dict[str, Any],
    message_id: str,
    *,
    failed: bool,
    failed_entities: int = 0,
    error: str | None = None,
) -> None:
    run = session.get(LocationScanRun, scan_run_id)
    if run is None or run.status in {"done", "failed"}:
        return
    seen = [str(item) for item in (run.processed_message_ids or [])]
    if message_id and message_id not in seen:
        seen.append(message_id)
        run.processed_message_ids = seen
    cost = usage.get("cost_usd") or 0
    run.cost_usd = Decimal(str(run.cost_usd or 0)) + Decimal(str(round(float(cost), 6)))
    run.batches_done = int(run.batches_done or 0) + 1
    if failed:
        run.failed_count = int(run.failed_count or 0) + failed_entities
        run.error = (error or "Location sweep batch failed")[:500]
    now = datetime.now(timezone.utc)
    run.updated_at = now
    if run.batches_done < int(run.batches_total or 0):
        run.status = "running"
        return
    failed_count = int(run.failed_count or 0)
    queued_count = int(run.queued_count or 0)
    run.status = "failed" if queued_count and failed_count >= queued_count else "done"
    run.finished_at = now


def _areas_by_label(session: Session) -> dict[str, GeographicArea]:
    rows = session.scalars(
        select(GeographicArea).where(
            GeographicArea.level == "district",
            GeographicArea.active.is_(True),
        )
    ).all()
    found: dict[str, GeographicArea] = {}
    for area in rows:
        found[_label_key(area.name)] = area
        for value in (area.name_translations or {}).values():
            found[_label_key(value)] = area
    found.pop("", None)
    return found


def _label_key(value: Any) -> str:
    return str(value or "").strip().casefold()


def _confidence(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except Exception:
        return None
    if number < 0:
        number = Decimal("0")
    if number > 1:
        number = Decimal("1")
    return number.quantize(Decimal("0.001"))


def _rationale(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text[:500] or None


def _timeout_seconds() -> int:
    raw = os.getenv("CATEGORY_SUGGESTION_OPENROUTER_TIMEOUT_SECONDS", "90")
    try:
        return max(10, int(raw))
    except ValueError:
        return 90
