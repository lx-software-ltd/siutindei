"""Home wizard choices stay aligned with show_in_wizard categories."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/codegen/generate_home_wizard_choices.py"
)
_CHOICES = (
    Path(__file__).resolve().parents[1] / "shared/home_wizard/home_wizard_choices.json"
)


def _builder():
    spec = importlib.util.spec_from_file_location("home_wizard_choices", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_current_wizard_categories_keep_the_committed_file() -> None:
    existing = json.loads(_CHOICES.read_text(encoding="utf-8"))
    rows = [
        {
            "id": item["categoryId"],
            "name": item["labels"]["en"],
            "name_translations": {"zh-HK": item["labels"]["zh-HK"]},
            "show_in_wizard": True,
        }
        for item in existing["activityTypes"]
    ]
    built = _builder().build_home_wizard_choices(rows, existing)
    assert built["activityTypes"] == existing["activityTypes"]
    assert built["version"] == existing["version"]
    assert built["ageGroups"] == existing["ageGroups"]
    assert built["regions"] == existing["regions"]
    assert built["neighbourhoods"] == existing["neighbourhoods"]


def test_new_wizard_category_bumps_the_version() -> None:
    existing = json.loads(_CHOICES.read_text(encoding="utf-8"))
    rows = [
        {
            "id": "c1111111-1111-1111-1111-111111111155",
            "name": "Ceramics",
            "name_translations": {"zh": "陶藝"},
            "show_in_wizard": True,
        }
    ]
    built = _builder().build_home_wizard_choices(rows, existing)
    assert built["version"] == existing["version"] + 1
    assert built["activityTypes"][0]["labels"]["zh-HK"] == "陶藝"
    assert built["ageGroups"] == existing["ageGroups"]


def test_category_export_accepts_an_items_object() -> None:
    rows = _builder().rows_from_category_export(
        {
            "items": [
                {
                    "id": "c1111111-1111-1111-1111-111111111201",
                    "name": "Early years and schools",
                    "name_translations": {"zh-HK": "幼兒及學校"},
                    "show_in_wizard": True,
                },
                {"name": "not a category"},
            ]
        }
    )
    assert len(rows) == 2
    built = _builder().build_home_wizard_choices(
        rows,
        {"version": 2, "activityTypes": [], "ageGroups": [], "regions": []},
    )
    assert built["activityTypes"][0]["id"] == "early-years-and-schools"


def test_kinds_are_copied_through() -> None:
    existing = json.loads(_CHOICES.read_text(encoding="utf-8"))
    built = _builder().build_home_wizard_choices([], existing)
    assert built["kinds"] == existing["kinds"]


def test_committed_file_lists_topics_kinds_and_five_age_groups() -> None:
    existing = json.loads(_CHOICES.read_text(encoding="utf-8"))
    assert existing["version"] == 3
    assert [item["id"] for item in existing["activityTypes"]] == [
        "baby-toddler",
        "sports",
        "water",
        "art",
        "performing",
        "languages",
        "stem",
        "tutoring",
        "community",
    ]
    assert [item["categoryId"][-4:] for item in existing["activityTypes"]] == [
        str(suffix) for suffix in range(1301, 1310)
    ]
    assert [
        (group["id"], group["minAge"], group["maxAge"])
        for group in existing["ageGroups"]
    ] == [("0-1", 0, 0), ("1-2", 1, 2), ("3-5", 3, 5), ("6-11", 6, 11), ("12-18", 12, 18)]
    for group in existing["ageGroups"]:
        assert group["minAge"] <= group["searchAge"] <= group["maxAge"]
    kinds = {kind["id"]: kind for kind in existing["kinds"]}
    assert list(kinds) == ["class", "camp", "place", "eat"]
    assert [kind_id for kind_id, kind in kinds.items() if kind["hasTopics"]] == [
        "class",
        "camp",
    ]
    assert [kind_id for kind_id, kind in kinds.items() if kind["pilot"]] == ["eat"]
    for kind in kinds.values():
        assert set(kind["labels"]) == {"en", "zh-HK"}
        assert set(kind["hint"]) == {"en", "zh-HK"}
