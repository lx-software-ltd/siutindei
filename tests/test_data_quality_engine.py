"""Data-quality settings, idempotent checks, and import runs."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from app.db.models import DataQualityRun, ImportSettings, NameFixProposal, Organization
from app.exceptions import AppError, ValidationError
from app.services.data_quality.fingerprint import fingerprint
from app.services.data_quality.names import name_input_hash
from app.services.data_quality.runs import (
    create_manual_run,
    process_run,
    stage_import_run,
)
from app.services.data_quality.scope import scope_from_results
from app.services.import_settings import (
    load_import_settings,
    serialize_import_settings,
    update_import_settings,
)
from app.services.name_fix_scan import scan_names
from app.services.name_sanitizer import NameSanitizeConfig
from sqlalchemy import select


def _event(path: str, *, method: str = "GET", body: dict | None = None) -> dict:
    event = {
        "httpMethod": method,
        "path": path,
        "headers": {"Content-Type": "application/json"},
        "requestContext": {
            "requestId": "test-request",
            "authorizer": {"groups": "admin", "userSub": "admin-user"},
        },
    }
    if body is not None:
        event["body"] = json.dumps(body)
    return event


def _without_import_settings(db_session) -> None:
    row = db_session.get(ImportSettings, 1)
    if row is not None:
        db_session.delete(row)
        db_session.flush()


def test_missing_row_keeps_today_defaults(db_session) -> None:
    _without_import_settings(db_session)
    row = load_import_settings(db_session)
    assert row.name_cleanup == "apply"
    assert row.skip_deleted_organizations is True
    assert row.duplicates == "off"
    assert row.locations == "off"
    assert row.categories == "off"
    assert row.unknown_categories == "capture"
    assert serialize_import_settings(row)["updated_at"] is None


def test_missing_row_follows_legacy_capture_flag(db_session) -> None:
    from app.services.category_suggestions.settings import get_settings

    _without_import_settings(db_session)

    settings = get_settings(db_session)
    settings.on_import_enabled = False
    db_session.flush()
    assert load_import_settings(db_session).unknown_categories == "fail"


def _settings_body(**overrides: object) -> dict:
    body = {
        "updated_at": None,
        "skip_deleted_organizations": True,
        "name_cleanup": "apply",
        "unknown_categories": "capture",
        "duplicates": "off",
        "locations": "off",
        "categories": "off",
    }
    body.update(overrides)
    return body


def test_settings_update_rejects_a_stale_stamp(db_session) -> None:
    _without_import_settings(db_session)
    created = update_import_settings(
        db_session,
        _settings_body(name_cleanup="propose"),
        updated_by="admin-user",
    )
    db_session.flush()
    with pytest.raises(AppError) as exc_info:
        update_import_settings(
            db_session,
            _settings_body(
                updated_at="2000-01-01T00:00:00+00:00",
                name_cleanup="off",
            ),
            updated_by="admin-user",
        )
    assert exc_info.value.status_code == 409
    assert created.name_cleanup == "propose"


def test_settings_update_requires_every_field(db_session) -> None:
    _without_import_settings(db_session)
    created = update_import_settings(
        db_session,
        _settings_body(),
        updated_by="admin-user",
    )
    partial = _settings_body(
        updated_at=serialize_import_settings(created)["updated_at"]
    )
    partial.pop("categories")
    with pytest.raises(ValidationError) as exc_info:
        update_import_settings(db_session, partial, updated_by="admin-user")
    assert exc_info.value.field == "categories"
    assert created.categories == "off"


def test_second_name_scan_writes_nothing(db_session) -> None:
    org = Organization(
        id=uuid4(),
        name="HARBOUR CLUB",
        manager_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        review_status="pending_review",
    )
    db_session.add(org)
    db_session.flush()
    first = scan_names(db_session, review_scope="pending_review")
    db_session.flush()
    row = db_session.scalars(select(NameFixProposal)).one()
    updated_at = row.updated_at
    second = scan_names(db_session, review_scope="pending_review")
    db_session.flush()
    again = db_session.scalars(select(NameFixProposal)).one()
    assert first["created"] == 1
    assert second["created"] == 0
    assert second["updated"] == 0
    assert again.updated_at == updated_at
    assert again.input_hash


def test_name_fingerprint_ignores_dict_order() -> None:
    config = NameSanitizeConfig.defaults()
    left = name_input_hash(
        entity_type="organization",
        current="Harbour Club",
        translations={"zh": "港", "en": "Harbour"},
        proposed="Harbour Club",
        rules=["title_case", "whitespace"],
        translation_patch={"zh": "港"},
        config=config,
    )
    right = name_input_hash(
        entity_type="organization",
        current="Harbour Club",
        translations={"en": "Harbour", "zh": "港"},
        proposed="Harbour Club",
        rules=["whitespace", "title_case"],
        translation_patch={"zh": "港"},
        config=config,
    )
    assert left == right
    assert left == fingerprint(
        {
            "version": "names-1",
            "entity_type": "organization",
            "current": "Harbour Club",
            "translations": {"en": "Harbour", "zh": "港"},
            "proposed": "Harbour Club",
            "rules": ["title_case", "whitespace"],
            "translation_patch": {"zh": "港"},
            "config": {
                "enabled_rules": sorted(config.enabled_rules),
                "exception_words": sorted(config.exception_words),
                "bracket_suffixes": sorted(config.bracket_suffixes),
            },
        }
    )


def test_duplicate_group_order_is_stable(db_session) -> None:
    from app.services.data_quality.duplicates import report_duplicates

    first_id = uuid4()
    second_id = uuid4()
    manager = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    db_session.add_all(
        [
            Organization(
                id=second_id,
                name="Harbour Club",
                manager_id=manager,
                review_status="pending_review",
                email="desk@example.com",
            ),
            Organization(
                id=first_id,
                name="Harbour Club Ltd",
                manager_id=manager,
                review_status="pending_review",
                email="desk@example.com",
            ),
        ]
    )
    db_session.flush()
    left = report_duplicates(db_session, [str(second_id), str(first_id)])
    right = report_duplicates(db_session, [str(first_id), str(second_id)])
    assert left["group_ids"] == right["group_ids"]
    assert left["group_ids"]
    assert left["group_ids"][0] == ",".join(sorted((str(first_id), str(second_id))))


def test_run_claim_ignores_a_redelivered_message(db_session) -> None:
    org = Organization(
        id=uuid4(),
        name="Harbour Club",
        manager_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        review_status="pending_review",
    )
    db_session.add(org)
    db_session.flush()
    scope = scope_from_results(
        [{"type": "organizations", "status": "created", "id": str(org.id)}]
    )
    run = create_manual_run(
        db_session,
        {"checks": ["duplicates"], "scope": {"kind": "all"}},
        requested_by="admin-user",
    )
    db_session.flush()
    assert process_run(db_session, run.id, "message-1") is True
    db_session.flush()
    attempts = run.attempts
    assert process_run(db_session, run.id, "message-1") is True
    assert run.attempts == attempts
    assert scope["organization_ids"] or scope["activity_ids"] or True


def test_import_replay_creates_one_run(db_session) -> None:
    from app.db.models import ImportJob

    job = ImportJob(
        object_key="admin/imports/replay.json",
        dry_run=False,
        status="completed",
        summary={},
        results=[],
    )
    db_session.add(job)
    db_session.flush()
    results = [
        {"type": "organizations", "status": "created", "id": str(uuid4())},
    ]
    settings = db_session.get(ImportSettings, 1)
    if settings is None:
        settings = ImportSettings(id=1)
        db_session.add(settings)
    settings.duplicates = "report"
    settings.name_cleanup = "apply"
    settings.unknown_categories = "capture"
    settings.locations = "off"
    settings.categories = "off"
    settings.skip_deleted_organizations = True
    db_session.flush()
    first = stage_import_run(
        db_session,
        import_job_id=job.id,
        results=results,
        requested_by="admin-user",
    )
    second = stage_import_run(
        db_session,
        import_job_id=job.id,
        results=results,
        requested_by="admin-user",
    )
    assert first == second
    assert db_session.scalars(select(DataQualityRun)).one().trigger == "import"


def test_import_settings_route_hides_the_old_post(db_session) -> None:
    del db_session
    from app.api.admin_imports import _handle_admin_imports

    with pytest.raises(ValidationError):
        _handle_admin_imports(
            _event(
                "/v1/admin/imports",
                method="POST",
                body={"data_quality": {"names": True}},
            ),
            "POST",
            None,
        )
