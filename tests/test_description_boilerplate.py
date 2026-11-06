"""Import filler phrases stay aligned across Python and the public site."""

from __future__ import annotations

import re
from pathlib import Path

from app.services.description_boilerplate import (
    CANTONESE_IMPORT_BOILERPLATE,
    ENGLISH_IMPORT_BOILERPLATE,
    ENGLISH_IMPORT_STEMS,
    description_is_import_boilerplate,
    leftover_chinese_boilerplate,
)

_PUBLIC = (
    Path(__file__).resolve().parents[1]
    / "apps/public_www/src/lib/activities/description-boilerplate.ts"
)


def test_public_www_boilerplate_phrases_match_python() -> None:
    text = _PUBLIC.read_text(encoding="utf-8")
    english = re.search(r"export const ENGLISH_IMPORT_BOILERPLATE = '([^']+)'", text)
    cantonese = re.search(
        r"export const CANTONESE_IMPORT_BOILERPLATE = '([^']+)'", text
    )
    stems = re.findall(r"'(is an? )'", text)
    assert english is not None
    assert cantonese is not None
    assert english.group(1) == ENGLISH_IMPORT_BOILERPLATE
    assert cantonese.group(1) == CANTONESE_IMPORT_BOILERPLATE
    assert tuple(stems) == ENGLISH_IMPORT_STEMS


def test_edb_and_lcsd_sentences_are_filler() -> None:
    assert description_is_import_boilerplate(
        "Harbour Club is a class or early-years centre in CENTRAL "
        "for children and families."
    )
    assert description_is_import_boilerplate(
        "Harbour Park is a indoor family venue in Yau Tsim Mong "
        "for children and families."
    )
    assert description_is_import_boilerplate(
        "Harbour Park is a public outdoor venue in Tai Po for children and families."
    )
    assert description_is_import_boilerplate(
        "Harbour Park is a sports venue in Southern for children and families."
    )
    assert description_is_import_boilerplate("南區嘅幼兒或興趣班，適合小朋友同家庭。")
    assert description_is_import_boilerplate(
        "Harbour Park係Sha Tin嘅室內親子場地，適合小朋友同家庭。"
    )


def test_unique_copy_is_not_filler() -> None:
    assert not description_is_import_boilerplate(
        "Saturday art class for children in the harbour."
    )
    assert not description_is_import_boilerplate(
        "Saturday art class for children and families in the harbour."
    )
    assert not leftover_chinese_boilerplate({"zh": "星期六繪畫班"})
    assert leftover_chinese_boilerplate(
        {"zh": "南區嘅幼兒或興趣班，適合小朋友同家庭。"}
    )
