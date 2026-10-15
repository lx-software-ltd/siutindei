"""Shared accounting for model sweeps on the category-suggestion queue."""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.engine import get_engine
from app.exceptions import ValidationError

STALE_SWEEP_ERROR = "No batch completed before the sweep went stale"


def openrouter_timeout_seconds() -> int:
    raw = os.getenv("CATEGORY_SUGGESTION_OPENROUTER_TIMEOUT_SECONDS", "90")
    try:
        return max(10, int(raw))
    except ValueError:
        return 90


def confidence_score(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if number < 0:
        number = Decimal("0")
    if number > 1:
        number = Decimal("1")
    return number.quantize(Decimal("0.001"))


def rationale_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text[:500] or None


def parse_cost_limit(value: Any) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(
            "monthly_cost_limit_usd must be a number",
            field="monthly_cost_limit_usd",
        ) from exc
    if parsed <= 0 or parsed > 1000:
        raise ValidationError(
            "monthly_cost_limit_usd must be greater than 0 and at most 1000",
            field="monthly_cost_limit_usd",
        )
    return parsed


def month_total(session: Session, cost_column, created_column) -> float:
    """Sum sweep cost since the start of the UTC month."""
    start = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    value = session.scalar(
        select(func.coalesce(func.sum(cost_column), 0)).where(created_column >= start)
    )
    return float(value or 0)


def out_of_time(deadline: float | None) -> bool:
    return deadline is not None and time.monotonic() >= deadline


def take_limited(session: Session, stmt, limit: int) -> tuple[list, bool]:
    """Return at most `limit` rows and whether another row exists."""
    if limit <= 0:
        return [], False
    rows = list(session.scalars(stmt.limit(limit + 1)).all())
    if len(rows) > limit:
        return rows[:limit], True
    return rows, False


def chunk_entity_batches(
    queued: dict[str, list[str]], batch_size: int
) -> list[dict[str, Any]]:
    batches = []
    for entity_type, ids in queued.items():
        for index in range(0, len(ids), batch_size):
            batches.append(
                {
                    "entity_type": entity_type,
                    "entity_ids": ids[index : index + batch_size],
                }
            )
    return batches


def fail_open_run(run: Any, error: str) -> None:
    now = datetime.now(timezone.utc)
    run.status = "failed"
    run.error = error
    run.finished_at = now
    run.updated_at = now


def fail_stale_runs(
    session: Session,
    model: Any,
    *,
    stale_after: timedelta,
    active: tuple[str, ...],
    error: str = STALE_SWEEP_ERROR,
    on_each: Callable[[Any], None] | None = None,
) -> None:
    cutoff = datetime.now(timezone.utc) - stale_after
    now = datetime.now(timezone.utc)
    stale = session.scalars(
        select(model).where(
            model.status.in_(active),
            or_(model.updated_at < cutoff, model.updated_at.is_(None)),
        )
    ).all()
    for run in stale:
        run.status = "failed"
        run.error = error
        run.finished_at = now
        run.updated_at = now
        if on_each is not None:
            on_each(run)


def advance_scan_batch(
    run: Any,
    usage: dict[str, Any],
    message_id: str,
    *,
    failed: bool,
    failed_entities: int = 0,
    error: str | None = None,
    default_error: str,
    created: int = 0,
    updated: int = 0,
) -> bool:
    """Count one finished batch. Return True when the run reaches a terminal status."""
    if run is None or run.status in {"done", "failed"}:
        return False
    seen = [str(item) for item in (run.processed_message_ids or [])]
    if message_id and message_id not in seen:
        seen.append(message_id)
        run.processed_message_ids = seen
    cost = (usage or {}).get("cost_usd") or 0
    run.cost_usd = Decimal(str(run.cost_usd or 0)) + Decimal(str(round(float(cost), 6)))
    run.batches_done = int(run.batches_done or 0) + 1
    run.created_count = int(run.created_count or 0) + created
    run.updated_count = int(run.updated_count or 0) + updated
    if failed:
        run.failed_count = int(run.failed_count or 0) + failed_entities
        run.error = (error or default_error)[:500]
    now = datetime.now(timezone.utc)
    run.updated_at = now
    if run.batches_done < int(run.batches_total or 0):
        run.status = "running"
        return False
    failed_count = int(run.failed_count or 0)
    queued_count = int(run.queued_count or 0)
    run.status = "failed" if queued_count and failed_count >= queued_count else "done"
    run.finished_at = now
    return True


def mark_scan_enqueue_failed(model: Any, run_id: str, error: str) -> None:
    with Session(get_engine()) as session:
        try:
            parsed = UUID(str(run_id))
        except (TypeError, ValueError):
            return
        run = session.get(model, parsed)
        if run is None or run.status in {"done", "failed"}:
            return
        fail_open_run(run, error)
        session.commit()
