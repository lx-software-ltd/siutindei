#!/usr/bin/env python3
"""Build home wizard choices from categories flagged show_in_wizard.

Age groups and regions are copied from the existing file. ``--write``
reads ``show_in_wizard`` rows from ``DATABASE_URL`` and rewrites the
canonical JSON and the public-site copy.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CHOICES = ROOT / "shared" / "home_wizard" / "home_wizard_choices.json"
PUBLIC_COPY = ROOT / "apps" / "public_www" / "src" / "data" / "home_wizard_choices.json"


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
        "neighbourhoods": existing.get("neighbourhoods") or [],
    }


def load_show_in_wizard_rows(database_url: str) -> list[dict[str, Any]]:
    """Return categories flagged for the home wizard."""
    import psycopg

    url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    url = url.replace("postgresql+psycopg2://", "postgresql://", 1)
    with psycopg.connect(url) as connection:
        fetched = connection.execute(
            """
            SELECT id::text, name, name_translations, show_in_wizard
            FROM activity_categories
            WHERE show_in_wizard IS TRUE
            ORDER BY display_order, name
            """
        ).fetchall()
    return [
        {
            "id": row[0],
            "name": row[1],
            "name_translations": row[2] or {},
            "show_in_wizard": bool(row[3]),
        }
        for row in fetched
    ]


def write_home_wizard_choices(payload: dict[str, Any]) -> None:
    """Write the canonical file and the public-site copy."""
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    CHOICES.write_text(text, encoding="utf-8")
    PUBLIC_COPY.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_COPY.write_text(text, encoding="utf-8")


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
    return slug or "category"


def rows_from_category_export(payload: Any) -> list[dict[str, Any]]:
    """Accept an admin category list or ``{"items": [...]}`` export."""
    items = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise TypeError("category export must be a list or an items object")
    return [row for row in items if isinstance(row, dict)]


def main() -> None:
    """Print the contract, or rewrite the JSON when ``--write`` is set."""
    existing = json.loads(CHOICES.read_text(encoding="utf-8"))
    if "--from-json" in sys.argv:
        index = sys.argv.index("--from-json")
        if index + 1 >= len(sys.argv):
            raise SystemExit("--from-json requires a file path")
        raw = json.loads(Path(sys.argv[index + 1]).read_text(encoding="utf-8"))
        built = build_home_wizard_choices(rows_from_category_export(raw), existing)
        write_home_wizard_choices(built)
        print(
            f"Wrote {CHOICES.name} version {built.get('version')} "
            f"({len(built.get('activityTypes') or [])} activity types)."
        )
        return
    if "--write" not in sys.argv:
        print(
            "Home wizard choices stay in "
            f"{CHOICES.name} version {existing.get('version')}. "
            "Run with --write and DATABASE_URL, or --from-json <export>."
        )
        return
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL is required with --write")
    built = build_home_wizard_choices(
        load_show_in_wizard_rows(database_url),
        existing,
    )
    write_home_wizard_choices(built)
    print(
        f"Wrote {CHOICES.name} version {built.get('version')} "
        f"({len(built.get('activityTypes') or [])} activity types)."
    )


if __name__ == "__main__":
    main()
