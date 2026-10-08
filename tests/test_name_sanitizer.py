"""Deterministic name cleanup."""

from __future__ import annotations

from app.services.name_sanitizer import (
    organization_name_key,
    sanitize_name,
)


def test_title_case_and_unchanged_sample() -> None:
    assert sanitize_name("Test Organization", {}).name == "Test Organization"
    cleaned = sanitize_name("HARBOUR CLUB", {})
    assert cleaned.name == "Harbour Club"
    assert "title_case" in cleaned.rules


def test_title_case_lowercases_particles() -> None:
    cleaned = sanitize_name("SCHOOL OF THE ARTS", {})
    assert cleaned.name == "School of the Arts"
    leading = sanitize_name("THE HARBOUR CLUB", {})
    assert leading.name == "The Harbour Club"
    bracketed = sanitize_name("HARBOUR (THE CLUB OF THE BAY)", {})
    assert bracketed.name == "Harbour (The Club of the Bay)"
    hyphen = sanitize_name("OUT-OF-SCHOOL CLUB", {})
    assert hyphen.name == "Out-of-School Club"


def test_title_case_uses_exception_list_only() -> None:
    cleaned = sanitize_name("YWCA HARBOUR", {})
    assert cleaned.name == "Ywca Harbour"
    kept = sanitize_name("YMCA HARBOUR", {})
    assert kept.name == "YMCA Harbour"


def test_keeps_exception_words_and_strips_brackets() -> None:
    cleaned = sanitize_name("YMCA HARBOUR (LCSD)", {})
    assert cleaned.name == "YMCA Harbour"
    assert "brackets" in cleaned.rules


def test_spaces_before_brackets() -> None:
    cleaned = sanitize_name("bla bla bla(xx xx)", {})
    assert cleaned.name == "bla bla bla (xx xx)"
    assert "whitespace" in cleaned.rules
    assert sanitize_name("Harbour Club[Hall A]", {}).name == "Harbour Club [Hall A]"
    titled = sanitize_name("HARBOUR CLUB(HK)", {})
    assert titled.name == "Harbour Club (HK)"


def test_splits_bilingual_name_into_translation() -> None:
    cleaned = sanitize_name("Harbour 海港會", {})
    assert cleaned.name == "Harbour"
    assert cleaned.translation_patch == {"zh": "海港會"}


def test_split_drops_brackets_that_only_held_chinese() -> None:
    cleaned = sanitize_name("Harbour Club (海港會)", {})
    assert cleaned.name == "Harbour Club"
    assert cleaned.translation_patch == {"zh": "海港會"}
    assert sanitize_name("Harbour Club[海港會]", {}).name == "Harbour Club"


def test_split_keeps_brackets_that_still_have_english() -> None:
    cleaned = sanitize_name("Harbour Club (Central 海港)", {})
    assert cleaned.name == "Harbour Club (Central)"
    assert cleaned.translation_patch == {"zh": "海港"}
    mixed = sanitize_name("Harbour Club (海港 Hall A)", {})
    assert mixed.name == "Harbour Club (Hall A)"
    assert mixed.translation_patch == {"zh": "海港"}


def test_empty_cleanup_keeps_original() -> None:
    assert sanitize_name("...", {}).name == "..."


def test_name_key_strips_limited() -> None:
    assert organization_name_key("Harbour Club") == organization_name_key(
        "Harbour Club Limited"
    )
