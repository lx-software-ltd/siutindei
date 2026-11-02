"""Search query parameter validation."""

from __future__ import annotations

from decimal import Decimal
from typing import NamedTuple

from app.api.admin_validators import _validate_language_code
from app.exceptions import ValidationError

_VIEWS = frozenset({"card", "full"})
_MIN_QUERY_LENGTH = 2
_MAX_QUERY_LENGTH = 100


class SearchQueryValidation(NamedTuple):
    """Validated search query values that are not plain filter numbers."""

    languages: list[str]
    text_query: str | None
    view: str


def validate_search_query_params(
    *,
    age: int | None,
    day_of_week_utc: int | None,
    start_minutes_utc: int | None,
    end_minutes_utc: int | None,
    price_min: Decimal | None,
    price_max: Decimal | None,
    languages: list[str],
    limit: int,
    q: str | None = None,
    view: str | None = None,
) -> SearchQueryValidation:
    """Validate search filters against the OpenAPI contract."""

    if age is not None and age < 0:
        raise ValidationError("age must be >= 0", field="age")

    if day_of_week_utc is not None and not 0 <= day_of_week_utc <= 6:
        raise ValidationError(
            "day_of_week_utc must be between 0 and 6",
            field="day_of_week_utc",
        )

    if start_minutes_utc is not None and not 0 <= start_minutes_utc <= 1439:
        raise ValidationError(
            "start_minutes_utc must be between 0 and 1439",
            field="start_minutes_utc",
        )

    if end_minutes_utc is not None and not 0 <= end_minutes_utc <= 1439:
        raise ValidationError(
            "end_minutes_utc must be between 0 and 1439",
            field="end_minutes_utc",
        )

    if (
        start_minutes_utc is not None
        and end_minutes_utc is not None
        and start_minutes_utc >= end_minutes_utc
    ):
        raise ValidationError(
            "start_minutes_utc must be less than end_minutes_utc",
            field="start_minutes_utc",
        )

    if price_min is not None and price_min < 0:
        raise ValidationError("price_min must be >= 0", field="price_min")

    if price_max is not None and price_max < 0:
        raise ValidationError("price_max must be >= 0", field="price_max")

    if price_min is not None and price_max is not None and price_min > price_max:
        raise ValidationError(
            "price_min must be less than or equal to price_max",
            field="price_min",
        )

    if limit < 1 or limit > 200:
        raise ValidationError("limit must be between 1 and 200", field="limit")

    validated_languages: list[str] = []
    for index, language in enumerate(languages):
        code = _validate_language_code(language, f"language[{index}]")
        if code not in validated_languages:
            validated_languages.append(code)

    return SearchQueryValidation(
        languages=validated_languages,
        text_query=_validate_text_query(q),
        view=_validate_view(view),
    )


def _validate_text_query(q: str | None) -> str | None:
    if q is None:
        return None
    text = q.strip()
    if not text:
        return None
    if len(text) < _MIN_QUERY_LENGTH:
        raise ValidationError("q must be at least 2 characters", field="q")
    if len(text) > _MAX_QUERY_LENGTH:
        raise ValidationError("q must be at most 100 characters", field="q")
    return text


def _validate_view(view: str | None) -> str:
    if view is None or view == "":
        return "full"
    if view not in _VIEWS:
        raise ValidationError("view must be card or full", field="view")
    return view
