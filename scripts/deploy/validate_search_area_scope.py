#!/usr/bin/env python3
"""Fail a deploy when SEARCH_AREA_SCOPE names an unknown area.

A blank value is unrestricted and exits 0. Unknown slugs exit 1 so a
typo cannot ship a public site that hides every neighbourhood, or a
Lambda that returns no activities.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from app.data.hk_neighbourhoods import (
    neighbourhoods_for_scope_token,
    resolve_search_area_scope,
)


def main() -> int:
    raw = os.environ.get("SEARCH_AREA_SCOPE", "")
    resolved, unknown = resolve_search_area_scope(raw)
    if resolved is None:
        print("SEARCH_AREA_SCOPE is unset. Public search is not limited.")
        return 0
    seen: set[str] = set()
    for part in raw.split(","):
        token = part.strip().casefold()
        if not token or token in seen or token in unknown:
            continue
        seen.add(token)
        leaves = neighbourhoods_for_scope_token(token)
        count = 0 if leaves is None else len(leaves)
        print(f"  {token}: {count} neighbourhoods")
    print(f"SEARCH_AREA_SCOPE expands to {len(resolved)} neighbourhoods.")
    if unknown:
        print("Unknown SEARCH_AREA_SCOPE slugs: " + ", ".join(unknown), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
