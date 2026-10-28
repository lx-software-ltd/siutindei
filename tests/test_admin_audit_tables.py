"""Audit log table filter lists every currently audited table."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from app.api.admin_audit import AUDITABLE_TABLES, _list_audit_logs
from app.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "backend" / "db" / "alembic" / "versions"

TRIGGER_RE = re.compile(r"CREATE TRIGGER ([a-z0-9_]+)_audit_trigger\b")
AUDITED_LIST_RE = re.compile(r"AUDITED_TABLES\s*=\s*\[(.*?)\]", re.DOTALL)
NAME_RE = re.compile(r'"([a-z0-9_]+)"')

# Tables that once had audit triggers and were dropped in later revisions.
DROPPED_AUDITED_TABLES = frozenset(
    {
        "organization_access_requests",
        "organization_suggestions",
    }
)

# Rows written by AuditService without a table trigger.
APPLICATION_AUDIT_TABLES = frozenset(
    {
        "cognito_user",
        "organization_duplicate_dismissals",
        "organization_merges",
    }
)


def _trigger_tables_from_migrations() -> set[str]:
    tables: set[str] = set()
    for path in VERSIONS.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        tables.update(TRIGGER_RE.findall(text))
        listed = AUDITED_LIST_RE.search(text)
        if listed:
            tables.update(NAME_RE.findall(listed.group(1)))
    return tables


def _expected_auditable_tables() -> set[str]:
    return (
        _trigger_tables_from_migrations() - DROPPED_AUDITED_TABLES
    ) | APPLICATION_AUDIT_TABLES


def test_auditable_tables_match_triggers_and_application_logs() -> None:
    assert AUDITABLE_TABLES == _expected_auditable_tables()


def test_auditable_tables_sort_alphabetically() -> None:
    assert sorted(AUDITABLE_TABLES) == [
        "activities",
        "activity_categories",
        "activity_locations",
        "activity_pricing",
        "activity_schedule",
        "api_keys",
        "category_suggestion_settings",
        "category_suggestions",
        "cognito_user",
        "feedback_labels",
        "import_settings",
        "locations",
        "organization_duplicate_dismissals",
        "organization_feedback",
        "organization_merges",
        "organizations",
        "tickets",
    ]


def test_list_audit_logs_rejects_unknown_table() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _list_audit_logs({"queryStringParameters": {"table": "listing_events"}})
    assert exc_info.value.field == "table"
    assert "activity_categories" in str(exc_info.value)
    assert "organization_merges" in str(exc_info.value)


def test_list_audit_logs_rejects_dropped_table() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _list_audit_logs(
            {"queryStringParameters": {"table": "organization_access_requests"}}
        )
    assert exc_info.value.field == "table"
