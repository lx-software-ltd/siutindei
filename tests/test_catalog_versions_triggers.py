"""PostgreSQL triggers that version catalog rows."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from app.db.models import (
    Activity,
    ActivityCategory,
    ActivityLocation,
    ActivityPricing,
    ActivitySchedule,
    ActivityScheduleEntry,
    AuditLog,
    CatalogVersion,
    GeographicArea,
    Location,
    Organization,
)
from app.db.models.enums import PricingType, ScheduleType
from app.services.org_merge import merge_organizations
from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

_BACKFILL_FUNCTIONS = (
    "catalog_backfill_deleted_batch(text)",
    "catalog_backfill_deleted(text, text[])",
    "catalog_backfill_deleted_candidates(text, integer)",
    "catalog_backfill_live_batch(text)",
    "catalog_backfill_live(text, uuid[])",
    "catalog_backfill_live_candidates(text, integer)",
)

_BACKFILL = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "db"
    / "catalog_version_backfill.sql"
)


def _triggers_installed(session: Session) -> bool:
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return False
    return bool(
        session.scalar(
            text(
                "SELECT 1 FROM pg_trigger "
                "WHERE tgname = 'catalog_versions_delete_guard'"
            )
        )
    )


@pytest.fixture
def versions(test_engine):
    """Skip unless this database installed the catalog version triggers."""
    with Session(test_engine) as session:
        if not _triggers_installed(session):
            pytest.skip("catalog version triggers are not installed")
    return test_engine


@pytest.fixture(autouse=True)
def _clear_committed_catalog(versions):
    """These tests commit so triggers can bump. Later tests must not see that."""
    yield
    with Session(versions) as session:
        org_ids = select(Organization.id).where(Organization.name.like("Trigger %"))
        activity_ids = select(Activity.id).where(Activity.org_id.in_(org_ids))
        schedule_ids = select(ActivitySchedule.id).where(
            ActivitySchedule.activity_id.in_(activity_ids)
        )
        session.execute(
            text(
                "DELETE FROM activity_schedule_entries "
                "WHERE schedule_id IN "
                "(SELECT id FROM activity_schedule WHERE activity_id IN "
                "(SELECT id FROM activities WHERE org_id IN "
                "(SELECT id FROM organizations WHERE name LIKE 'Trigger %')))"
            )
        )
        session.execute(
            delete(ActivitySchedule).where(ActivitySchedule.id.in_(schedule_ids))
        )
        session.execute(
            delete(ActivityPricing).where(ActivityPricing.activity_id.in_(activity_ids))
        )
        session.execute(
            text(
                "DELETE FROM activity_locations WHERE activity_id IN "
                "(SELECT id FROM activities WHERE org_id IN "
                "(SELECT id FROM organizations WHERE name LIKE 'Trigger %'))"
            )
        )
        session.execute(delete(Activity).where(Activity.org_id.in_(org_ids)))
        session.execute(delete(Location).where(Location.org_id.in_(org_ids)))
        session.execute(
            text(
                "DELETE FROM organization_merges WHERE merged_org_id IN "
                "(SELECT id FROM organizations WHERE name LIKE 'Trigger %') "
                "OR survivor_org_id IN "
                "(SELECT id FROM organizations WHERE name LIKE 'Trigger %')"
            )
        )
        session.execute(delete(Organization).where(Organization.name.like("Trigger %")))
        session.execute(
            delete(GeographicArea).where(
                GeographicArea.name.like("Trigger Area %")
                | GeographicArea.name.like("Later Area %")
                | GeographicArea.name.like("Delete Area %")
                | GeographicArea.name.like("Price Area %")
                | GeographicArea.name.like("Slot Area %")
                | GeographicArea.name.like("Join Area %")
            )
        )
        session.execute(
            delete(ActivityCategory).where(
                ActivityCategory.name.like("Price Class %")
                | ActivityCategory.name.like("Slot Class %")
                | ActivityCategory.name.like("Join Class %")
            )
        )
        session.flush()
        session.execute(
            text(
                "ALTER TABLE catalog_versions "
                "DISABLE TRIGGER catalog_versions_delete_guard"
            )
        )
        session.execute(
            delete(CatalogVersion).where(
                CatalogVersion.org_id.is_not(None),
                CatalogVersion.org_id.not_in(select(Organization.id)),
            )
        )
        session.execute(
            text(
                "ALTER TABLE catalog_versions "
                "ENABLE TRIGGER catalog_versions_delete_guard"
            )
        )
        session.commit()


def _org(name: str) -> Organization:
    return Organization(
        name=name,
        description="Original",
        manager_id="00000000-0000-0000-0000-000000000091",
    )


def _rows(
    session: Session, entity_type: str, entity_id: object
) -> list[CatalogVersion]:
    return list(
        session.scalars(
            select(CatalogVersion)
            .where(
                CatalogVersion.entity_type == entity_type,
                CatalogVersion.entity_id == entity_id,
            )
            .order_by(CatalogVersion.version)
        ).all()
    )


def test_create_writes_version_1(versions) -> None:
    with Session(versions) as session:
        org = _org(f"Trigger Create {uuid4()}")
        session.add(org)
        session.commit()
        org_id = org.id
    with Session(versions) as session:
        found = session.get(Organization, org_id)
        assert found is not None
        assert found.version == 1
        rows = _rows(session, "organization", org_id)
        assert [row.action for row in rows] == ["created"]
        assert rows[0].version == 1


def test_tracked_update_bumps_and_moves_updated_at(versions) -> None:
    with Session(versions) as session:
        org = _org(f"Trigger Edit {uuid4()}")
        session.add(org)
        session.commit()
        org_id = org.id
        started = org.updated_at
    with Session(versions) as session:
        org = session.get(Organization, org_id)
        assert org is not None
        org.description = "Edited"
        session.commit()
    with Session(versions) as session:
        org = session.get(Organization, org_id)
        assert org is not None
        assert org.version == 2
        assert org.updated_at > started
        rows = _rows(session, "organization", org_id)
        assert rows[-1].action == "updated"
        assert "description" in (rows[-1].changed_fields or [])


def test_bookkeeping_update_does_not_bump(versions) -> None:
    with Session(versions) as session:
        org = _org(f"Trigger Book {uuid4()}")
        session.add(org)
        session.commit()
        org_id = org.id
    with Session(versions) as session:
        org = session.get(Organization, org_id)
        assert org is not None
        org.last_imported_at = org.updated_at
        session.commit()
    with Session(versions) as session:
        org = session.get(Organization, org_id)
        assert org is not None
        assert org.version == 1
        assert len(_rows(session, "organization", org_id)) == 1


def test_review_status_bumps(versions) -> None:
    with Session(versions) as session:
        org = _org(f"Trigger Review {uuid4()}")
        session.add(org)
        session.commit()
        org_id = org.id
    with Session(versions) as session:
        org = session.get(Organization, org_id)
        assert org is not None
        org.review_status = "approved"
        session.commit()
    with Session(versions) as session:
        org = session.get(Organization, org_id)
        assert org is not None
        assert org.version == 2
        changed = _rows(session, "organization", org_id)[-1].changed_fields or []
        assert "review_status" in changed


def test_review_reason_bumps(versions) -> None:
    with Session(versions) as session:
        org = _org(f"Trigger Reason {uuid4()}")
        session.add(org)
        session.commit()
        org_id = org.id
    with Session(versions) as session:
        org = session.get(Organization, org_id)
        assert org is not None
        org.review_status = "rejected"
        org.review_reason = "not_relevant"
        session.commit()
    with Session(versions) as session:
        org = session.get(Organization, org_id)
        assert org is not None
        assert org.version == 2
        changed = _rows(session, "organization", org_id)[-1].changed_fields or []
        assert "review_reason" in changed


def test_child_created_with_org_leaves_org_at_version_1(versions) -> None:
    with Session(versions) as session:
        org = _org(f"Trigger Child {uuid4()}")
        area = GeographicArea(name=f"Trigger Area {uuid4()}", level="district")
        session.add(org)
        session.add(area)
        session.flush()
        session.add(Location(org_id=org.id, area_id=area.id, address="1 Trigger Road"))
        session.commit()
        org_id = org.id
    with Session(versions) as session:
        org = session.get(Organization, org_id)
        assert org is not None
        assert org.version == 1


def test_later_location_change_bumps_org_once(versions) -> None:
    with Session(versions) as session:
        org = _org(f"Trigger Later {uuid4()}")
        area = GeographicArea(name=f"Later Area {uuid4()}", level="district")
        session.add(org)
        session.add(area)
        session.flush()
        location = Location(org_id=org.id, area_id=area.id, address="1 Trigger Road")
        session.add(location)
        session.commit()
        org_id = org.id
        location_id = location.id
    with Session(versions) as session:
        org = session.get(Organization, org_id)
        assert org is not None
        started = org.updated_at
    with Session(versions) as session:
        location = session.get(Location, location_id)
        assert location is not None
        location.address = "2 Trigger Road"
        session.commit()
    with Session(versions) as session:
        org = session.get(Organization, org_id)
        location = session.get(Location, location_id)
        assert org is not None and location is not None
        assert location.version == 2
        assert org.version == 2
        assert org.updated_at == started


def test_media_change_bumps_media_version(versions) -> None:
    with Session(versions) as session:
        org = _org(f"Trigger Media {uuid4()}")
        session.add(org)
        session.commit()
        org_id = org.id
    with Session(versions) as session:
        org = session.get(Organization, org_id)
        assert org is not None
        org.media_urls = ["https://cdn.example.com/one.jpg"]
        session.commit()
    with Session(versions) as session:
        org = session.get(Organization, org_id)
        assert org is not None
        assert org.version == 2
        assert org.media_version == 2
        media = _rows(session, "media", org_id)
        assert [row.version for row in media] == [1, 2]


def test_delete_writes_tombstone_and_child_tombstone(versions) -> None:
    with Session(versions) as session:
        org = _org(f"Trigger Delete {uuid4()}")
        area = GeographicArea(name=f"Delete Area {uuid4()}", level="district")
        session.add(org)
        session.add(area)
        session.flush()
        location = Location(org_id=org.id, area_id=area.id, address="1 Trigger Road")
        session.add(location)
        session.commit()
        org_id = org.id
        location_id = location.id
    with Session(versions) as session:
        org = session.get(Organization, org_id)
        assert org is not None
        session.delete(org)
        session.commit()
    with Session(versions) as session:
        assert session.get(Organization, org_id) is None
        deleted = _rows(session, "organization", org_id)[-1]
        assert deleted.action == "deleted"
        child = _rows(session, "location", location_id)[-1]
        assert child.action == "deleted"


def test_pricing_change_bumps_activity_and_org(versions) -> None:
    with Session(versions) as session:
        org = _org(f"Trigger Price {uuid4()}")
        area = GeographicArea(name=f"Price Area {uuid4()}", level="district")
        category = ActivityCategory(name=f"Price Class {uuid4()}", display_order=0)
        session.add_all([org, area, category])
        session.flush()
        location = Location(org_id=org.id, area_id=area.id, address="1 Trigger Road")
        activity = Activity(
            org_id=org.id,
            category_id=category.id,
            name=f"Class {uuid4()}",
            age_range=Range(5, 9, bounds="[]"),
        )
        session.add_all([location, activity])
        session.flush()
        pricing = ActivityPricing(
            activity_id=activity.id,
            location_id=location.id,
            pricing_type=PricingType.PER_CLASS,
            amount=100,
        )
        session.add(pricing)
        session.commit()
        org_id, activity_id, pricing_id = org.id, activity.id, pricing.id
    with Session(versions) as session:
        pricing = session.get(ActivityPricing, pricing_id)
        assert pricing is not None
        pricing.amount = 120
        session.commit()
    with Session(versions) as session:
        assert session.get(ActivityPricing, pricing_id).version == 2
        assert session.get(Activity, activity_id).version == 2
        assert session.get(Organization, org_id).version == 2


def test_schedule_entry_bumps_schedule_activity_and_org(versions) -> None:
    with Session(versions) as session:
        org = _org(f"Trigger Slot {uuid4()}")
        area = GeographicArea(name=f"Slot Area {uuid4()}", level="district")
        category = ActivityCategory(name=f"Slot Class {uuid4()}", display_order=0)
        session.add_all([org, area, category])
        session.flush()
        location = Location(org_id=org.id, area_id=area.id, address="1 Trigger Road")
        activity = Activity(
            org_id=org.id,
            category_id=category.id,
            name=f"Class {uuid4()}",
            age_range=Range(5, 9, bounds="[]"),
        )
        session.add_all([location, activity])
        session.flush()
        schedule = ActivitySchedule(
            activity_id=activity.id,
            location_id=location.id,
            schedule_type=ScheduleType.WEEKLY,
            languages=["en"],
        )
        session.add(schedule)
        session.flush()
        entry = ActivityScheduleEntry(
            schedule_id=schedule.id,
            day_of_week_utc=1,
            start_minutes_utc=540,
            end_minutes_utc=600,
        )
        session.add(entry)
        session.commit()
        ids = (org.id, activity.id, schedule.id, entry.id)
    with Session(versions) as session:
        entry = session.get(ActivityScheduleEntry, ids[3])
        assert entry is not None
        entry.start_minutes_utc = 600
        entry.end_minutes_utc = 660
        session.commit()
    with Session(versions) as session:
        assert session.get(ActivitySchedule, ids[2]).version == 2
        assert session.get(Activity, ids[1]).version == 2
        assert session.get(Organization, ids[0]).version == 2


def test_merge_annotates_the_source_tombstone(versions) -> None:
    with Session(versions) as session:
        survivor = _org(f"Trigger Survivor {uuid4()}")
        source = _org(f"Trigger Source {uuid4()}")
        session.add_all([survivor, source])
        session.commit()
        survivor_id, source_id = survivor.id, source.id
        merge_organizations(session, survivor_id, [source_id], merged_by="admin-sub")
        session.commit()
    with Session(versions) as session:
        deleted = _rows(session, "organization", source_id)[-1]
        assert deleted.action == "deleted"
        assert deleted.reason == "merged"
        assert deleted.related_id == survivor_id


def _install_backfill(session: Session) -> None:
    """Create the batch functions. Each statement is one function body."""
    chunks: list[str] = []
    current: list[str] = []
    for line in _BACKFILL.read_text(encoding="utf-8").splitlines(keepends=True):
        if line.startswith("CREATE OR REPLACE FUNCTION") and current:
            chunks.append("".join(current))
            current = []
        current.append(line)
    if current:
        chunks.append("".join(current))
    for chunk in chunks:
        statement = chunk.strip()
        if statement.startswith("CREATE"):
            session.execute(text(statement))


def _drop_backfill(session: Session) -> None:
    for name in _BACKFILL_FUNCTIONS:
        session.execute(text(f"DROP FUNCTION IF EXISTS {name}"))


def test_backfill_prefers_the_audit_insert(versions) -> None:
    with Session(versions) as session:
        # LOCAL reverts when this transaction commits, so the pooled
        # connection is not left with triggers disabled.
        session.execute(text("SET LOCAL session_replication_role = replica"))
        org = _org(f"Trigger Backfill {uuid4()}")
        org.description = "Current"
        session.add(org)
        session.flush()
        session.add(
            AuditLog(
                table_name="organizations",
                record_id=str(org.id),
                action="INSERT",
                new_values={
                    "id": str(org.id),
                    "name": org.name,
                    "description": "Original",
                    "manager_id": org.manager_id,
                },
            )
        )
        session.commit()
        org_id = org.id
    with Session(versions) as session:
        _install_backfill(session)
        session.execute(
            text(
                "SELECT catalog_backfill_live("
                "'organizations', ARRAY[CAST(:org_id AS uuid)])"
            ),
            {"org_id": org_id},
        )
        _drop_backfill(session)
        session.commit()
    with Session(versions) as session:
        org = session.get(Organization, org_id)
        assert org is not None
        assert org.version == 2
        rows = _rows(session, "organization", org_id)
        assert rows[0].snapshot["description"] == "Original"
        assert rows[1].action == "updated"
        assert rows[1].snapshot["description"] == "Current"


def _audit_row(
    table_name: str,
    record_id: str,
    action: str,
    *,
    new_values: dict | None = None,
    old_values: dict | None = None,
) -> AuditLog:
    return AuditLog(
        table_name=table_name,
        record_id=record_id,
        action=action,
        new_values=new_values,
        old_values=old_values,
    )


def _deleted_candidates(session: Session, table_name: str) -> list[str]:
    found = session.scalar(
        text("SELECT catalog_backfill_deleted_candidates(:table_name, 10000)"),
        {"table_name": table_name},
    )
    return [str(item) for item in (found or [])]


def _forget_backfill_residue(session: Session, record_id: str) -> None:
    session.execute(
        text(
            "ALTER TABLE catalog_versions DISABLE TRIGGER catalog_versions_delete_guard"
        )
    )
    session.execute(
        text("DELETE FROM catalog_versions WHERE entity_id = CAST(:record_id AS uuid)"),
        {"record_id": record_id},
    )
    session.execute(
        text(
            "DELETE FROM organization_merges WHERE merged_org_id = CAST(:record_id AS uuid)"
        ),
        {"record_id": record_id},
    )
    session.execute(
        text("DELETE FROM audit_log WHERE record_id = :record_id"),
        {"record_id": record_id},
    )
    session.execute(
        text(
            "ALTER TABLE catalog_versions ENABLE TRIGGER catalog_versions_delete_guard"
        )
    )


def test_deleted_backfill_skips_a_delete_without_an_insert(versions) -> None:
    record_id = str(uuid4())
    with Session(versions) as session:
        session.add(
            _audit_row(
                "organizations",
                record_id,
                "DELETE",
                old_values={"id": record_id, "name": "Gone"},
            )
        )
        session.commit()
    try:
        with Session(versions) as session:
            _install_backfill(session)
            assert record_id not in _deleted_candidates(session, "organizations")
            session.execute(
                text(
                    "SELECT catalog_backfill_deleted("
                    "'organizations', ARRAY[:record_id])"
                ),
                {"record_id": record_id},
            )
            _drop_backfill(session)
            session.commit()
        with Session(versions) as session:
            assert _rows(session, "organization", record_id) == []
    finally:
        with Session(versions) as session:
            _forget_backfill_residue(session, record_id)
            session.commit()


def test_deleted_backfill_writes_created_then_deleted(versions) -> None:
    record_id = str(uuid4())
    snapshot = {"id": record_id, "name": "Original", "description": "Then"}
    with Session(versions) as session:
        session.add(
            _audit_row("organizations", record_id, "INSERT", new_values=snapshot)
        )
        session.add(
            _audit_row("organizations", record_id, "DELETE", old_values=snapshot)
        )
        session.commit()
    try:
        with Session(versions) as session:
            _install_backfill(session)
            assert record_id in _deleted_candidates(session, "organizations")
            session.execute(
                text(
                    "SELECT catalog_backfill_deleted("
                    "'organizations', ARRAY[:record_id])"
                ),
                {"record_id": record_id},
            )
            session.commit()
            assert record_id not in _deleted_candidates(session, "organizations")
            _drop_backfill(session)
            session.commit()
        with Session(versions) as session:
            rows = _rows(session, "organization", record_id)
            assert [row.action for row in rows] == ["created", "deleted"]
            assert rows[0].version == 1
            assert rows[0].snapshot["description"] == "Then"
            assert rows[1].version == 2
            assert rows[1].snapshot["description"] == "Then"
    finally:
        with Session(versions) as session:
            _forget_backfill_residue(session, record_id)
            session.commit()


def test_deleted_backfill_leaves_a_live_row_alone(versions) -> None:
    with Session(versions) as session:
        session.execute(text("SET LOCAL session_replication_role = replica"))
        org = _org(f"Trigger Live Skip {uuid4()}")
        session.add(org)
        session.flush()
        record_id = str(org.id)
        snapshot = {"id": record_id, "name": org.name, "description": "Original"}
        session.add(
            _audit_row("organizations", record_id, "INSERT", new_values=snapshot)
        )
        session.add(
            _audit_row("organizations", record_id, "DELETE", old_values=snapshot)
        )
        session.commit()
    try:
        with Session(versions) as session:
            _install_backfill(session)
            assert record_id not in _deleted_candidates(session, "organizations")
            _drop_backfill(session)
            session.commit()
        with Session(versions) as session:
            assert _rows(session, "organization", record_id) == []
    finally:
        with Session(versions) as session:
            _forget_backfill_residue(session, record_id)
            session.commit()


def test_deleted_backfill_ignores_an_insert_with_no_values(versions) -> None:
    record_id = str(uuid4())
    earlier = datetime.now(UTC) - timedelta(minutes=5)
    later = datetime.now(UTC)
    payload = json.dumps({"id": record_id, "name": "Later"})
    with Session(versions) as session:
        # SQL NULL, not JSON null. The writer skips only the former.
        session.execute(
            text(
                "INSERT INTO audit_log "
                "(timestamp, table_name, record_id, action, new_values) "
                "VALUES (:earlier, 'organizations', :record_id, 'INSERT', NULL)"
            ),
            {"earlier": earlier, "record_id": record_id},
        )
        session.execute(
            text(
                "INSERT INTO audit_log "
                "(timestamp, table_name, record_id, action, new_values) "
                "VALUES (:later, 'organizations', :record_id, 'INSERT', "
                "CAST(:payload AS jsonb))"
            ),
            {"later": later, "record_id": record_id, "payload": payload},
        )
        session.execute(
            text(
                "INSERT INTO audit_log "
                "(timestamp, table_name, record_id, action, old_values) "
                "VALUES (:later, 'organizations', :record_id, 'DELETE', "
                "CAST(:payload AS jsonb))"
            ),
            {"later": later, "record_id": record_id, "payload": payload},
        )
        session.commit()
    try:
        with Session(versions) as session:
            _install_backfill(session)
            assert record_id not in _deleted_candidates(session, "organizations")
            _drop_backfill(session)
            session.commit()
    finally:
        with Session(versions) as session:
            _forget_backfill_residue(session, record_id)
            session.commit()


def test_deleted_backfill_ignores_a_non_uuid_record_id(versions) -> None:
    record_id = "not-a-uuid"
    with Session(versions) as session:
        session.add(
            _audit_row(
                "organizations",
                record_id,
                "INSERT",
                new_values={"name": "Broken"},
            )
        )
        session.add(
            _audit_row(
                "organizations",
                record_id,
                "DELETE",
                old_values={"name": "Broken"},
            )
        )
        session.commit()
    try:
        with Session(versions) as session:
            _install_backfill(session)
            found = _deleted_candidates(session, "organizations")
            _drop_backfill(session)
            session.commit()
        assert record_id not in found
    finally:
        with Session(versions) as session:
            session.execute(
                text("DELETE FROM audit_log WHERE record_id = :record_id"),
                {"record_id": record_id},
            )
            session.commit()


def test_deleted_backfill_ignores_a_hex_string_that_is_not_a_uuid(versions) -> None:
    record_id = "a" * 36
    with Session(versions) as session:
        session.add(
            _audit_row(
                "organizations",
                record_id,
                "INSERT",
                new_values={"name": "Broken"},
            )
        )
        session.add(
            _audit_row(
                "organizations",
                record_id,
                "DELETE",
                old_values={"name": "Broken"},
            )
        )
        session.commit()
    try:
        with Session(versions) as session:
            _install_backfill(session)
            found = _deleted_candidates(session, "organizations")
            _drop_backfill(session)
            session.commit()
        assert record_id not in found
    finally:
        with Session(versions) as session:
            session.execute(
                text("DELETE FROM audit_log WHERE record_id = :record_id"),
                {"record_id": record_id},
            )
            session.commit()


def test_committed_snapshot_is_immutable(versions) -> None:
    with Session(versions) as session:
        org = _org(f"Trigger Frozen {uuid4()}")
        session.add(org)
        session.commit()
        org_id = org.id
    with Session(versions) as session:
        with pytest.raises(DBAPIError, match="immutable"):
            session.execute(
                text(
                    "UPDATE catalog_versions SET snapshot = '{}'::jsonb "
                    "WHERE entity_type = 'organization' AND entity_id = :org_id "
                    "AND version = 1"
                ),
                {"org_id": org_id},
            )
        session.rollback()
        with pytest.raises(DBAPIError, match="immutable"):
            session.execute(
                text(
                    "SELECT catalog_upsert_version("
                    "'organization', :org_id, :org_id, 1, 'created', "
                    "'{}'::jsonb, NULL, NULL)"
                ),
                {"org_id": org_id},
            )
        session.rollback()
        with pytest.raises(DBAPIError, match="immutable"):
            session.execute(
                text(
                    "DELETE FROM catalog_versions "
                    "WHERE entity_type = 'organization' AND entity_id = :org_id"
                ),
                {"org_id": org_id},
            )
        session.rollback()


def test_open_transaction_can_drop_its_own_version(versions) -> None:
    with Session(versions) as session:
        org = _org(f"Trigger Dry {uuid4()}")
        session.add(org)
        session.flush()
        session.execute(
            text("DELETE FROM catalog_versions WHERE entity_id = :org_id"),
            {"org_id": org.id},
        )
        remaining = session.scalar(
            text("SELECT count(*) FROM catalog_versions WHERE entity_id = :org_id"),
            {"org_id": org.id},
        )
        assert remaining == 0
        session.rollback()


def test_activity_snapshot_keeps_a_location_added_after_an_edit(versions) -> None:
    with Session(versions) as session:
        org = _org(f"Trigger Join {uuid4()}")
        area = GeographicArea(name=f"Join Area {uuid4()}", level="district")
        category = ActivityCategory(name=f"Join Class {uuid4()}", display_order=0)
        session.add_all([org, area, category])
        session.flush()
        location = Location(org_id=org.id, area_id=area.id, address="1 Trigger Road")
        activity = Activity(
            org_id=org.id,
            category_id=category.id,
            name=f"Class {uuid4()}",
            age_range=Range(5, 9, bounds="[]"),
        )
        session.add_all([location, activity])
        session.commit()
        activity_id = activity.id
        location_id = location.id
    with Session(versions) as session:
        activity = session.get(Activity, activity_id)
        assert activity is not None
        activity.description = "Edited"
        session.flush()
        session.add(ActivityLocation(activity_id=activity_id, location_id=location_id))
        session.commit()
    with Session(versions) as session:
        updated = _rows(session, "activity", activity_id)[-1]
        stored = {str(item) for item in updated.snapshot.get("location_ids") or []}
        assert str(location_id) in stored


def test_forget_keeps_merged_and_strips_contacts(versions) -> None:
    with Session(versions) as session:
        survivor = _org(f"Trigger Survivor {uuid4()}")
        source = _org(f"Trigger Source {uuid4()}")
        source.email = "source@example.com"
        session.add_all([survivor, source])
        session.commit()
        survivor_id, source_id = survivor.id, source.id
        merge_organizations(session, survivor_id, [source_id], merged_by="admin-sub")
        session.commit()
    with Session(versions) as session:
        session.execute(
            text("SELECT catalog_forget_entity('organization', :org_id)"),
            {"org_id": source_id},
        )
        session.commit()
    with Session(versions) as session:
        rows = _rows(session, "organization", source_id)
        created = rows[0]
        deleted = rows[-1]
        assert created.reason is None
        assert deleted.reason == "merged"
        assert deleted.related_id == survivor_id
        assert "email" not in (created.snapshot or {})
        assert "email" not in (deleted.snapshot or {})


def test_forgetting_an_organization_forgets_child_baselines(versions) -> None:
    with Session(versions) as session:
        org = _org(f"Trigger Forget {uuid4()}")
        org.email = "org@example.com"
        area = GeographicArea(name=f"Trigger Area {uuid4()}", level="district")
        session.add(org)
        session.add(area)
        session.flush()
        location = Location(org_id=org.id, area_id=area.id, address="1 Trigger Road")
        session.add(location)
        session.commit()
        org_id = org.id
        location_id = location.id
    with Session(versions) as session:
        org = session.get(Organization, org_id)
        assert org is not None
        session.delete(org)
        session.commit()
    with Session(versions) as session:
        session.execute(
            text("SELECT catalog_forget_entity('organization', :org_id)"),
            {"org_id": org_id},
        )
        session.commit()
    with Session(versions) as session:
        org_rows = _rows(session, "organization", org_id)
        location_rows = _rows(session, "location", location_id)
        assert org_rows[0].reason == "forgotten"
        assert "email" not in (org_rows[0].snapshot or {})
        assert location_rows[0].reason == "forgotten"
