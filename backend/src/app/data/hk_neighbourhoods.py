"""Hong Kong neighbourhoods under the 18 districts.

Centroids place an existing location onto the nearest neighbourhood in
its current district. Ids are uuid5 so the wizard, the staging fixture,
and the migration share one identifier.
"""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass

_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

# district, English name, zh-HK, latitude, longitude
_ROWS: tuple[tuple[str, str, str, float, float], ...] = (
    ("Central and Western", "Kennedy Town", "堅尼地城", 22.2812, 114.1289),
    ("Central and Western", "Shek Tong Tsui", "石塘咀", 22.2873, 114.1358),
    ("Central and Western", "Sai Ying Pun", "西營盤", 22.2858, 114.1428),
    ("Central and Western", "Sheung Wan", "上環", 22.2864, 114.1506),
    ("Central and Western", "Central", "中環", 22.2814, 114.1580),
    ("Central and Western", "Admiralty", "金鐘", 22.2794, 114.1650),
    ("Central and Western", "Mid-Levels", "半山", 22.2828, 114.1485),
    ("Central and Western", "The Peak", "山頂", 22.2714, 114.1498),
    ("Wan Chai", "Wan Chai", "灣仔", 22.2772, 114.1728),
    ("Wan Chai", "Causeway Bay", "銅鑼灣", 22.2803, 114.1846),
    ("Wan Chai", "Happy Valley", "跑馬地", 22.2684, 114.1862),
    ("Wan Chai", "Tai Hang", "大坑", 22.2764, 114.1918),
    ("Wan Chai", "Jardine's Lookout", "渣甸山", 22.2680, 114.1955),
    ("Eastern", "North Point", "北角", 22.2914, 114.2003),
    ("Eastern", "Quarry Bay", "鰂魚涌", 22.2878, 114.2098),
    ("Eastern", "Tai Koo", "太古", 22.2846, 114.2166),
    ("Eastern", "Sai Wan Ho", "西灣河", 22.2816, 114.2224),
    ("Eastern", "Shau Kei Wan", "筲箕灣", 22.2788, 114.2292),
    ("Eastern", "Heng Fa Chuen", "杏花邨", 22.2772, 114.2396),
    ("Eastern", "Chai Wan", "柴灣", 22.2644, 114.2368),
    ("Eastern", "Siu Sai Wan", "小西灣", 22.2622, 114.2492),
    ("Southern", "Pok Fu Lam", "薄扶林", 22.2596, 114.1378),
    ("Southern", "Aberdeen", "香港仔", 22.2482, 114.1554),
    ("Southern", "Ap Lei Chau", "鴨脷洲", 22.2422, 114.1558),
    ("Southern", "Wong Chuk Hang", "黃竹坑", 22.2478, 114.1682),
    ("Southern", "Repulse Bay", "淺水灣", 22.2362, 114.1972),
    ("Southern", "Stanley", "赤柱", 22.2188, 114.2114),
    ("Southern", "Chung Hom Kok", "舂坎角", 22.2162, 114.2034),
    ("Southern", "Shek O", "石澳", 22.2314, 114.2512),
    ("Yau Tsim Mong", "Tsim Sha Tsui", "尖沙咀", 22.2980, 114.1722),
    ("Yau Tsim Mong", "Jordan", "佐敦", 22.3048, 114.1716),
    ("Yau Tsim Mong", "Yau Ma Tei", "油麻地", 22.3128, 114.1704),
    ("Yau Tsim Mong", "Mong Kok", "旺角", 22.3192, 114.1694),
    ("Yau Tsim Mong", "Prince Edward", "太子", 22.3246, 114.1682),
    ("Yau Tsim Mong", "Tai Kok Tsui", "大角咀", 22.3218, 114.1614),
    ("Sham Shui Po", "Sham Shui Po", "深水埗", 22.3308, 114.1622),
    ("Sham Shui Po", "Cheung Sha Wan", "長沙灣", 22.3354, 114.1564),
    ("Sham Shui Po", "Lai Chi Kok", "荔枝角", 22.3372, 114.1482),
    ("Sham Shui Po", "Mei Foo", "美孚", 22.3378, 114.1396),
    ("Sham Shui Po", "Shek Kip Mei", "石硤尾", 22.3346, 114.1688),
    ("Sham Shui Po", "Nam Cheong", "南昌", 22.3264, 114.1534),
    ("Kowloon City", "Hung Hom", "紅磡", 22.3032, 114.1822),
    ("Kowloon City", "To Kwa Wan", "土瓜灣", 22.3172, 114.1876),
    ("Kowloon City", "Ma Tau Wai", "馬頭圍", 22.3224, 114.1864),
    ("Kowloon City", "Kowloon City", "九龍城", 22.3302, 114.1912),
    ("Kowloon City", "Ho Man Tin", "何文田", 22.3164, 114.1828),
    ("Kowloon City", "Kowloon Tong", "九龍塘", 22.3368, 114.1764),
    ("Kowloon City", "Kai Tak", "啟德", 22.3284, 114.2016),
    ("Wong Tai Sin", "Wong Tai Sin", "黃大仙", 22.3418, 114.1934),
    ("Wong Tai Sin", "Diamond Hill", "鑽石山", 22.3402, 114.2018),
    ("Wong Tai Sin", "San Po Kong", "新蒲崗", 22.3362, 114.1972),
    ("Wong Tai Sin", "Lok Fu", "樂富", 22.3382, 114.1872),
    ("Wong Tai Sin", "Tsz Wan Shan", "慈雲山", 22.3492, 114.2002),
    ("Wong Tai Sin", "Choi Hung", "彩虹", 22.3348, 114.2066),
    ("Wong Tai Sin", "Ngau Chi Wan", "牛池灣", 22.3342, 114.2094),
    ("Kwun Tong", "Kowloon Bay", "九龍灣", 22.3234, 114.2134),
    ("Kwun Tong", "Ngau Tau Kok", "牛頭角", 22.3156, 114.2186),
    ("Kwun Tong", "Kwun Tong", "觀塘", 22.3126, 114.2258),
    ("Kwun Tong", "Lam Tin", "藍田", 22.3068, 114.2328),
    ("Kwun Tong", "Yau Tong", "油塘", 22.2978, 114.2372),
    ("Kwun Tong", "Sau Mau Ping", "秀茂坪", 22.3204, 114.2322),
    ("Kwun Tong", "Shun Lee", "順利", 22.3322, 114.2256),
    ("Kwai Tsing", "Kwai Hing", "葵興", 22.3632, 114.1312),
    ("Kwai Tsing", "Kwai Fong", "葵芳", 22.3568, 114.1276),
    ("Kwai Tsing", "Kwai Chung", "葵涌", 22.3684, 114.1318),
    ("Kwai Tsing", "Lai King", "荔景", 22.3484, 114.1262),
    ("Kwai Tsing", "Tsing Yi", "青衣", 22.3472, 114.1042),
    ("Tsuen Wan", "Tsuen Wan", "荃灣", 22.3708, 114.1148),
    ("Tsuen Wan", "Tsuen Wan West", "荃灣西", 22.3682, 114.1096),
    ("Tsuen Wan", "Tai Wo Hau", "大窩口", 22.3704, 114.1252),
    ("Tsuen Wan", "Sham Tseng", "深井", 22.3662, 114.0598),
    ("Tsuen Wan", "Ting Kau", "汀九", 22.3688, 114.0776),
    ("Tsuen Wan", "Ma Wan", "馬灣", 22.3492, 114.0592),
    ("Tuen Mun", "Tuen Mun Town Centre", "屯門市中心", 22.3924, 113.9772),
    ("Tuen Mun", "Tuen Mun San Hui", "屯門新墟", 22.3972, 113.9764),
    ("Tuen Mun", "Siu Hong", "兆康", 22.4118, 113.9782),
    ("Tuen Mun", "Butterfly", "蝴蝶", 22.3748, 113.9624),
    ("Tuen Mun", "So Kwun Wat", "掃管笏", 22.3752, 114.0002),
    ("Tuen Mun", "Tai Lam", "大欖", 22.3654, 114.0102),
    ("Tuen Mun", "Lam Tei", "藍地", 22.4196, 113.9832),
    ("Yuen Long", "Yuen Long Town", "元朗市", 22.4448, 114.0224),
    ("Yuen Long", "Long Ping", "朗屏", 22.4476, 114.0252),
    ("Yuen Long", "Tin Shui Wai", "天水圍", 22.4602, 114.0024),
    ("Yuen Long", "Hung Shui Kiu", "洪水橋", 22.4302, 113.9982),
    ("Yuen Long", "Kam Tin", "錦田", 22.4402, 114.0652),
    ("Yuen Long", "Pat Heung", "八鄉", 22.4304, 114.0802),
    ("Yuen Long", "Lau Fau Shan", "流浮山", 22.4682, 113.9842),
    ("Yuen Long", "San Tin", "新田", 22.5002, 114.0702),
    ("North", "Sheung Shui", "上水", 22.5012, 114.1282),
    ("North", "Fanling", "粉嶺", 22.4922, 114.1402),
    ("North", "Luen Wo Hui", "聯和墟", 22.4982, 114.1432),
    ("North", "Kwu Tung", "古洞", 22.5052, 114.1002),
    ("North", "Ta Kwu Ling", "打鼓嶺", 22.5402, 114.1602),
    ("North", "Sha Tau Kok", "沙頭角", 22.5472, 114.2232),
    ("Tai Po", "Tai Po Market", "大埔墟", 22.4508, 114.1692),
    ("Tai Po", "Tai Po Centre", "大埔中心", 22.4518, 114.1648),
    ("Tai Po", "Tai Wo", "太和", 22.4506, 114.1612),
    ("Tai Po", "Lam Tsuen", "林村", 22.4562, 114.1402),
    ("Tai Po", "Tai Mei Tuk", "大美督", 22.4722, 114.2322),
    ("Tai Po", "Shuen Wan", "船灣", 22.4602, 114.1982),
    ("Sha Tin", "Tai Wai", "大圍", 22.3728, 114.1788),
    ("Sha Tin", "Hin Keng", "顯徑", 22.3642, 114.1712),
    ("Sha Tin", "Sha Tin Town Centre", "沙田市中心", 22.3818, 114.1882),
    ("Sha Tin", "Fo Tan", "火炭", 22.3952, 114.1982),
    ("Sha Tin", "Tai Shui Hang", "大水坑", 22.4082, 114.2232),
    ("Sha Tin", "Ma On Shan", "馬鞍山", 22.4242, 114.2322),
    ("Sha Tin", "Wu Kai Sha", "烏溪沙", 22.4292, 114.2436),
    ("Sha Tin", "Che Kung Temple", "車公廟", 22.3748, 114.1856),
    ("Sai Kung", "Tseung Kwan O", "將軍澳", 22.3118, 114.2598),
    ("Sai Kung", "Hang Hau", "坑口", 22.3154, 114.2646),
    ("Sai Kung", "Po Lam", "寶琳", 22.3226, 114.2572),
    ("Sai Kung", "LOHAS Park", "康城", 22.2952, 114.2712),
    ("Sai Kung", "Sai Kung Town", "西貢市", 22.3816, 114.2726),
    ("Sai Kung", "Clear Water Bay", "清水灣", 22.2802, 114.2902),
    ("Sai Kung", "Pak Tam Chung", "北潭涌", 22.3952, 114.3222),
    ("Islands", "Tung Chung", "東涌", 22.2892, 113.9418),
    ("Islands", "Discovery Bay", "愉景灣", 22.2962, 114.0152),
    ("Islands", "Mui Wo", "梅窩", 22.2642, 114.0002),
    ("Islands", "Pui O", "貝澳", 22.2402, 113.9752),
    ("Islands", "Tai O", "大澳", 22.2538, 113.8632),
    ("Islands", "Cheung Chau", "長洲", 22.2088, 114.0288),
    ("Islands", "Peng Chau", "坪洲", 22.2858, 114.0386),
    ("Islands", "Lamma Island", "南丫島", 22.2102, 114.1198),
)

