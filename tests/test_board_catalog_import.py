"""Board catalog bulk-import acceptance tests."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.admin_imports_importer import process_import_payload
from app.api.admin_imports_jobs import (
    find_import_job_by_key,
    serialize_import_job,
    store_import_job,
)
from app.db.models import Organization


CATALOG_MANAGER = "00000000-0000-0000-0000-000000000088"


def _board_org(
    index: int,
    *,
    category_name: str,
    area_name: str,
    place_id: str | None = None,
    name: str | None = None,
    status: str | None = None,
) -> dict:
    org_name = name or f"Board Playground {index:02d}"
    payload = {
        "name": org_name,
        "name_zh": "",
        "manager_id": CATALOG_MANAGER,
        "area_name": area_name,
        "category_name": category_name,
        "address": f"{index} Park Road, Eastern",
        "description": f"{org_name} is a public outdoor venue.",
        "description_zh": "",
        "vetting_note": (
            f"source=lcsd; sourceId=lcsd-{index}; descriptionSource=template"
        ),
        "lat": 22.291,
        "lng": 114.216,
        "activities": [
            {
                "name": org_name,
                "category_name": category_name,
                "description": f"{org_name} is a public outdoor venue.",
                "vetting_note": (
                    f"source=lcsd; sourceId=lcsd-{index}; "
                    "descriptionSource=template"
                ),
            }
        ],
    }
    if place_id:
        payload["place_id"] = place_id
    if status:
        payload["status"] = status
    return payload


def test_fifty_org_batch_place_id_and_unknown_category(
    db_session,
    sample_activity_category,
    sample_geographic_area,
) -> None:
    batch = uuid4().hex[:8]
    orgs = []
    shared_place = f"ChIJ-{batch}-03"
    for index in range(1, 51):
        category = sample_activity_category.name
        if index == 7:
            category = "Unknown Category"
        place_id = f"ChIJ-{batch}-{index:02d}"
        name = f"Board {batch} Playground {index:02d}"
        if index == 12:
            place_id = shared_place
            name = f"Board {batch} Playground 12 renamed"
        if index == 3:
            place_id = shared_place
        orgs.append(
            _board_org(
                index,
                category_name=category,
                area_name=sample_geographic_area.name,
                place_id=place_id,
                name=name,
            )
        )

    warnings: list[str] = []
    summary, results = process_import_payload(
        db_session,
        {"organizations": orgs},
        warnings,
        allow_org_updates=True,
        catalog_manager_id=CATALOG_MANAGER,
    )
    assert summary["organizations"]["created"] == 48
    assert summary["organizations"]["updated"] == 1
    assert summary["organizations"]["failed"] == 1
    org_results = [row for row in results if row["type"] == "organizations"]
    failed = next(row for row in org_results if row["status"] == "failed")
    assert failed["key"].startswith(f"Board {batch} Playground 07")
    updated = next(row for row in org_results if row["status"] == "updated")
    assert updated["key"] == f"Board {batch} Playground 12 renamed"
    assert updated["place_id"] == shared_place

    stored = store_import_job(
        db_session,
        f"admin/imports/board-catalog-{batch}.json",
        dry_run=False,
        summary=summary,
        results=results,
        file_warnings=warnings,
    )
    again = find_import_job_by_key(
        db_session,
        f"admin/imports/board-catalog-{batch}.json",
    )
    assert again is not None
    assert again.id == stored.id
    replay = serialize_import_job(again)
    assert replay["summary"]["organizations"]["created"] == 48
    assert replay["results"] == results


def test_closed_permanently_updates_and_hides_from_search(
    db_session,
    sample_activity_category,
    sample_geographic_area,
) -> None:
    name = f"Close Me Park {uuid4()}"
    process_import_payload(
        db_session,
        {
            "organizations": [
                _board_org(
                    1,
                    category_name=sample_activity_category.name,
                    area_name=sample_geographic_area.name,
                    place_id="ChIJ-close-me",
                    name=name,
                )
            ]
        },
        [],
        allow_org_updates=True,
        catalog_manager_id=CATALOG_MANAGER,
    )
    org = db_session.execute(
        select(Organization).where(Organization.name == name)
    ).scalar_one()
    assert org.status == "operational"

    summary, results = process_import_payload(
        db_session,
        {
            "organizations": [
                _board_org(
                    1,
                    category_name=sample_activity_category.name,
                    area_name=sample_geographic_area.name,
                    place_id="ChIJ-close-me",
                    name=name,
                    status="closed_permanently",
                )
            ]
        },
        [],
        allow_org_updates=True,
        catalog_manager_id=CATALOG_MANAGER,
    )
    assert results[0]["status"] == "updated"
    assert summary["organizations"]["updated"] == 1
    db_session.refresh(org)
    assert org.status == "closed_permanently"
    assert org.status_source == "importer"

    admin_found = db_session.execute(
        select(Organization).where(Organization.id == org.id)
    ).scalar_one()
    assert admin_found.name == name

    public_ids = {
        row.id
        for row in db_session.execute(
            select(Organization).where(
                Organization.status.in_(
                    ("operational", "closed_temporarily")
                )
            )
        ).scalars()
    }
    assert org.id not in public_ids


def test_closed_permanently_without_match_does_not_create(
    db_session,
    sample_activity_category,
    sample_geographic_area,
) -> None:
    name = f"Never Existed Park {uuid4()}"
    summary, results = process_import_payload(
        db_session,
        {
            "organizations": [
                _board_org(
                    1,
                    category_name=sample_activity_category.name,
                    area_name=sample_geographic_area.name,
                    name=name,
                    status="closed_permanently",
                )
            ]
        },
        [],
        allow_org_updates=True,
        catalog_manager_id=CATALOG_MANAGER,
    )
    assert results[0]["status"] == "skipped"
    assert results[0]["error"] == "no matching organization to close"
    assert summary["organizations"]["skipped"] == 1
    found = db_session.execute(
        select(Organization).where(Organization.name == name)
    ).scalar_one_or_none()
    assert found is None


def test_provider_owned_org_is_skipped(
    db_session,
    sample_organization,
) -> None:
    summary, results = process_import_payload(
        db_session,
        {
            "organizations": [
                {
                    "name": sample_organization.name,
                    "manager_id": CATALOG_MANAGER,
                    "status": "closed_permanently",
                }
            ]
        },
        [],
        allow_org_updates=True,
        catalog_manager_id=CATALOG_MANAGER,
    )
    assert results[0]["status"] == "skipped"
    assert results[0]["error"] == "managed by provider"
    db_session.refresh(sample_organization)
    assert sample_organization.status == "operational"


def test_dry_run_place_id_match_reports_update_without_write(
    test_engine,
) -> None:
    from app.db.models import ActivityCategory, GeographicArea

    name = f"Dry Place Park {uuid4()}"
    category_name = f"Dry Cat {uuid4().hex[:8]}"
    area_name = f"Dry Dist {uuid4().hex[:8]}"
    with Session(test_engine) as session:
        session.add(ActivityCategory(name=category_name, display_order=0))
        session.add(
            GeographicArea(name=area_name, level="district", active=True)
        )
        session.commit()
        process_import_payload(
            session,
            {
                "organizations": [
                    _board_org(
                        1,
                        category_name=category_name,
                        area_name=area_name,
                        place_id="ChIJ-dry-place",
                        name=name,
                    )
                ]
            },
            [],
            allow_org_updates=True,
        )
    renamed = f"{name} renamed"
    with Session(test_engine) as session:
        _summary, results = process_import_payload(
            session,
            {
                "organizations": [
                    _board_org(
                        1,
                        category_name=category_name,
                        area_name=area_name,
                        place_id="ChIJ-dry-place",
                        name=renamed,
                    )
                ]
            },
            [],
            dry_run=True,
            allow_org_updates=True,
        )
        session.rollback()
    assert results[0]["status"] == "updated"
    assert results[0]["key"] == renamed
    with Session(test_engine) as session:
        org = session.execute(
            select(Organization).where(
                Organization.place_id == "ChIJ-dry-place"
            )
        ).scalar_one()
        assert org.name == name


def test_activity_created_without_schedule(
    db_session,
    sample_activity_category,
    sample_geographic_area,
) -> None:
    name = f"No Hours Park {uuid4()}"
    summary, results = process_import_payload(
        db_session,
        {
            "organizations": [
                _board_org(
                    1,
                    category_name=sample_activity_category.name,
                    area_name=sample_geographic_area.name,
                    name=name,
                )
            ]
        },
        [],
        allow_org_updates=True,
    )
    by_type = {item["type"]: item for item in results}
    assert by_type["organizations"]["status"] == "created"
    assert by_type["activities"]["status"] == "created"
    assert summary["schedules"]["failed"] == 0


def test_truncation_is_a_file_warning(
    db_session,
    sample_activity_category,
    sample_geographic_area,
) -> None:
    warnings: list[str] = []
    long_name = "N" * 201
    process_import_payload(
        db_session,
        {
            "organizations": [
                _board_org(
                    1,
                    category_name=sample_activity_category.name,
                    area_name=sample_geographic_area.name,
                    name=long_name,
                )
            ]
        },
        warnings,
        allow_org_updates=True,
    )
    assert any("truncated" in item for item in warnings)
    found = db_session.execute(
        select(Organization).where(Organization.name == long_name[:200])
    ).scalar_one()
    assert found.place_id is None
    assert found.description_source == "template"
    assert found.source == "lcsd"
    assert found.source_id == "lcsd-1"
