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
    by_path = {
        str(row.get("path") or ""): index
        for index, row in enumerate(failed)
        if row.get("path")
    }
    pending_name: list[tuple[int, Any, str]] = []
    for index, organization in enumerate(organizations):
        path = f"organizations[{index}]"
        raw_name = _payload_name(organization)
        hit = by_path.get(path)
        if hit is not None and hit not in matched:
            matched.add(hit)
            chosen.append(organization)
            paths.add(path)
            continue
        pending_name.append((index, organization, raw_name))
    _match_unique_names(
        failed, pending_name, organizations, matched, chosen, paths, names
    )
    if not chosen:
        raise ValidationError(
            "No failed organizations to retry",
            field="retry_failed",
        )
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
    captured, captured_ids = _captured_total(previous_summary, new_summary)
    summary = _summarize(merged, captured)
    if captured_ids:
        summary["captured_category_ids"] = captured_ids
    return summary, merged


def _match_unique_names(
    failed: list[dict[str, Any]],
    pending_name: list[tuple[int, Any, str]],
    organizations: list[Any],
    matched: set[int],
    chosen: list[Any],
    paths: set[str],
    names: set[str],
) -> None:
    """Match a renamed file position only when the name is unique."""
    unmatched_by_name: dict[str, list[int]] = {}
    for index, row in enumerate(failed):
        if index in matched:
            continue
        stored = _result_name(row)
        if stored:
            unmatched_by_name.setdefault(stored, []).append(index)
    payload_counts: dict[str, int] = {}
    for organization in organizations:
        raw_name = _payload_name(organization)
        if raw_name:
            payload_counts[raw_name] = payload_counts.get(raw_name, 0) + 1
    for _index, organization, raw_name in pending_name:
        if not raw_name:
            continue
        hits = unmatched_by_name.get(raw_name, [])
        if len(hits) != 1 or payload_counts.get(raw_name, 0) != 1:
            continue
        hit = hits[0]
        if hit in matched:
            continue
        matched.add(hit)
        chosen.append(organization)
        stored_path = str(failed[hit].get("path") or "")
        if stored_path:
            paths.add(stored_path)
        names.add(raw_name)


def _payload_name(organization: Any) -> str:
    if isinstance(organization, dict) and isinstance(organization.get("name"), str):
        return normalize_org_name(organization["name"])
    return ""


def _captured_total(
    previous_summary: dict[str, Any],
    new_summary: dict[str, Any],
) -> tuple[int, list[str]]:
    """Union suggestion ids when either summary recorded them."""
    has_ids = (
        "captured_category_ids" in previous_summary
        or "captured_category_ids" in new_summary
    )
    if not has_ids:
        captured = int(previous_summary.get("captured_categories") or 0) + int(
            new_summary.get("captured_categories") or 0
        )
        return captured, []
    union = _captured_ids(previous_summary) | _captured_ids(new_summary)
    if "captured_category_ids" not in previous_summary:
        legacy = int(previous_summary.get("captured_categories") or 0)
        return max(legacy, len(union)), sorted(union)
    return len(union), sorted(union)


def _captured_ids(summary: dict[str, Any]) -> set[str]:
    raw = summary.get("captured_category_ids")
    if not isinstance(raw, list):
        return set()
    return {str(item) for item in raw if item}


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
