"""Approximate boxes for the 18 Hong Kong districts.

A pin is outside its district when it falls in a different district's
box, or outside Hong Kong entirely. Gaps between boxes are not flagged.
"""

from __future__ import annotations

from app.db.models import GeographicArea

# south, north, west, east
_Box = tuple[float, float, float, float]

_BOXES: dict[str, _Box] = {
    "central-and-western": (22.268, 22.296, 114.122, 114.164),
    "wan-chai": (22.268, 22.288, 114.164, 114.210),
    "eastern": (22.268, 22.298, 114.200, 114.255),
    "southern": (22.205, 22.268, 114.115, 114.255),
    "yau-tsim-mong": (22.293, 22.322, 114.158, 114.182),
    "sham-shui-po": (22.322, 22.348, 114.130, 114.175),
    "kowloon-city": (22.308, 22.348, 114.175, 114.210),
    "wong-tai-sin": (22.332, 22.358, 114.180, 114.220),
    "kwun-tong": (22.292, 22.338, 114.208, 114.250),
    "kwai-tsing": (22.340, 22.378, 114.095, 114.148),
    "tsuen-wan": (22.355, 22.405, 114.065, 114.155),
    "tuen-mun": (22.365, 22.435, 113.910, 114.005),
    "yuen-long": (22.415, 22.535, 113.960, 114.105),
    "north": (22.485, 22.565, 114.075, 114.235),
    "tai-po": (22.415, 22.515, 114.135, 114.285),
    "sha-tin": (22.355, 22.435, 114.165, 114.255),
    "sai-kung": (22.295, 22.485, 114.245, 114.430),
    "islands": (22.180, 22.340, 113.820, 114.060),
}

_HONG_KONG: _Box = (22.14, 22.58, 113.80, 114.45)

_ALIASES = {
    "central and western": "central-and-western",
    "中西區": "central-and-western",
    "wan chai": "wan-chai",
    "灣仔": "wan-chai",
    "eastern": "eastern",
    "東區": "eastern",
    "southern": "southern",
    "南區": "southern",
    "yau tsim mong": "yau-tsim-mong",
    "油尖旺": "yau-tsim-mong",
    "sham shui po": "sham-shui-po",
    "深水埗": "sham-shui-po",
    "kowloon city": "kowloon-city",
    "九龍城": "kowloon-city",
    "wong tai sin": "wong-tai-sin",
    "黃大仙": "wong-tai-sin",
    "kwun tong": "kwun-tong",
    "觀塘": "kwun-tong",
    "kwai tsing": "kwai-tsing",
    "葵青": "kwai-tsing",
    "tsuen wan": "tsuen-wan",
    "荃灣": "tsuen-wan",
    "tuen mun": "tuen-mun",
    "屯門": "tuen-mun",
    "yuen long": "yuen-long",
    "元朗": "yuen-long",
    "north": "north",
    "北區": "north",
    "tai po": "tai-po",
    "大埔": "tai-po",
    "sha tin": "sha-tin",
    "沙田": "sha-tin",
    "sai kung": "sai-kung",
    "西貢": "sai-kung",
    "islands": "islands",
    "離島": "islands",
}


def district_key(areas: list[GeographicArea]) -> str | None:
    """First official district named by this area or one of its parents."""
    for area in areas:
        for label in _labels(area):
            key = _ALIASES.get(label.casefold())
            if key:
                return key
    return None


def pin_is_outside(lat: float, lng: float, key: str) -> bool:
    """True when the pin is in another district, or outside Hong Kong."""
    if key not in _BOXES:
        return False
    found = _containing(lat, lng)
    if key in found:
        return False
    if found:
        return True
    south, north, west, east = _HONG_KONG
    return not (south <= lat <= north and west <= lng <= east)


def _labels(area: GeographicArea) -> list[str]:
    raw = [area.name, *(area.name_translations or {}).values()]
    return [str(value).strip() for value in raw if str(value or "").strip()]


def _containing(lat: float, lng: float) -> set[str]:
    found = set()
    for key, box in _BOXES.items():
        south, north, west, east = box
        if south <= lat <= north and west <= lng <= east:
            found.add(key)
    return found
