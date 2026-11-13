"""Catalogue snapshot for the public website build."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from app.api.schemas import dump_search_response
from app.api.search import fetch_search_response
from app.db.models import (
    Activity,
    ActivityCategory,
    ActivityPricing,
    ActivitySchedule,
    ActivityScheduleEntry,
    GeographicArea,
    Location,
    Organization,
)
from app.db.models.enums import PricingType, ScheduleType
from app.db.queries import ActivitySearchFilters
from app.services import catalogue_snapshot
from botocore.exceptions import ClientError
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.orm import Session

_MANAGER = "00000000-0000-0000-0000-000000000001"
_NOW = datetime(2026, 11, 13, 5, 0, tzinfo=UTC)


class FakeS3:
    """Records put_object calls and answers head_object from them."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict] = {}
        self.puts: list[dict] = []

    def head_object(self, *, Bucket: str, Key: str) -> dict:
        stored = self.objects.get((Bucket, Key))
        if stored is None:
            raise ClientError(
                {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
            )
        return {"Metadata": dict(stored["Metadata"])}

    def put_object(self, **kwargs) -> dict:
        self.puts.append(kwargs)
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = kwargs
        return {}


def _seed(engine) -> dict:
    token = uuid4().hex[:8]
    with Session(engine) as session:
        area = GeographicArea(name=f"Area {token}", level="neighbourhood", active=True)
        outside = GeographicArea(
            name=f"Outside {token}", level="neighbourhood", active=True
        )
        category = ActivityCategory(name=f"Category {token}", display_order=0)
        org = Organization(
            name=f"Harbour Club {token}",
            manager_id=_MANAGER,
            description="Club",
            review_status="approved",
            website="https://example.com/club",
        )
        session.add_all([area, outside, category, org])
        session.flush()

        activity_ids: list[str] = []
        for index, where in enumerate([area, area, area, outside]):
            venue = Location(
                org_id=org.id,
                area_id=where.id,
                address=f"{index} Example Road {token}",
                lat=Decimal("22.218000"),
                lng=Decimal("114.213000"),
            )
            act = Activity(
                org_id=org.id,
                category_id=category.id,
                name=f"Class {index} {token}",
                description="A weekly class.",
                age_range=Range(3, 8, bounds="[]"),
            )
            session.add_all([venue, act])
            session.flush()
            session.add(
                ActivityPricing(
                    activity_id=act.id,
                    location_id=venue.id,
                    pricing_type=PricingType.PER_CLASS,
                    amount=Decimal(150),
                )
            )
            schedule = ActivitySchedule(
                activity_id=act.id,
                location_id=venue.id,
                schedule_type=ScheduleType.WEEKLY,
                languages=["en"],
            )
            session.add(schedule)
            session.flush()
            session.add(
                ActivityScheduleEntry(
                    schedule_id=schedule.id,
                    day_of_week_utc=index % 7,
                    start_minutes_utc=120,
                    end_minutes_utc=180,
                )
            )
            activity_ids.append(str(act.id))
        session.commit()
        return {
            "area_id": area.id,
            "outside_id": outside.id,
            "category_id": category.id,
            "org_id": org.id,
            "in_scope": activity_ids[:3],
            "out_of_scope": activity_ids[3],
        }


def _delete(engine, seeded: dict) -> None:
    with Session(engine) as session:
        for model, key in (
            (Organization, "org_id"),
            (GeographicArea, "area_id"),
            (GeographicArea, "outside_id"),
            (ActivityCategory, "category_id"),
        ):
            row = session.get(model, seeded[key])
            if row is not None:
                session.delete(row)
        session.commit()


@pytest.fixture
def seeded(monkeypatch, test_engine):
    monkeypatch.setattr("app.api.search.get_engine", lambda: test_engine)
    data = _seed(test_engine)
    scope = frozenset({data["area_id"]})
    monkeypatch.setattr("app.db.queries.configured_search_area_ids", lambda: scope)
    yield data
    _delete(test_engine, data)


def _activity_ids(snapshot: dict) -> list[str]:
    return [item["activity"]["id"] for item in snapshot["items"]]


def test_snapshot_holds_every_page_of_the_scoped_public_search(seeded) -> None:
    snapshot = catalogue_snapshot.build_catalogue_snapshot(page_size=1)

    assert sorted(_activity_ids(snapshot)) == sorted(seeded["in_scope"])
    assert seeded["out_of_scope"] not in _activity_ids(snapshot)
    assert snapshot["schema_version"] == catalogue_snapshot.SNAPSHOT_SCHEMA_VERSION
    assert snapshot["area_scope"] == [str(seeded["area_id"])]


def test_snapshot_items_match_the_public_search_response(seeded) -> None:
    snapshot = catalogue_snapshot.build_catalogue_snapshot()
    expected = dump_search_response(
        fetch_search_response(
            ActivitySearchFilters(limit=100, view="full", include_incomplete=True)
        ),
        "full",
    )

    assert json.loads(json.dumps(snapshot["items"], default=str)) == json.loads(
        json.dumps(expected["items"], default=str)
    )
    first = snapshot["items"][0]
    assert first["organization"]["contact"]["website"] == "https://example.com/club"
    assert first["organization"]["place_id"] is None


def test_snapshot_stops_at_the_page_limit(seeded) -> None:
    with pytest.raises(catalogue_snapshot.CatalogueSnapshotError):
        catalogue_snapshot.build_catalogue_snapshot(page_size=1, max_pages=2)


def test_publish_writes_once_and_skips_unchanged_content(seeded) -> None:
    s3 = FakeS3()

    first = catalogue_snapshot.publish_catalogue_snapshot(
        s3, "bucket", "public-www/catalogue-snapshot.json", now=_NOW
    )
    second = catalogue_snapshot.publish_catalogue_snapshot(
        s3, "bucket", "public-www/catalogue-snapshot.json", now=_NOW
    )

    assert first["written"] is True
    assert first["items"] == 3
    assert second["written"] is False
    assert len(s3.puts) == 1
    put = s3.puts[0]
    assert put["ContentType"] == "application/json"
    assert put["Metadata"]["content-sha256"] == first["digest"]
    body = json.loads(put["Body"])
    assert body["generated_at"] == "2026-11-13T05:00:00+00:00"
    assert sorted(_activity_ids(body)) == sorted(seeded["in_scope"])


def test_publish_rewrites_when_the_catalogue_changes(seeded, test_engine) -> None:
    s3 = FakeS3()
    catalogue_snapshot.publish_catalogue_snapshot(s3, "bucket", "key", now=_NOW)

    with Session(test_engine) as session:
        activity = session.get(Activity, UUID(seeded["in_scope"][0]))
        assert activity is not None
        activity.name = f"{activity.name} renamed"
        session.commit()

    result = catalogue_snapshot.publish_catalogue_snapshot(
        s3, "bucket", "key", now=_NOW
    )

    assert result["written"] is True
    assert len(s3.puts) == 2


def test_lambda_handler_reads_bucket_and_key_from_the_environment(
    seeded, monkeypatch
) -> None:
    s3 = FakeS3()
    monkeypatch.setenv("CATALOGUE_SNAPSHOT_BUCKET", "snapshot-bucket")
    monkeypatch.delenv("CATALOGUE_SNAPSHOT_KEY", raising=False)
    monkeypatch.setattr(catalogue_snapshot, "get_s3_client", lambda: s3)

    result = catalogue_snapshot.lambda_handler({}, None)

    assert result["written"] is True
    assert s3.puts[0]["Bucket"] == "snapshot-bucket"
    assert s3.puts[0]["Key"] == catalogue_snapshot.DEFAULT_SNAPSHOT_KEY


def test_lambda_handler_requires_a_bucket(monkeypatch) -> None:
    monkeypatch.delenv("CATALOGUE_SNAPSHOT_BUCKET", raising=False)

    with pytest.raises(catalogue_snapshot.CatalogueSnapshotError):
        catalogue_snapshot.lambda_handler({}, None)
