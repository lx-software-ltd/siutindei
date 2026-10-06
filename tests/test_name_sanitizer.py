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


def test_keeps_exception_words_and_strips_brackets() -> None:
    cleaned = sanitize_name("YMCA HARBOUR (LCSD)", {})
    assert cleaned.name == "YMCA Harbour"
    assert "brackets" in cleaned.rules


def test_splits_bilingual_name_into_translation() -> None:
    cleaned = sanitize_name("Harbour 海港會", {})
    assert cleaned.name == "Harbour"
    assert cleaned.translation_patch == {"zh": "海港會"}


def test_empty_cleanup_keeps_original() -> None:
    assert sanitize_name("...", {}).name == "..."


def test_name_key_strips_limited() -> None:
    assert organization_name_key("Harbour Club") == organization_name_key(
        "Harbour Club Limited"
    )
