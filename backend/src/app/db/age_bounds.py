"""Inclusive age bounds for Postgres int4range values.

Postgres stores ``int4range(0, 18, '[]')`` as ``[0, 19)``. Callers that
show or compare an inclusive maximum must subtract one from an exclusive
upper bound.
"""

from __future__ import annotations

from typing import Any


def inclusive_age_bounds(age_range: Any) -> tuple[int | None, int | None]:
    """Return inclusive ``(age_min, age_max)`` for a range value."""
    if age_range is None:
        return None, None
    if isinstance(age_range, str):
        return _bounds_from_literal(age_range)
    lower = getattr(age_range, "lower", None)
    upper = getattr(age_range, "upper", None)
    if lower is None and upper is None:
        return None, None
    return _adjust_bounds(
        lower,
        upper,
        lower_inc=getattr(age_range, "lower_inc", True) is not False,
        upper_inc=getattr(age_range, "upper_inc", True) is not False,
    )


def _adjust_bounds(
    lower: Any,
    upper: Any,
    *,
    lower_inc: bool,
    upper_inc: bool,
) -> tuple[int | None, int | None]:
    lower_out = int(lower) if lower is not None else None
    upper_out = int(upper) if upper is not None else None
    if lower_out is not None and not lower_inc:
        lower_out += 1
    if upper_out is not None and not upper_inc:
        upper_out -= 1
    return lower_out, upper_out


def _bounds_from_literal(age_range: str) -> tuple[int | None, int | None]:
    text = age_range.strip()
    if len(text) < 3:
        return None, None
    lower_inc = text[0] == "["
    upper_inc = text[-1] == "]"
    parts = text[1:-1].split(",")
    if len(parts) != 2:
        return None, None
    try:
        lower = int(parts[0]) if parts[0].strip() else None
        upper = int(parts[1]) if parts[1].strip() else None
    except ValueError:
        return None, None
    return _adjust_bounds(
        lower,
        upper,
        lower_inc=lower_inc,
        upper_inc=upper_inc,
    )
