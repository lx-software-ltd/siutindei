"""Shared limits and the copyright notice stored with copied media."""

from __future__ import annotations

USER_AGENT = "SiutindeiBot/1.0 (+https://siutindei.com/bot)"
COPYRIGHT_NOTICE = (
    "Copied from the provider website for this catalog. "
    "Copyright remains with the provider."
)

# Two queue messages share the 120s admin function: crawl, then extract.
CRAWL_TIME_BUDGET_SECONDS = 20
EXTRACT_TIMEOUT_SECONDS = 70
MAX_PAGE_TEXT = 8000
MAX_PROMPT_CHARS = 40_000
MAX_IMAGE_BYTES = 5_000_000
MAX_APPLY_IDS = 200
MAX_JSONLD_BLOCKS = 20
# Three 180s queue receives, plus time waiting to start.
STALE_RUN_MINUTES = 20

ORG_FIELDS = (
    "description",
    "email",
    "phone_country_code",
    "phone_number",
    "whatsapp",
    "facebook",
    "instagram",
    "tiktok",
    "twitter",
    "xiaohongshu",
    "wechat",
    "website",
)

SOCIAL_HOSTS = {
    "facebook.com": "facebook",
    "instagram.com": "instagram",
    "tiktok.com": "tiktok",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "xiaohongshu.com": "xiaohongshu",
    "youtube.com": None,
    "wa.me": "whatsapp",
    "whatsapp.com": "whatsapp",
    "linkedin.com": None,
    "linktr.ee": None,
    "t.me": None,
}

# Last labels that are a public suffix, not a registrable domain.
# Single-label TLDs use the last two labels. This list is what stops
# shop.example.com.hk and other.example.com.hk from looking like one site
# when a naive "last two labels" rule treats com.hk as the domain.
MULTI_PART_SUFFIXES = frozenset(
    {
        "com.hk",
        "org.hk",
        "edu.hk",
        "gov.hk",
        "idv.hk",
        "net.hk",
        "co.uk",
        "org.uk",
        "ac.uk",
        "gov.uk",
        "com.au",
        "net.au",
        "org.au",
        "edu.au",
        "co.jp",
        "ne.jp",
        "or.jp",
        "com.sg",
        "com.tw",
        "org.tw",
        "com.mo",
        "com.cn",
        "net.cn",
        "org.cn",
        "co.nz",
        "com.br",
        "co.za",
        "com.my",
        "co.kr",
        "com.vn",
    }
)

PAGE_KEYWORDS = (
    "about",
    "contact",
    "location",
    "class",
    "course",
    "price",
    "fee",
    "schedule",
    "timetable",
    "gallery",
    "photo",
    "關於",
    "聯絡",
    "地址",
    "分店",
    "校舍",
    "課程",
    "收費",
    "學費",
    "時間表",
    "上課",
    "相片",
)
