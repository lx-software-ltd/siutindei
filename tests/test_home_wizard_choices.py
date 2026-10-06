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
