#!/usr/bin/env python3
"""Build home wizard choices from categories flagged show_in_wizard.

The committed JSON stays as-is unless a caller writes the result of
``build_home_wizard_choices`` after checking it still lists the current
activity types. Age groups and regions are copied from the existing file.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CHOICES = ROOT / "shared" / "home_wizard" / "home_wizard_choices.json"


def build_home_wizard_choices(
    rows: list[dict[str, Any]],
    existing: dict[str, Any],
) -> dict[str, Any]:
    """Return wizard JSON. Version bumps only when activity types change."""
    by_category = {
        str(item.get("categoryId")): str(item.get("id"))
        for item in existing.get("activityTypes") or []
        if isinstance(item, dict)
    }
    types: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("show_in_wizard"):
            continue
        category_id = str(row.get("id") or "")
        name = str(row.get("name") or "").strip()
        if not category_id or not name:
            continue
        translations = row.get("name_translations") or {}
        if not isinstance(translations, dict):
            translations = {}
        zh = (
            translations.get("zh-HK")
            or translations.get("zh-hk")
            or translations.get("zh")
            or name
        )
        types.append(
            {
                "id": by_category.get(category_id) or _slug(name),
                "categoryId": category_id,
                "labels": {"en": name, "zh-HK": str(zh)},
            }
        )
    version = int(existing.get("version") or 1)
    if types != existing.get("activityTypes"):
        version += 1
    return {
        "version": version,
        "activityTypes": types,
        "ageGroups": existing.get("ageGroups") or [],
        "regions": existing.get("regions") or [],
    }


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
    return slug or "category"


def main() -> None:
    """Print the builder contract. This command does not rewrite the JSON."""
    existing = json.loads(CHOICES.read_text(encoding="utf-8"))
    print(
        "Home wizard choices stay in "
        f"{CHOICES.name} version {existing.get('version')}. "
        "Pass category rows to build_home_wizard_choices."
    )


if __name__ == "__main__":
    main()
