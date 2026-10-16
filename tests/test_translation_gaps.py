"""Gap rules for English, Chinese, and Hong Kong text."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.translation_gaps import (
    entity_gaps,
    field_gap,
    language_map,
    source_hash,
)


def test_blank_description_is_not_a_gap() -> None:
    assert field_gap(None, {}) is None
    assert field_gap("  ", {"zh": "  "}) is None


def test_one_language_requests_the_other_two() -> None:
    gap = field_gap("Harbour Club", {})
    assert gap is not None
    assert gap["source"] == {"en": "Harbour Club"}
    assert gap["missing"] == ["zh", "zh-HK"]


def test_chinese_only_requests_english_and_hong_kong() -> None:
    gap = field_gap(None, {"zh": "海港會"})
    assert gap is not None
    assert gap["missing"] == ["en", "zh-HK"]
    assert gap["source"] == {"zh": "海港會"}


def test_complete_field_is_not_a_gap() -> None:
    assert (
        field_gap(
            "Harbour Club",
            {"zh": "海港会", "zh-HK": "海港會"},
        )
        is None
    )


def test_entity_gaps_cover_name_and_description() -> None:
    entity = SimpleNamespace(
        name="Harbour Club",
        name_translations={"zh": "海港会", "zh-HK": "海港會"},
        description="Swim lessons",
        description_translations={},
    )
    gaps = entity_gaps(entity)
    assert "name" not in gaps
    assert gaps["description"]["missing"] == ["zh", "zh-HK"]


def test_language_map_keeps_required_languages_and_strips_space() -> None:
    assert language_map(
        "  Harbour Club  ",
        {"zh": " 海港会 ", "zh-HK": "海港會", "fr": "ignored"},
    ) == {
        "en": "Harbour Club",
        "zh": "海港会",
        "zh-HK": "海港會",
    }


def test_source_hash_changes_when_the_source_text_changes() -> None:
    first = source_hash(
        entity_type="organization",
        entity_id="org-1",
        field="name",
        source={"en": "Harbour Club"},
    )
    second = source_hash(
        entity_type="organization",
        entity_id="org-1",
        field="name",
        source={"en": "Harbour Club Ltd"},
    )
    assert first != second
