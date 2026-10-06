"""Retry organizations that failed inside a completed import."""

from __future__ import annotations

from typing import Any

from app.api.admin_imports_catalog import normalize_org_name
from app.api.admin_imports_results import init_summary
from app.exceptions import ValidationError


def select_retry_organizations(
    payload: dict[str, Any],
    previous_results: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], set[str], set[str]]:
    """Keep organizations whose previous result failed.

    Returns the filtered payload, unmatched failed rows, matched paths,
    and matched normalised names.
    """
    organizations = payload.get("organizations")
    if not isinstance(organizations, list):
        raise ValidationError(
            "organizations must be a list",
            field="organizations",
        )
    failed = [
        row
        for row in previous_results
        if row.get("type") == "organizations" and row.get("status") == "failed"
    ]
    chosen: list[Any] = []
    paths: set[str] = set()
    names: set[str] = set()
    matched: set[int] = set()
    for index, organization in enumerate(organizations):
        path = f"organizations[{index}]"
        raw_name = ""
        if isinstance(organization, dict) and isinstance(organization.get("name"), str):
            raw_name = normalize_org_name(organization["name"])
        hit = _matching_failure(failed, path, raw_name)
        if hit is None:
            continue
        matched.add(hit)
        chosen.append(organization)
        paths.add(path)
        if raw_name:
            names.add(raw_name)
        stored_name = _result_name(failed[hit])
        if stored_name:
            names.add(stored_name)
    unmatched = [row for index, row in enumerate(failed) if index not in matched]
    filtered = dict(payload)
    filtered["organizations"] = chosen
    return filtered, unmatched, paths, names


def merge_import_results(
    previous_results: list[dict[str, Any]],
    previous_summary: dict[str, Any],
    new_results: list[dict[str, Any]],
    new_summary: dict[str, Any],
    *,
    paths: set[str],
    names: set[str],
    unmatched: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Replace retried rows and recompute the job summary."""
    kept = [row for row in previous_results if not _belongs_to_retry(row, paths, names)]
    notes = [_unmatched_result(row) for row in unmatched]
    merged = kept + new_results + notes
    captured = int(previous_summary.get("captured_categories") or 0) + int(
        new_summary.get("captured_categories") or 0
    )
    summary = _summarize(merged, captured)
    return summary, merged


def _matching_failure(
    failed: list[dict[str, Any]],
    path: str,
    raw_name: str,
) -> int | None:
    for index, row in enumerate(failed):
        if str(row.get("path") or "") == path:
            return index
        stored = _result_name(row)
        if raw_name and stored and stored == raw_name:
            return index
    return None


def _result_name(row: dict[str, Any]) -> str:
    key = str(row.get("key") or "")
    if not key or key.startswith("organizations["):
        return ""
    return normalize_org_name(key)


def _belongs_to_retry(row: dict[str, Any], paths: set[str], names: set[str]) -> bool:
    path = str(row.get("path") or "")
    if path in paths or any(path.startswith(f"{item}/") for item in paths):
        return True
    key = str(row.get("key") or "")
    folded = normalize_org_name(key) if key else ""
    if folded and folded in names:
        return True
    for name in names:
        if key.casefold().startswith(f"{name} /"):
            return True
    return False


def _unmatched_result(row: dict[str, Any]) -> dict[str, Any]:
    key = str(row.get("key") or row.get("path") or "organization")
    return {
        "type": "organizations",
        "key": key,
        "status": "skipped",
        "id": None,
        "path": row.get("path"),
        "warnings": [
            "Import file no longer contains this failed organization",
        ],
        "errors": [],
    }


def _summarize(results: list[dict[str, Any]], captured: int) -> dict[str, Any]:
    summary = init_summary()
    summary["captured_categories"] = captured
    for row in results:
        counts = summary.get(str(row.get("type") or ""))
        status = str(row.get("status") or "")
        if isinstance(counts, dict) and status in counts:
            counts[status] += 1
        summary["warnings"] += len(row.get("warnings") or [])
        summary["errors"] += len(row.get("errors") or [])
    return summary