DISTRICT_REGION_ID: dict[str, str] = {
    "Central and Western": "hong_kong_island",
    "Eastern": "hong_kong_island",
    "Southern": "hong_kong_island",
    "Wan Chai": "hong_kong_island",
    "Kowloon City": "kowloon",
    "Kwun Tong": "kowloon",
    "Sham Shui Po": "kowloon",
    "Wong Tai Sin": "kowloon",
    "Yau Tsim Mong": "kowloon",
    "Kwai Tsing": "new_territories",
    "North": "new_territories",
    "Sai Kung": "new_territories",
    "Sha Tin": "new_territories",
    "Tai Po": "new_territories",
    "Tsuen Wan": "new_territories",
    "Tuen Mun": "new_territories",
    "Yuen Long": "new_territories",
    "Islands": "islands",
}

HK_DISTRICTS: tuple[str, ...] = tuple(DISTRICT_REGION_ID)

# Official Traditional Chinese district names. District rows created before
# neighbourhoods stored an empty translation map.
DISTRICT_NAME_ZH: dict[str, str] = {
    "Central and Western": "中西區",
    "Eastern": "東區",
    "Southern": "南區",
    "Wan Chai": "灣仔區",
    "Kowloon City": "九龍城區",
    "Kwun Tong": "觀塘區",
    "Sham Shui Po": "深水埗區",
    "Wong Tai Sin": "黃大仙區",
    "Yau Tsim Mong": "油尖旺區",
    "Kwai Tsing": "葵青區",
    "North": "北區",
    "Sai Kung": "西貢區",
    "Sha Tin": "沙田區",
    "Tai Po": "大埔區",
    "Tsuen Wan": "荃灣區",
    "Tuen Mun": "屯門區",
    "Yuen Long": "元朗區",
    "Islands": "離島區",
}

