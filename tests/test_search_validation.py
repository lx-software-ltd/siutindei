"""Tests for search query parameter validation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.api.search_validation import (
    validate_listing_filters,
    validate_search_query_params,
)
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


def _listing(**kwargs):
    values = {
        "kinds": [],
        "age": None,
        "age_min": None,
        "age_max": None,
        "verified": None,
    }
    values.update(kwargs)
    return validate_listing_filters(**values)


def test_listing_filters_default_to_every_kind_and_no_age() -> None:
    result = _listing()
    assert result.kinds == ()
    assert result.age_min is None
    assert result.age_max is None
    assert result.verified is False


def test_listing_filters_split_and_dedupe_kinds() -> None:
    result = _listing(kinds=["class,camp", " place ", "class", ""])
    assert result.kinds == ("class", "camp", "place")


def test_listing_filters_reject_unknown_kind() -> None:
    with pytest.raises(ValidationError) as exc:
        _listing(kinds=["class,party"])
    assert exc.value.field == "kind"


def test_listing_filters_accept_an_age_range() -> None:
    result = _listing(age_min=6, age_max=11)
    assert (result.age_min, result.age_max) == (6, 11)
    assert _listing(age_min=12).age_max is None


@pytest.mark.parametrize(
    ("kwargs", "field"),
    [
        ({"age": 4, "age_min": 3}, "age"),
        ({"age": 4, "age_max": 5}, "age"),
        ({"age_min": -1}, "age_min"),
        ({"age_max": -1}, "age_max"),
        ({"age_min": 8, "age_max": 6}, "age_min"),
        ({"verified": "maybe"}, "verified"),
    ],
)
def test_listing_filters_reject_bad_combinations(kwargs, field) -> None:
    with pytest.raises(ValidationError) as exc:
        _listing(**kwargs)
    assert exc.value.field == field


def test_listing_filters_read_verified_flag() -> None:
    assert _listing(verified="true").verified is True
    assert _listing(verified="false").verified is False
