"""Tests for search query parameter validation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.api.search_validation import validate_search_query_params
from app.exceptions import ValidationError


def test_validate_search_rejects_negative_age() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_search_query_params(
            age=-1,
            day_of_week_utc=None,
            start_minutes_utc=None,
            end_minutes_utc=None,
            price_min=None,
            price_max=None,
            languages=[],
            limit=50,
        )
    assert exc.value.field == "age"


def test_validate_search_rejects_invalid_day_of_week() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_search_query_params(
            age=None,
            day_of_week_utc=7,
            start_minutes_utc=None,
            end_minutes_utc=None,
            price_min=None,
            price_max=None,
            languages=[],
            limit=50,
        )
    assert exc.value.field == "day_of_week_utc"


def test_validate_search_rejects_price_min_above_max() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_search_query_params(
            age=None,
            day_of_week_utc=None,
            start_minutes_utc=None,
            end_minutes_utc=None,
            price_min=Decimal("100"),
            price_max=Decimal("10"),
            languages=[],
            limit=50,
        )
    assert exc.value.field == "price_min"


def test_validate_search_rejects_invalid_language_code() -> None:
    with pytest.raises(ValidationError):
        validate_search_query_params(
            age=None,
            day_of_week_utc=None,
            start_minutes_utc=None,
            end_minutes_utc=None,
            price_min=None,
            price_max=None,
            languages=["not-a-language"],
            limit=50,
        )


def test_validate_search_rejects_limit_out_of_range() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_search_query_params(
            age=None,
            day_of_week_utc=None,
            start_minutes_utc=None,
            end_minutes_utc=None,
            price_min=None,
            price_max=None,
            languages=[],
            limit=0,
        )
    assert exc.value.field == "limit"


def test_validate_search_rejects_short_q() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_search_query_params(
            age=None,
            day_of_week_utc=None,
            start_minutes_utc=None,
            end_minutes_utc=None,
            price_min=None,
            price_max=None,
            languages=[],
            limit=50,
            q="a",
        )
    assert exc.value.field == "q"
    assert "at least 2" in str(exc.value)


def test_validate_search_blank_q_is_no_filter() -> None:
    result = validate_search_query_params(
        age=None,
        day_of_week_utc=None,
        start_minutes_utc=None,
        end_minutes_utc=None,
        price_min=None,
        price_max=None,
        languages=[],
        limit=50,
        q="  ",
    )
    assert result.text_query is None
    assert result.view == "full"


def test_validate_search_accepts_q_and_card_view() -> None:
    result = validate_search_query_params(
        age=None,
        day_of_week_utc=None,
        start_minutes_utc=None,
        end_minutes_utc=None,
        price_min=None,
        price_max=None,
        languages=[],
        limit=50,
        q="  swim ",
        view="card",
    )
    assert result.text_query == "swim"
    assert result.view == "card"


def test_validate_search_rejects_unknown_view() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_search_query_params(
            age=None,
            day_of_week_utc=None,
            start_minutes_utc=None,
            end_minutes_utc=None,
            price_min=None,
            price_max=None,
            languages=[],
            limit=50,
            view="compact",
        )
    assert exc.value.field == "view"
