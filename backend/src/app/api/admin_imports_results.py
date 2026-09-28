"""Result helpers for admin imports."""

from __future__ import annotations

from typing import Any

from app.exceptions import ValidationError


def record_result(
    results: list[dict[str, Any]],
    summary: dict[str, Any],
    record_type: str,
    key: str,
    status: str,
    entity_id: str | None = None,
    warnings: list[str] | None = None,
    errors: list[dict[str, Any]] | None = None,
    path: str | None = None,
) -> None:
    warnings_list = list(warnings or [])
    errors_list = list(errors or [])
    result = {
        "type": record_type,
        "key": key,
        "status": status,
        "id": entity_id,
        "warnings": warnings_list,
        "errors": errors_list,
    }
    if errors_list:
        first = errors_list[0]
        result["error"] = (
            first.get("message") if isinstance(first, dict) else str(first)
        )
    if path:
        result["path"] = path
    results.append(result)

    counts = summary.get(record_type)
    if isinstance(counts, dict) and status in counts:
        counts[status] += 1
    summary["warnings"] += len(warnings_list)
    summary["errors"] += len(errors_list)


def record_skipped_children(
    raw_parent: dict[str, Any],
    key_prefix: str,
    results: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    for section, record_type in (
        ("locations", "locations"),
        ("activities", "activities"),
        ("pricing", "pricing"),
        ("schedules", "schedules"),
    ):
        items = raw_parent.get(section)
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            item_key = f"{key_prefix} / {section}[{index}]"
            if isinstance(item, dict) and "name" in item:
                item_key = f"{key_prefix} / {item.get('name')}"
            record_result(
                results,
                summary,
                record_type,
                item_key,
                "skipped",
                errors=[{"message": "Parent record failed"}],
            )


def init_summary() -> dict[str, Any]:
    return {
        "organizations": init_counts(),
        "locations": init_counts(),
        "activities": init_counts(),
        "pricing": init_counts(),
        "schedules": init_counts(),
        "warnings": 0,
        "errors": 0,
        "captured_categories": 0,
    }


def init_counts() -> dict[str, int]:
    return {"created": 0, "updated": 0, "failed": 0, "skipped": 0}


def format_error(exc: ValidationError) -> dict[str, Any]:
    return {"message": exc.message, "field": exc.field}
