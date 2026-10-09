"""Model venue choices and the queue worker that runs them."""

from __future__ import annotations

import importlib.util
import json
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from app.db.models import (
    Activity,
    GeographicArea,
    Location,
    LocationFixProposal,
    LocationScanRun,
    Organization,
)
from app.services.location_fix_model import store_model_items
from psycopg.types.range import Range
from sqlalchemy import select

_MANAGER = "00000000-0000-0000-0000-000000000001"
_WORKER = None


def _worker():
    global _WORKER
    if _WORKER is None:
        path = (
            Path(__file__).resolve().parents[1]
            / "backend/lambda/category_suggestions/handler.py"
        )
        spec = importlib.util.spec_from_file_location(
            "category_suggestion_sqs_handler_locations",
            path,
        )
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)
        _WORKER = module
    return _WORKER


def _run(db_session) -> LocationScanRun:
    run = LocationScanRun(status="done", review_scope="all")
    db_session.add(run)
    db_session.flush()
    return run


def test_several_indexes_stay_unresolved_and_name_the_venues(
    db_session, sample_activity_category
) -> None:
    org = Organization(name="Index Club", manager_id=_MANAGER)
    db_session.add(org)
    db_session.flush()
    area = GeographicArea(name="灣仔", level="district", active=True)
    db_session.add(area)
    db_session.flush()
    first = Location(
        org_id=org.id,
        area_id=area.id,
        address="A Street",
        lat=Decimal("22.1"),
        lng=Decimal("114.1"),
    )
    second = Location(
        org_id=org.id,
        area_id=area.id,
        address="B Street",
        lat=Decimal("22.2"),
        lng=Decimal("114.2"),
    )
    activity = Activity(
        org_id=org.id,
        category_id=sample_activity_category.id,
        name="Art",
        age_range=Range(5, 12, bounds="[]"),
    )
    db_session.add_all([first, second, activity])
    db_session.flush()
    store_model_items(
        db_session,
        _run(db_session).id,
        "activity",
        [str(activity.id)],
        {
            "items": [
                {
                    "entity_id": str(activity.id),
                    "kind": "link_existing",
                    "location_indexes": [0, 1],
                    "rationale": "Both streets are named",
                }
            ]
        },
    )
    proposal = db_session.scalars(
        select(LocationFixProposal).where(LocationFixProposal.org_id == org.id)
    ).one()
    assert proposal.kind == "unresolved"
    assert proposal.target_location_id is None
    assert "A Street" in (proposal.rationale or "")
    assert "B Street" in (proposal.rationale or "")
    candidates = proposal.proposed_location["candidates"]
    assert {item["address"] for item in candidates} == {"A Street", "B Street"}


def test_location_message_is_handled_before_a_category_scan(monkeypatch) -> None:
    worker = _worker()
    called: dict[str, object] = {}

    def fake_location(
        scan_run_id, entity_type, entity_ids, *, message_id, receive_count
    ):
        called["location"] = (entity_type, entity_ids, message_id, receive_count)
        return True

    def fake_scan(*_args, **_kwargs):
        called["scan"] = True
        return True

    monkeypatch.setattr(worker, "process_location_batch", fake_location)
    monkeypatch.setattr(worker, "process_scan_batch", fake_scan)
    entity_id = str(uuid4())
    result = worker.lambda_handler(
        {
            "Records": [
                {
                    "messageId": "m-1",
                    "body": json.dumps(
                        {
                            "location_scan_run_id": str(uuid4()),
                            "scan_run_id": str(uuid4()),
                            "entity_type": "activity",
                            "entity_ids": [entity_id],
                        }
                    ),
                    "attributes": {"ApproximateReceiveCount": "2"},
                }
            ]
        },
        None,
    )
    assert called["location"] == ("activity", [entity_id], "m-1", 2)
    assert "scan" not in called
    assert result == {"batchItemFailures": []}


def test_lookup_message_is_routed_before_the_model(monkeypatch) -> None:
    worker = _worker()
    called: dict[str, object] = {}

    def fake_lookup(scan_run_id, provider, entity_ids, *, message_id, receive_count):
        called["lookup"] = (provider, entity_ids, message_id, receive_count)
        return True

    def fail_location(*_args, **_kwargs):
        raise AssertionError("lookup payload should not call the model")

    monkeypatch.setattr(worker, "process_lookup_batch", fake_lookup)
    monkeypatch.setattr(worker, "process_location_batch", fail_location)
    entity_id = str(uuid4())
    result = worker.lambda_handler(
        {
            "Records": [
                {
                    "messageId": "m-lookup",
                    "body": json.dumps(
                        {
                            "location_scan_run_id": str(uuid4()),
                            "entity_type": "location",
                            "lookup": "nominatim",
                            "entity_ids": [entity_id],
                        }
                    ),
                    "attributes": {"ApproximateReceiveCount": "1"},
                }
            ]
        },
        None,
    )
    assert called["lookup"] == ("nominatim", [entity_id], "m-lookup", 1)
    assert result == {"batchItemFailures": []}


def test_invalid_location_message_is_acknowledged(monkeypatch) -> None:
    worker = _worker()

    def fail_location(*_args, **_kwargs):
        raise AssertionError("invalid payload should not call the model")

    monkeypatch.setattr(worker, "process_location_batch", fail_location)
    result = worker.lambda_handler(
        {
            "Records": [
                {
                    "messageId": "m-2",
                    "body": json.dumps(
                        {"location_scan_run_id": str(uuid4()), "entity_type": "ticket"}
                    ),
                }
            ]
        },
        None,
    )
    assert result == {"batchItemFailures": []}
