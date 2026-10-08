#!/usr/bin/env python3
"""Fail when production Python exceeds 500 lines, unless allowlisted.

The allowlist only shrinks: an entry must exist and must still be over
the limit. Alembic revisions are outside this scan.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 500
SCAN_ROOTS = (ROOT / "backend" / "src", ROOT / "backend" / "lambda")
ALLOWLIST = ROOT / "scripts" / "python-file-length-allowlist.txt"


def _allowlist() -> list[str]:
    if not ALLOWLIST.exists():
        return []
    entries: list[str] = []
    for line in ALLOWLIST.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        entries.append(stripped)
    return entries


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def main() -> int:
    errors: list[str] = []
    allowed = set(_allowlist())
    seen: set[str] = set()
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            rel = path.relative_to(ROOT).as_posix()
            count = _line_count(path)
            seen.add(rel)
            if count <= LIMIT:
                continue
            if rel in allowed:
                continue
            errors.append(f"{rel} is {count} lines (max {LIMIT})")
    for rel in sorted(allowed):
        path = ROOT / rel
        if not path.exists():
            errors.append(f"allowlist entry does not exist: {rel}")
            continue
        if rel not in seen:
            errors.append(f"allowlist entry is outside the scan: {rel}")
            continue
        if _line_count(path) <= LIMIT:
            errors.append(f"allowlist entry is now within {LIMIT} lines; remove {rel}")
    if errors:
        print("Python file length check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Python file length check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