HK_COUNTRY_NAME_ZH = "香港"

# A pin farther than this from every neighbourhood centroid is still stored
# on the nearest one, and the caller records that the snap needs review.
CONFIDENT_RADIUS_KM = 5.0


def neighbourhood_uuid(district: str, name: str) -> uuid.UUID:
    """Stable id shared by the migration, wizard, and staging fixture."""
    return uuid.uuid5(_NAMESPACE, f"siutindei.hk.neighbourhood.{district}.{name}")


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


@dataclass(frozen=True)
class Neighbourhood:
    """One neighbourhood under a Hong Kong district."""

    district: str
    name: str
    name_zh: str
    lat: float
    lng: float
    display_order: int

    @property
    def id(self) -> uuid.UUID:
        return neighbourhood_uuid(self.district, self.name)

    @property
    def region_id(self) -> str:
        return DISTRICT_REGION_ID[self.district]

    @property
    def wizard_id(self) -> str:
        return f"{_slug(self.district)}-{_slug(self.name)}"


def _build() -> tuple[Neighbourhood, ...]:
    order: dict[str, int] = {}
    built: list[Neighbourhood] = []
    for district, name, name_zh, lat, lng in _ROWS:
        order[district] = order.get(district, 0) + 1
        built.append(
            Neighbourhood(
                district=district,
                name=name,
                name_zh=name_zh,
                lat=lat,
                lng=lng,
                display_order=order[district],
            )
        )
    return tuple(built)


