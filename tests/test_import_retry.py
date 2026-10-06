"""Retry selection keeps failed organizations and merges their new rows."""

from __future__ import annotations

from app.api.admin_imports_retry import merge_import_results, select_retry_organizations


def test_select_retry_matches_path_or_name() -> None:
    payload = {
        "organizations": [
            {"name": "Kept Studio"},
            {"name": "Failed Studio"},
            {"name": "Also Fine"},
        ]
    }
    previous = [
        {
            "type": "organizations",
            "key": "Kept Studio",
            "status": "created",
            "path": "organizations[0]",
        },
        {
            "type": "organizations",
            "key": "Failed Studio",
            "status": "failed",
            "path": "organizations[1]",
        },
        {
            "type": "activities",
            "key": "Failed Studio / Clay",
            "status": "failed",
            "path": "organizations[1]/activities[0]",
        },
    ]
    filtered, unmatched, paths, names = select_retry_organizations(payload, previous)
    assert [item["name"] for item in filtered["organizations"]] == ["Failed Studio"]
    assert unmatched == []
    assert "organizations[1]" in paths
    assert "failed studio" in names


def test_merge_replaces_retried_rows_and_notes_missing_orgs() -> None:
    previous_results = [
        {
            "type": "organizations",
            "key": "Kept Studio",
            "status": "created",
            "path": "organizations[0]",
            "warnings": [],
            "errors": [],
        },
        {
            "type": "organizations",
            "key": "Gone Studio",
            "status": "failed",
            "path": "organizations[1]",
            "warnings": [],
            "errors": [{"message": "bad"}],
        },
    ]
    new_results = [
        {
            "type": "organizations",
            "key": "Retried Studio",
            "status": "created",
            "path": "organizations[0]",
            "warnings": [],
            "errors": [],
        },
    ]
    summary, merged = merge_import_results(
        previous_results,
        {"captured_categories": 1},
        new_results,
        {"captured_categories": 2},
        paths={"organizations[1]"},
        names={"gone studio"},
        unmatched=[previous_results[1]],
    )
    keys = [row["key"] for row in merged]
    assert "Kept Studio" in keys
    assert "Retried Studio" in keys
    assert any(
        row["status"] == "skipped" and "no longer contains" in row["warnings"][0]
        for row in merged
    )
    assert summary["captured_categories"] == 3
    assert summary["organizations"]["created"] == 2
    assert summary["organizations"]["skipped"] == 1
