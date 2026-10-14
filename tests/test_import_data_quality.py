"""Import Settings: which Data quality checks run after a live import."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from app.api.admin_imports import _handle_admin_imports
from app.exceptions import ValidationError
from app.services.import_data_quality import (
    QUALITY_KEYS,
    default_settings,
    imported_org_ids,
    load_settings,
    parse_settings,
    run_import_data_quality,
    save_settings,
)
from botocore.exceptions import ClientError


def _event(path: str, *, method: str = "GET", body: dict | None = None) -> dict:
    event = {
        "httpMethod": method,
        "path": path,
        "headers": {"Content-Type": "application/json"},
        "requestContext": {
            "requestId": "test-request",
            "authorizer": {
                "groups": "admin",
                "userSub": "admin-user",
            },
        },
    }
    if body is not None:
        event["body"] = json.dumps(body)
    return event


def _no_such_key() -> ClientError:
    return ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "missing"}},
        "GetObject",
    )


def test_default_settings_are_off() -> None:
    assert default_settings() == {
        "duplicates": False,
        "names": False,
        "locations": False,
        "categories": False,
    }
    assert tuple(default_settings()) == QUALITY_KEYS


def test_parse_settings_fills_missing_keys() -> None:
    assert parse_settings({"names": True}) == {
        "duplicates": False,
        "names": True,
        "locations": False,
        "categories": False,
    }


def test_parse_settings_reads_nested_data_quality() -> None:
    parsed = parse_settings({"data_quality": {"locations": True, "categories": True}})
    assert parsed["locations"] is True
    assert parsed["categories"] is True
    assert parsed["duplicates"] is False


def test_parse_settings_rejects_non_bool() -> None:
    with pytest.raises(ValidationError, match="must be a boolean"):
        parse_settings({"names": "yes"})


def test_load_settings_defaults_when_bucket_missing(monkeypatch) -> None:
    monkeypatch.delenv("ADMIN_IMPORT_EXPORT_BUCKET", raising=False)
    assert load_settings() == default_settings()


def test_load_settings_defaults_when_object_missing(monkeypatch) -> None:
    client = MagicMock()
    client.get_object.side_effect = _no_such_key()
    monkeypatch.setenv("ADMIN_IMPORT_EXPORT_BUCKET", "import-bucket")
    monkeypatch.setattr(
        "app.services.import_data_quality.get_s3_client",
        lambda: client,
    )
    assert load_settings() == default_settings()


def test_load_settings_reads_saved_flags(monkeypatch) -> None:
    client = MagicMock()
    client.get_object.return_value = {
        "Body": SimpleNamespace(read=lambda: json.dumps({"names": True}).encode())
    }
    monkeypatch.setenv("ADMIN_IMPORT_EXPORT_BUCKET", "import-bucket")
    monkeypatch.setattr(
        "app.services.import_data_quality.get_s3_client",
        lambda: client,
    )
    assert load_settings()["names"] is True
    assert load_settings()["duplicates"] is False


def test_save_settings_writes_s3(monkeypatch) -> None:
    client = MagicMock()
    monkeypatch.setenv("ADMIN_IMPORT_EXPORT_BUCKET", "import-bucket")
    monkeypatch.setattr(
        "app.services.import_data_quality.get_s3_client",
        lambda: client,
    )
    saved = save_settings({"duplicates": True, "categories": True})
    assert saved == {
        "duplicates": True,
        "names": False,
        "locations": False,
        "categories": True,
    }
    client.put_object.assert_called_once()
    kwargs = client.put_object.call_args.kwargs
    assert kwargs["Bucket"] == "import-bucket"
    assert kwargs["Key"] == "admin/settings/import-data-quality.json"
    assert json.loads(kwargs["Body"].decode()) == saved


def test_imported_org_ids_uses_written_organizations() -> None:
    assert imported_org_ids(
        [
            {"type": "organizations", "status": "created", "id": "org-a"},
            {"type": "organizations", "status": "updated", "id": "org-b"},
            {"type": "organizations", "status": "skipped", "id": "org-c"},
            {"type": "locations", "status": "created", "id": "loc-1"},
            {"type": "organizations", "status": "failed"},
        ]
    ) == ["org-a", "org-b"]


def test_run_skips_when_all_off(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.import_data_quality.load_settings",
        lambda: default_settings(),
    )
    result = run_import_data_quality(
        results=[{"type": "organizations", "status": "created", "id": "org-1"}],
        requested_by="admin-user",
    )
    assert result["ran"] == []
    assert result["skipped"] == list(QUALITY_KEYS)
    assert result["errors"] == []


def test_run_names_for_imported_orgs(monkeypatch) -> None:
    calls: list[dict] = []

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def commit(self):
            return None

        def rollback(self):
            return None

    monkeypatch.setattr(
        "app.services.import_data_quality.load_settings",
        lambda: parse_settings({"names": True}),
    )
    monkeypatch.setattr(
        "app.services.import_data_quality.Session", lambda *a, **k: _Session()
    )
    monkeypatch.setattr("app.services.import_data_quality.get_engine", lambda: None)

    def _scan(session, **kwargs):
        calls.append(kwargs)
        return {"created": 1}

    monkeypatch.setattr("app.services.import_data_quality.scan_names", _scan)
    result = run_import_data_quality(
        results=[
            {"type": "organizations", "status": "created", "id": str(UUID(int=1))}
        ],
        requested_by="admin-user",
    )
    assert result["ran"] == ["names"]
    assert result["skipped"] == ["duplicates", "locations", "categories"]
    assert calls[0]["review_scope"] == "pending_review"
    assert calls[0]["org_id"] == UUID(int=1)


def test_run_records_busy_location_without_raising(monkeypatch) -> None:
    from app.services.location_fix_scan import LocationScanBusy

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def commit(self):
            return None

        def rollback(self):
            return None

    monkeypatch.setattr(
        "app.services.import_data_quality.load_settings",
        lambda: parse_settings({"locations": True}),
    )
    monkeypatch.setattr(
        "app.services.import_data_quality.Session", lambda *a, **k: _Session()
    )
    monkeypatch.setattr("app.services.import_data_quality.get_engine", lambda: None)

    def _start(*args, **kwargs):
        raise LocationScanBusy()

    monkeypatch.setattr(
        "app.services.import_data_quality.start_location_scan",
        _start,
    )
    result = run_import_data_quality(
        results=[
            {"type": "organizations", "status": "created", "id": str(UUID(int=2))}
        ],
        requested_by="admin-user",
    )
    assert result["ran"] == []
    assert result["errors"] == [{"check": "locations", "error": "busy"}]


def test_get_settings_returns_defaults(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.admin_imports_settings.load_import_data_quality_settings",
        lambda: default_settings(),
    )
    response = _handle_admin_imports(
        _event("/v1/admin/imports/settings"), "GET", "settings"
    )
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == default_settings()


def test_post_settings_saves_without_object_key(monkeypatch) -> None:
    saved: dict = {}

    def _save(body):
        saved.update(body)
        return parse_settings(body)

    monkeypatch.setattr(
        "app.api.admin_imports_settings.save_import_data_quality_settings",
        _save,
    )
    response = _handle_admin_imports(
        _event(
            "/v1/admin/imports",
            method="POST",
            body={"data_quality": {"duplicates": True, "names": True}},
        ),
        "POST",
        None,
    )
    assert response["statusCode"] == 200
    assert json.loads(response["body"])["names"] is True
    assert saved["data_quality"]["duplicates"] is True


def test_importer_cannot_save_settings(monkeypatch) -> None:
    saved = {"called": False}

    def _save(body):
        saved["called"] = True
        return parse_settings(body)

    monkeypatch.setattr(
        "app.api.admin_imports_settings.save_import_data_quality_settings",
        _save,
    )
    event = _event(
        "/v1/admin/imports",
        method="POST",
        body={"data_quality": {"names": True}},
    )
    event["requestContext"]["authorizer"] = {
        "groups": "importer",
        "userSub": "importer-user",
    }
    with pytest.raises(ValidationError, match="object_key is required"):
        _handle_admin_imports(event, "POST", None)
    assert saved["called"] is False


def test_post_import_with_object_key_is_not_settings(monkeypatch) -> None:
    called = {"process": False}

    def _process(event):
        called["process"] = True
        return {"statusCode": 200, "body": json.dumps({"ok": True})}

    monkeypatch.setattr("app.api.admin_imports._handle_import_process", _process)
    response = _handle_admin_imports(
        _event(
            "/v1/admin/imports",
            method="POST",
            body={
                "object_key": "admin/imports/file.json",
                "data_quality": {"names": True},
            },
        ),
        "POST",
        None,
    )
    assert response["statusCode"] == 200
    assert called["process"] is True
