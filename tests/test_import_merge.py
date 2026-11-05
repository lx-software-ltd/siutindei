"""Per-field import decisions."""

from uuid import uuid4

import pytest
from app.api.admin_imports_importer import process_import_payload
from app.db.models import ImportChangeProposal, ImportSettings, Organization
from app.services.import_merge import decide_fields
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.test_import_versions import reset_import_mode


@pytest.fixture(autouse=True)
def _merge_defaults(test_engine) -> None:
    reset_import_mode(test_engine)


def _org(description: str = "Original", **extra: object) -> dict:
    body = {"name": "Harbour Club", "description": description, "manager_id": "m"}
    body.update(extra)
    return body


def test_decision_table_for_each_entity() -> None:
    cases = (
        (
            "organization",
            {"name": "Harbour Club", "description": "Same"},
            {"description"},
        ),
        (
            "activity",
            {"name": "Swim", "age_min": 5, "age_max": 8},
            {"age_min", "age_max"},
        ),
        (
            "location",
            {"address": "1 Pier", "lat": "22.100000", "lng": "114.100000"},
            {"lat"},
        ),
        (
            "pricing",
            {
                "location_address": "1 Pier",
                "pricing_type": "per_session",
                "amount": "10.00",
            },
            {"amount"},
        ),
        (
            "schedule",
            {
                "location_address": "1 Pier",
                "languages": ["en"],
                "entries": [
                    {
                        "day_of_week_utc": 1,
                        "start_minutes_utc": 600,
                        "end_minutes_utc": 660,
                    }
                ],
            },
            {"weekly_entries"},
        ),
    )
    for entity_type, base, present in cases:
        same = decide_fields(entity_type, base, base, base, present, mode="merge")
        assert same.status == "unchanged"
        file = dict(base)
        if entity_type == "schedule":
            file = {key: value for key, value in base.items() if key != "entries"}
            file["weekly_entries"] = [
                {
                    "day_of_week_utc": 2,
                    "start_minutes_utc": 600,
                    "end_minutes_utc": 660,
                }
            ]
            edited = {
                **base,
                "entries": [
                    {
                        "day_of_week_utc": 3,
                        "start_minutes_utc": 600,
                        "end_minutes_utc": 660,
                    }
                ],
            }
            applied = decide_fields(
                entity_type, base, base, file, present, mode="merge"
            )
            conflict = decide_fields(
                entity_type, base, edited, file, present, mode="merge"
            )
        else:
            key = "age_min" if entity_type == "activity" else min(present)
            file[key] = 9 if key in {"age_min", "age_max", "lat"} else "Next"
            if key == "amount":
                file[key] = "12.00"
            edited = dict(base)
            edited[key] = 3 if key in {"age_min", "age_max", "lat"} else "Mine"
            if key == "amount":
                edited[key] = "8.00"
            applied = decide_fields(
                entity_type, base, base, file, present, mode="merge"
            )
            conflict = decide_fields(
                entity_type, base, edited, file, present, mode="merge"
            )
        assert applied.status is None
        assert any(change.action == "apply" for change in applied.changes)
        already = decide_fields(entity_type, base, file, file, present, mode="merge")
        assert already.status == "unchanged"
        assert conflict.status == "proposed"
        assert any(change.action == "proposal" for change in conflict.changes)


def test_omitted_fields_are_not_decided() -> None:
    base = _org()
    live = _org(description="Admin")
    plan = decide_fields(
        "organization",
        base,
        live,
        {"name": "Harbour Club"},
        {"name"},
        mode="merge",
    )
    assert plan.status == "unchanged"
    assert "description" not in {change.field for change in plan.changes}


def test_normalisation_treats_pins_names_and_slots_as_equal() -> None:
    location = decide_fields(
        "location",
        {"address": "1 Pier", "lat": 22.1234564, "lng": 114.1},
        {"address": "1 Pier", "lat": "22.123456", "lng": "114.100000"},
        {"address": "  1   Pier ", "lat": 22.1234561, "lng": 114.1},
        {"address", "lat", "lng"},
        mode="merge",
    )
    assert location.status == "unchanged"
    schedule = decide_fields(
        "schedule",
        {
            "location_address": "1 Pier",
            "languages": ["zh", "en"],
            "weekly_entries": [
                {"day_of_week": 1, "start_minutes": 600, "end_minutes": 660}
            ],
        },
        {
            "location_address": "1 Pier",
            "languages": ["en", "zh"],
            "entries": [
                {"day_of_week_utc": 1, "start_minutes_utc": 600, "end_minutes_utc": 660}
            ],
        },
        {
            "location_address": "1 Pier",
            "languages": ["en", "zh"],
            "weekly_entries": [
                {"day_of_week_utc": 1, "start_minutes_utc": 600, "end_minutes_utc": 660}
            ],
        },
        {"languages", "weekly_entries", "location_address"},
        mode="merge",
    )
    assert schedule.status == "unchanged"


def test_propose_mode_queues_a_clean_change(test_engine) -> None:
    name = f"Propose Org {uuid4()}"
    manager_id = "00000000-0000-0000-0000-000000000061"
    with Session(test_engine) as session:
        settings = session.get(ImportSettings, 1)
        if settings is None:
            settings = ImportSettings(id=1)
            session.add(settings)
        settings.existing_rows = "propose"
        org = Organization(name=name, description="Original", manager_id=manager_id)
        session.add(org)
        session.flush()
        from tests.test_import_versions import _remember

        _remember(session, org)
        session.commit()
        org_id = org.id

    with Session(test_engine) as session:
        _summary, results = process_import_payload(
            session,
            {
                "organizations": [
                    {"name": name, "description": "From file", "manager_id": manager_id}
                ]
            },
            [],
            allow_org_updates=True,
        )

    assert results[0]["status"] == "proposed"
    with Session(test_engine) as session:
        found = session.get(Organization, org_id)
        assert found is not None
        assert found.description == "Original"
        pending = session.scalars(select(ImportChangeProposal)).all()
        assert len(pending) == 1
        assert pending[0].field == "description"


def test_approved_organization_queues_a_clean_change(test_engine) -> None:
    name = f"Approved Org {uuid4()}"
    manager_id = "00000000-0000-0000-0000-000000000062"
    with Session(test_engine) as session:
        org = Organization(
            name=name,
            description="Original",
            manager_id=manager_id,
            review_status="approved",
        )
        session.add(org)
        session.flush()
        from tests.test_import_versions import _remember

        _remember(session, org)
        session.commit()
        org_id = org.id

    with Session(test_engine) as session:
        _summary, results = process_import_payload(
            session,
            {
                "organizations": [
                    {"name": name, "description": "From file", "manager_id": manager_id}
                ]
            },
            [],
            allow_org_updates=True,
        )

    assert results[0]["status"] == "proposed"
    with Session(test_engine) as session:
        found = session.get(Organization, org_id)
        assert found is not None
        assert found.description == "Original"
