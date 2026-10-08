#!/usr/bin/env python3
"""Board runner path and size policy.

Mirrors lx-software ``board_code.py`` so ``board-agent`` and
``board-merge-staging`` cannot drift from the admin Lambda guards.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PROTECTED_DIR_NAMES = frozenset({"auth", "payments", "migrations"})
PROTECTED_ROOTS = frozenset({"infra", ".github"})
# Prefixes and files are this repo's real red zone. The generic names above
# stay so the lx-software mirror remains a subset. See docs/architecture/zones.md.
PROTECTED_PREFIXES = (
    "backend/db/",
    "backend/infrastructure/",
    "backend/lambda/authorizers/",
    "backend/lambda/auth/",
    "backend/lambda/aws_proxy/",
    "backend/src/app/auth/",
    "apps/admin_web/src/app/auth/",
    "apps/siutindei_app/lib/features/auth/",
    "shared/",
    "scripts/deploy/",
    "scripts/ci/",
    ".cursor/hooks/",
)
PROTECTED_FILES = frozenset(
    {
        "backend/src/app/services/aws_proxy.py",
        "backend/src/app/services/openrouter_client.py",
        "scripts/check-pii.sh",
        "scripts/check_pii.py",
        "scripts/pii-denylist.sha256",
        "scripts/test_check_pii.py",
        ".cursor/hooks.json",
        ".pre-commit-config.yaml",
    }
)
CONTENT_ROOT = "content"
ALLOWED_KINDS = frozenset({"feature", "fix", "content"})
LINE_LIMIT = 400
CONTENT_LINE_LIMIT = 2000
CI_OK = frozenset({"success", "neutral", "skipped"})
LOCKFILE_NAMES = frozenset(
    {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "npm-shrinkwrap.json",
        "poetry.lock",
        "Pipfile.lock",
        "Cargo.lock",
        "Gemfile.lock",
        "composer.lock",
        "pubspec.lock",
        "go.sum",
        "uv.lock",
        "flake.lock",
    }
)


def path_parts(path: str) -> list[str]:
    normalized = str(path or "").replace("\\", "/").lstrip("/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return [part for part in normalized.split("/") if part]


def _normalized(path: str) -> str:
    normalized = str(path or "").replace("\\", "/").lstrip("/")
    return normalized.removeprefix("./")


def path_is_protected(path: str) -> bool:
    normalized = _normalized(path)
    if not normalized:
        return False
    if normalized in PROTECTED_FILES:
        return True
    for prefix in PROTECTED_PREFIXES:
        root = prefix.rstrip("/")
        if normalized == root or normalized.startswith(prefix):
            return True
    parts = path_parts(normalized)
    if parts[0] in PROTECTED_ROOTS:
        return True
    return any(part in PROTECTED_DIR_NAMES for part in parts)


def path_is_content(path: str) -> bool:
    parts = path_parts(path)
    return bool(parts) and parts[0] == CONTENT_ROOT


def file_paths(row: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ("filename", "previous_filename"):
        value = str(row.get(key) or "").strip()
        if value:
            out.append(value)
    return out


def path_is_lockfile(path: str) -> bool:
    parts = path_parts(path)
    return bool(parts) and parts[-1] in LOCKFILE_NAMES


def changed_lines(files: list[dict[str, Any]]) -> int:
    total = 0
    for row in files:
        if any(path_is_lockfile(path) for path in file_paths(row)):
            continue
        if row.get("changes") is not None:
            try:
                total += int(row.get("changes") or 0)
                continue
            except (TypeError, ValueError):
                pass
        try:
            total += int(row.get("additions") or 0) + int(row.get("deletions") or 0)
        except (TypeError, ValueError):
            continue
    return total


def files_protected(files: list[dict[str, Any]]) -> list[str]:
    hits: list[str] = []
    for row in files:
        for path in file_paths(row):
            if path_is_protected(path):
                hits.append(path)
    return hits


def files_outside_content(files: list[dict[str, Any]]) -> list[str]:
    return [
        path for row in files for path in file_paths(row) if not path_is_content(path)
    ]


def unknown_kind_reason(kind: str) -> str | None:
    """Reject brief kinds outside feature, fix, and content."""
    supplied = (kind or "").strip().lower()
    if supplied and supplied not in ALLOWED_KINDS:
        return f"unknown brief kind '{supplied}'; expected feature, fix, or content"
    return None


def resolved_kind(files: list[dict[str, Any]], kind: str = "") -> str:
    """Return feature, fix, or content. Content is inferred only for content/**."""
    resolved = (kind or "").strip().lower()
    if resolved:
        return resolved
    if files and not files_outside_content(files):
        return "content"
    return "feature"


def zone_for_files(files: list[dict[str, Any]], *, kind: str = "") -> str:
    """Label a diff for the pull request.

    Content-kind briefs are exempt from the red-zone map. They are still
    confined to content/** by evaluate_files.
    """
    if unknown_kind_reason(kind):
        return "unknown"
    if resolved_kind(files, kind) == "content":
        return "content"
    if files_protected(files):
        return "red"
    return "open"


def evaluate_files(files: list[dict[str, Any]], *, kind: str = "") -> str | None:
    """Return a refusal reason, or None when the change set is allowed."""
    unknown = unknown_kind_reason(kind)
    if unknown:
        return unknown
    lines = changed_lines(files)
    kind_name = resolved_kind(files, kind)
    # Content briefs stay exempt from the red-zone map. A path under
    # content/** is not refused for containing a protected directory name.
    if kind_name == "content":
        extra = files_outside_content(files)
        if extra:
            return f"content kind may only change content/** ({extra[0]})"
        if lines > CONTENT_LINE_LIMIT:
            return (
                f"content pull request changes {lines} lines (max {CONTENT_LINE_LIMIT})"
            )
        return None
    protected = files_protected(files)
    if protected:
        return f"protected path {protected[0]}"
    if lines > LINE_LIMIT:
        return f"pull request changes {lines} lines (max {LINE_LIMIT})"
    return None


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def worktree_files(base: str) -> list[dict[str, Any]]:
    """Build a PR-files-like list from ``git diff`` against *base*."""
    names = _git("diff", "--name-status", base)
    numstat = _git("diff", "--numstat", base)
    untracked = _git("ls-files", "--others", "--exclude-standard")
    stats: dict[str, tuple[int, int]] = {}
    for line in numstat.splitlines():
        if not line.strip():
            continue
        added, deleted, path = line.split("\t", 2)
        try:
            plus = int(added) if added != "-" else 0
            minus = int(deleted) if deleted != "-" else 0
        except ValueError:
            plus, minus = 0, 0
        stats[path] = (plus, minus)
    files: list[dict[str, Any]] = []
    for line in names.splitlines():
        if not line.strip():
            continue
        status, rest = line.split("\t", 1)
        previous = ""
        filename = rest
        if status.startswith("R") or status.startswith("C"):
            previous, filename = rest.split("\t", 1)
        plus, minus = stats.get(filename, (0, 0))
        files.append(
            {
                "filename": filename,
                "previous_filename": previous,
                "additions": plus,
                "deletions": minus,
                "changes": plus + minus,
            }
        )
    for path in untracked.splitlines():
        if not path.strip():
            continue
        files.append(
            {
                "filename": path,
                "previous_filename": "",
                "additions": 0,
                "deletions": 0,
                "changes": 0,
            }
        )
    return files


def ci_is_green(check_runs: list[dict[str, Any]], combined_state: str) -> bool:
    if check_runs:
        return all(
            str(row.get("status") or "") == "completed"
            and str(row.get("conclusion") or "") in CI_OK
            for row in check_runs
            if isinstance(row, dict)
        )
    # Docs-only PRs skip lint.yml / test.yml path filters, so GitHub
    # reports pending with zero check runs. Treat that as green unless
    # the combined status already failed.
    return combined_state not in {"failure", "error"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-worktree",
        metavar="BASE",
        help="Refuse if the worktree vs BASE touches protected paths or size",
    )
    parser.add_argument(
        "--kind",
        default="",
        help="feature, fix, or content (default: infer)",
    )
    parser.add_argument(
        "--files-json",
        help="Evaluate a GitHub PR files JSON array from a file or stdin (-)",
    )
    parser.add_argument(
        "--zone",
        metavar="BASE",
        help="Print content, red, or open for the worktree vs BASE",
    )
    args = parser.parse_args(argv)

    if args.files_json:
        if args.files_json == "-":
            raw = sys.stdin.read()
        else:
            raw = Path(args.files_json).read_text(encoding="utf-8")
        payload = json.loads(raw)
        files = payload if isinstance(payload, list) else payload.get("files") or []
        reason = evaluate_files(files, kind=args.kind)
        if reason:
            print(reason, file=sys.stderr)
            return 1
        print(f"ok lines={changed_lines(files)}")
        return 0

    if args.zone:
        files = worktree_files(args.zone)
        print(zone_for_files(files, kind=args.kind))
        return 0

    if args.check_worktree:
        files = worktree_files(args.check_worktree)
        reason = evaluate_files(files, kind=args.kind)
        if reason:
            print(reason, file=sys.stderr)
            return 1
        if not files:
            print("ok no changes")
            return 0
        print(f"ok lines={changed_lines(files)} files={len(files)}")
        return 0

    parser.error("pass --check-worktree BASE, --zone BASE, or --files-json")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
