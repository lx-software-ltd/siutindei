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


def test_title_case_keeps_cantonese_on_to_or() -> None:
    assert sanitize_name("LEE ON NURSERY", {}).name == "Lee On Nursery"
    assert sanitize_name("MA ON SHAN CLUB", {}).name == "Ma On Shan Club"
    assert sanitize_name("POOI TO PRIMARY SCHOOL", {}).name == (
        "Pooi To Primary School"
    )
    assert sanitize_name("KINDER OR PUI YING", {}).name == "Kinder Or Pui Ying"


def test_title_case_keeps_dotted_initialisms() -> None:
    cleaned = sanitize_name("S.K.H. ST. PETER'S CHURCH KINDERGARTEN", {})
    assert cleaned.name == "S.K.H. St. Peter's Church Kindergarten"
    ymca = sanitize_name("CHINESE Y.M.C.A. KINDERGARTEN", {})
    assert ymca.name == "Chinese Y.M.C.A. Kindergarten"
    nt = sanitize_name("HONG KONG Y.W.C.A. (N.T.)", {})
    assert nt.name == "Hong Kong Y.W.C.A. (N.T.)"


def test_title_case_matches_exceptions_without_dots() -> None:
    cleaned = sanitize_name("S.K.H. KINDERGARTEN", {})
    assert cleaned.name == "S.K.H. Kindergarten"
    hku = sanitize_name("HKU SUMMER CAMP", {})
    assert hku.name == "HKU Summer Camp"
    hyphen = sanitize_name("HKUST-UPC PROGRAMME", {})
    assert hyphen.name == "HKUST-UPC Programme"


def test_title_case_limits_roman_numerals() -> None:
    assert sanitize_name("CENTRE NO. II", {}).name == "Centre No. II"
    assert sanitize_name("TANG TAK LIM KINDERGARTEN", {}).name == (
        "Tang Tak Lim Kindergarten"
    )
    assert sanitize_name("MID LEVELS STUDIO", {}).name == "Mid Levels Studio"
    assert sanitize_name("LI FAMILY CLUB", {}).name == "Li Family Club"


def test_keeps_trailing_period_on_dotted_initialism() -> None:
    cleaned = sanitize_name("Jumpin Gym U.S.A.", {})
    assert cleaned.name == "Jumpin Gym U.S.A."
    assert "trailing_punctuation" not in cleaned.rules


def test_title_case_uses_exception_list_only() -> None:
    cleaned = sanitize_name("ABCD HARBOUR", {})
    assert cleaned.name == "Abcd Harbour"
    kept = sanitize_name("YMCA HARBOUR", {})
    assert kept.name == "YMCA Harbour"
    builtin = sanitize_name("YWCA HARBOUR", {})
    assert builtin.name == "YWCA Harbour"


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


def test_split_keeps_chinese_place_or_branch() -> None:
    branch = sanitize_name("Super Cube 銅鑼灣店", {})
    assert branch.name == "Super Cube 銅鑼灣店"
    assert branch.translation_patch == {"zh": "銅鑼灣店"}
    place = sanitize_name("Fantasy World (深水埗)", {})
    assert place.name == "Fantasy World (深水埗)"
    assert place.translation_patch == {"zh": "深水埗"}
    venue = sanitize_name("荃灣廣場空中樂園 PLAY GARDEN", {})
    assert venue.name == "荃灣廣場空中樂園 Play Garden"
    assert venue.translation_patch == {"zh": "荃灣廣場空中樂園"}


def test_empty_cleanup_keeps_original() -> None:
    assert sanitize_name("...", {}).name == "..."


def test_name_key_strips_limited() -> None:
    assert organization_name_key("Harbour Club") == organization_name_key(
        "Harbour Club Limited"
    )
