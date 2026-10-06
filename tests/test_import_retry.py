"""Retry selection keeps failed organizations and merges their new rows."""

from __future__ import annotations

import pytest

from app.api.admin_imports_retry import merge_import_results, select_retry_organizations
from app.exceptions import ValidationError


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
    assert names == set()


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


def test_same_name_does_not_drop_the_successful_twin() -> None:
    payload = {
        "organizations": [
            {"name": "Studio"},
            {"name": "Studio"},
        ]
    }
    previous = [
        {
            "type": "organizations",
            "key": "Studio",
            "status": "created",
            "path": "organizations[0]",
            "warnings": [],
            "errors": [],
        },
        {
            "type": "organizations",
            "key": "Studio",
            "status": "failed",
            "path": "organizations[1]",
            "warnings": [],
            "errors": [{"message": "bad"}],
        },
        {
            "type": "activities",
            "key": "Studio / Clay",
            "status": "failed",
            "path": "organizations[1]/activities[0]",
            "warnings": [],
            "errors": [],
        },
    ]
    filtered, unmatched, paths, names = select_retry_organizations(payload, previous)
    assert len(filtered["organizations"]) == 1
    assert unmatched == []
    assert paths == {"organizations[1]"}
    assert names == set()
    _summary, merged = merge_import_results(
        previous,
        {"captured_categories": 0},
        [
            {
                "type": "organizations",
                "key": "Studio",
                "status": "created",
                "path": "organizations[0]",
                "warnings": [],
                "errors": [],
            }
        ],
        {"captured_categories": 0},
        paths=paths,
        names=names,
        unmatched=unmatched,
    )
    assert any(
        row["path"] == "organizations[0]" and row["status"] == "created"
        for row in merged
    )
    assert all(row.get("path") != "organizations[1]" for row in merged)


def test_shifted_index_matches_a_unique_name() -> None:
    payload = {"organizations": [{"name": "Failed Studio"}]}
    previous = [
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
            "key": "Failed Studio",
            "status": "failed",
            "path": "organizations[1]",
            "warnings": [],
            "errors": [{"message": "bad"}],
        },
    ]
    filtered, unmatched, paths, names = select_retry_organizations(payload, previous)
    assert [item["name"] for item in filtered["organizations"]] == ["Failed Studio"]
    assert unmatched == []
    assert paths == {"organizations[1]"}
    assert names == {"failed studio"}


def test_retry_without_failures_is_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        select_retry_organizations(
            {"organizations": [{"name": "Kept Studio"}]},
            [
                {
                    "type": "organizations",
                    "key": "Kept Studio",
                    "status": "created",
                    "path": "organizations[0]",
                }
            ],
        )
    assert exc_info.value.field == "retry_failed"


def test_merge_counts_each_captured_category_once() -> None:
    summary, _merged = merge_import_results(
        [],
        {
            "captured_categories": 1,
            "captured_category_ids": ["same-label"],
        },
        [],
        {
            "captured_categories": 2,
            "captured_category_ids": ["same-label", "new-label"],
        },
        paths=set(),
        names=set(),
        unmatched=[],
    )
    assert summary["captured_categories"] == 2
    assert summary["captured_category_ids"] == ["new-label", "same-label"]
