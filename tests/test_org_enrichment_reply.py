"""Website enrichment: model replies that are long, compact, or cut off."""

from __future__ import annotations

import json
import logging

from app.services.enrichment.extract import validate_model_sheet
from app.services.enrichment.prompt import estimated_tokens, prompt_pages
from app.services.enrichment.sheet import read_sheet, sheet_from_text
from app.utils.logging import StructuredLogFormatter

_VENUE = "https://club.test/venue-locations"
_TERM = "https://club.test/fall-term"


def _pages() -> list[dict[str, object]]:
    return [
        {
            "final_url": _VENUE,
            "text": (
                "VENUE LOCATIONS North Court Example Sports Centre, 12 Sample Road, "
                "Hong Kong South Court Demo Hall, 3/F, 8 Fictional Street, Hong Kong"
            ),
        },
        {
            "final_url": _TERM,
            "text": (
                "Fall Term Skills Training for ages 6-12. Junior Skills Class "
                "Wednesdays 4:30pm - 6:00pm at North Court. "
                "Fee: HK$2,400 for 12 classes."
            ),
        },
    ]


def _compact_sheet() -> dict[str, object]:
    return {
        "locations": [
            {
                "address": "Example Sports Centre, 12 Sample Road, Hong Kong",
                "area_name": "Hong Kong",
                "confidence": 0.9,
                "url": _VENUE,
                "quote": "Example Sports Centre, 12 Sample Road",
            },
            {
                "address": "Demo Hall, 3/F, 8 Fictional Street, Hong Kong",
                "confidence": 0.9,
                "url": _VENUE,
                "quote": "Demo Hall, 3/F, 8 Fictional Street",
            },
        ],
        "activities": [
            {
                "name": "Junior Skills Class",
                "age_min": 6,
                "age_max": 12,
                "confidence": 0.85,
                "url": _TERM,
                "quote": "Junior Skills Class Wednesdays",
            }
        ],
        "pricing": [
            {
                "activity_name": "Junior Skills Class",
                "pricing_type": "per_sessions",
                "amount": "2400",
                "currency": "HKD",
                "confidence": 0.85,
                "url": _TERM,
                "quote": "Fee: HK$2,400 for 12 classes",
            }
        ],
        "schedules": [
            {
                "activity_name": "Junior Skills Class",
                "location_address": "Example Sports Centre, 12 Sample Road",
                "url": _TERM,
                "quote": "Wednesdays 4:30pm - 6:00pm",
                "entries": [
                    {"day_of_week": 3, "start_time": "16:30", "end_time": "18:00"}
                ],
            }
        ],
    }


def _sections(found: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in found:
        counts[str(item["section"])] = counts.get(str(item["section"]), 0) + 1
    return counts


def test_compact_rows_with_one_quote_each_are_kept() -> None:
    found = validate_model_sheet(_compact_sheet(), _pages(), {})
    assert _sections(found) == {
        "Locations": 2,
        "Activities": 1,
        "Pricing": 1,
        "Schedules": 1,
    }
    assert not any(item["unverified"] for item in found)


def test_reply_cut_off_mid_row_keeps_the_rows_before_it() -> None:
    text = json.dumps(_compact_sheet())
    cut = text[: text.index("Junior Skills Class Wednesdays") + 10]

    sheet, how = read_sheet(cut)

    assert how == "repaired"
    found = validate_model_sheet(sheet, _pages(), {})
    assert _sections(found) == {"Locations": 2}


def test_reply_cut_after_a_section_keeps_that_section() -> None:
    text = "```json\n" + json.dumps(_compact_sheet(), indent=2)
    cut = text[: text.index('"pricing"')]

    sheet = sheet_from_text(cut)

    assert len(sheet["locations"]) == 2
    assert len(sheet["activities"]) == 1
    assert "pricing" not in sheet


def test_whole_and_empty_replies_are_labelled() -> None:
    assert read_sheet(json.dumps({"locations": []})) == ({"locations": []}, "whole")
    assert read_sheet("I could not find anything.") == ({}, "empty")
    assert read_sheet('{"locations": [{"address": "Demo') == ({}, "empty")


def test_prompt_fits_the_token_budget_for_chinese_text() -> None:
    pages = [
        {"final_url": f"https://club.test/p{index}", "text": "籃球訓練班" * 4000}
        for index in range(6)
    ]

    prompt = prompt_pages(pages)

    assert estimated_tokens(prompt) <= 24_000
    assert prompt.count("URL: https://club.test/p") == 6


def test_english_prompt_keeps_its_character_room() -> None:
    pages = [{"final_url": "https://club.test/", "text": "Junior skills. " * 4000}]

    assert len(prompt_pages(pages)) > 55_000


def test_model_reply_log_names_the_finish_reason(monkeypatch, caplog) -> None:
    from app.services.enrichment import run as run_module

    full = json.dumps(_compact_sheet())
    content = full[: full.index("Demo Hall") + 4]
    body = json.dumps(
        {
            "model": "test/model",
            "choices": [{"finish_reason": "length", "message": {"content": content}}],
            "usage": {"cost": 0.001},
        }
    )
    monkeypatch.setattr(
        "app.services.openrouter_client.openrouter_chat_completion",
        lambda **_kwargs: body,
    )

    with caplog.at_level(logging.INFO, logger=run_module.logger.logger.name):
        sheet, _cost, _model = run_module._model("page text")

    assert len(sheet["locations"]) == 1
    record = next(
        r for r in caplog.records if r.getMessage() == "Enrichment model reply"
    )
    line = json.loads(StructuredLogFormatter().format(record))
    assert line["extra"]["finish_reason"] == "length"
    assert line["extra"]["sheet"] == "repaired"
    assert line["extra"]["reply_chars"] == len(content)