NEIGHBOURHOODS: tuple[Neighbourhood, ...] = _build()


def neighbourhoods_for(district: str) -> tuple[Neighbourhood, ...]:
    """Neighbourhoods of one district, in display order."""
    return tuple(item for item in NEIGHBOURHOODS if item.district == district)


def distance_km(lat: float, lng: float, other_lat: float, other_lng: float) -> float:
    """Kilometres between two WGS84 points, with longitude scaled by latitude."""
    mid = math.radians((lat + other_lat) / 2.0)
    north = (lat - other_lat) * 110.574
    east = (lng - other_lng) * 111.320 * math.cos(mid)
    return math.hypot(north, east)


@dataclass(frozen=True)
class NeighbourhoodAssignment:
    """Nearest neighbourhood and whether the pin is close enough to trust."""

    neighbourhood: Neighbourhood
    distance_km: float | None
    confident: bool


def assign_in_district(
    district: str,
    lat: float | None,
    lng: float | None,
) -> NeighbourhoodAssignment | None:
    """Closest neighbourhood. Unpinned or far pins are not confident."""
    return assign_among(neighbourhoods_for(district), lat, lng)


def assign_among(
    choices: tuple[Neighbourhood, ...] | list[Neighbourhood],
    lat: float | None,
    lng: float | None,
) -> NeighbourhoodAssignment | None:
    """Closest entry. Missing coordinates use display order and are not confident."""
    if not choices:
        return None
    ordered = tuple(choices)
    if lat is None or lng is None:
        return NeighbourhoodAssignment(ordered[0], None, False)
    nearest = min(
        ordered,
        key=lambda item: distance_km(item.lat, item.lng, lat, lng),
    )
    kilometres = distance_km(nearest.lat, nearest.lng, lat, lng)
    return NeighbourhoodAssignment(
        nearest,
        kilometres,
        kilometres <= CONFIDENT_RADIUS_KM,
    )


def nearest_in_district(
    district: str,
    lat: float | None,
    lng: float | None,
) -> Neighbourhood | None:
    """Closest neighbourhood in this district, or the first when unpinned."""
    assigned = assign_in_district(district, lat, lng)
    if assigned is None:
        return None
    return assigned.neighbourhood
