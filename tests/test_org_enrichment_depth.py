"""Website enrichment: which pages are read, and which model rows survive."""

from __future__ import annotations

from app.services.enrichment.extract import validate_model_sheet
from app.services.enrichment.fetch import FetchResult, crawl_site
from app.services.enrichment.parse import link_score, parse_html, url_key
from app.services.enrichment.prompt import prompt_pages
from app.services.enrichment.sheet import sheet_from_text

_MENU = "Home About Programs Venues Gallery Contact "

_VENUE_TEXT = (
    "VENUE LOCATIONS North Court (NC) Example Sports Centre, 12 Sample Road, "
    "Hong Kong Get directions South Court (SC) Demo Hall, 3/F, 8 Fictional "
    "Street, Hong Kong Get directions"
)
_TERM_TEXT = (
    "Fall Term Skills Training for ages 6-12. Junior Skills Class "
    "Wednesdays 4:30pm - 6:00pm at North Court. Fee: HK$2,400 for 12 classes."
)


def _pages() -> list[dict[str, object]]:
    return [
        {
            "url": "https://www.club.test/venue-locations",
            "final_url": "https://club.test/venue-locations",
            "text": _VENUE_TEXT,
            "jsonld_raw": [],
            "og": {},
        },
        {
            "url": "https://club.test/fall-term",
            "final_url": "https://club.test/fall-term",
            "text": _TERM_TEXT,
            "jsonld_raw": [],
            "og": {},
        },
    ]


def _by_section(found: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    sections: dict[str, list[dict[str, object]]] = {}
    for item in found:
        sections.setdefault(str(item["section"]), []).append(item)
    return sections


def test_rows_with_evidence_on_the_row_are_kept() -> None:
    venue = "https://club.test/venue-locations"
    term = "https://club.test/fall-term"
    sheet = {
        "locations": [
            {
                "address": "Example Sports Centre, 12 Sample Road, Hong Kong",
                "area_name": "Hong Kong",
                "confidence": 0.9,
                "evidence": [
                    {"url": venue, "quote": "Example Sports Centre, 12 Sample Road"}
                ],
            },
            {
                "value": {"address": "Demo Hall, 3/F, 8 Fictional Street"},
                "confidence": 0.8,
                "evidence": [{"url": venue, "quote": "Demo Hall, 3/F, 8 Fictional"}],
            },
        ],
        "activities": [
            {
                "name": "Junior Skills Class",
                "age_min": 6,
                "age_max": 12,
                "evidence": [{"url": term, "quote": "Junior Skills Class"}],
            }
        ],
        "pricing": [
            {
                "activity_name": "Junior Skills Class",
                "pricing_type": "per_sessions",
                "amount": "2400",
                "currency": "HKD",
                "confidence": 0.85,
                "evidence": [{"url": term, "quote": "Fee: HK$2,400 for 12 classes"}],
            }
        ],
        "schedules": [
            {
                "activity_name": "Junior Skills Class",
                "location_address": "Example Sports Centre, 12 Sample Road",
                "confidence": 0.8,
                "evidence": [{"url": term, "quote": "Wednesdays 4:30pm - 6:00pm"}],
                "entries": [
                    {
                        "day_of_week": "Wednesday",
                        "start_time": "4:30pm",
                        "end_time": "6:00 PM",
                    }
                ],
            }
        ],
    }
    sections = _by_section(validate_model_sheet(sheet, _pages(), {}))
    addresses = [row["proposed"]["address"] for row in sections["Locations"]]
    assert addresses == [
        "Example Sports Centre, 12 Sample Road, Hong Kong",
        "Demo Hall, 3/F, 8 Fictional Street",
    ]
    assert all(not row["unverified"] for row in sections["Locations"])
    activity = sections["Activities"][0]
    assert activity["proposed"]["age_min"] == 6
    assert activity["confidence"] >= 0.5
    assert sections["Pricing"][0]["proposed"]["amount"] == "2400"
    schedule = sections["Schedules"][0]["proposed"]
    assert schedule["entries"] == [
        {"day_of_week": 3, "start_time": "16:30", "end_time": "18:00"}
    ]


def test_quote_matches_across_spacing_case_and_url_form() -> None:
    sheet = {
        "locations": [
            {
                "address": {
                    "value": "12 Sample Road",
                    "confidence": 0.9,
                    "evidence": [
                        {
                            "url": "http://www.club.test/venue-locations/",
                            "quote": "example  sports centre,\n12 sample road",
                        }
                    ],
                }
            }
        ]
    }
    found = validate_model_sheet(sheet, _pages(), {})
    assert found[0]["unverified"] is False
    assert found[0]["evidence"][0]["url"] == "https://club.test/venue-locations"


def test_quote_from_another_fetched_page_is_attributed_to_it() -> None:
    sheet = {
        "activities": [
            {
                "name": "Junior Skills Class",
                "evidence": [
                    {"url": "https://club.test/", "quote": "Junior Skills Class"}
                ],
            }
        ]
    }
    found = validate_model_sheet(sheet, _pages(), {})
    assert found[0]["unverified"] is False
    assert found[0]["evidence"][0]["url"] == "https://club.test/fall-term"


def test_rows_without_any_quote_are_still_dropped() -> None:
    sheet = {"locations": [{"address": "Nowhere Lane"}], "activities": "Basketball"}
    assert validate_model_sheet(sheet, _pages(), {}) == []


def test_json_after_prose_is_read() -> None:
    text = 'Here is the sheet:\n{"locations": [], "activities": []}\nDone.'
    assert sheet_from_text(text) == {"locations": [], "activities": []}
    assert sheet_from_text("no json here") == {}


def test_nav_text_is_dropped_but_its_links_are_kept() -> None:
    page = parse_html(
        "https://club.test/",
        "<html><body><nav><a href='/programs'>Offered Programs</a>"
        "<a href='/gallery'>Photo Gallery</a></nav>"
        "<main><p>Training for boys and girls aged 6 to 12.</p></main></body></html>",
    )
    assert "Offered Programs" not in str(page["text"])
    assert "Training for boys and girls" in str(page["text"])
    hrefs = [link["href"] for link in page["links"]]  # type: ignore[index]
    assert hrefs == ["https://club.test/programs", "https://club.test/gallery"]


def test_links_to_programs_outrank_gallery_and_booking() -> None:
    useful = [
        ("https://club.test/2026-fall-term", "2026 Fall Term"),
        ("https://club.test/venue-locations", "Venue Locations"),
        ("https://club.test/girls-program", "Girls Program"),
        ("https://club.test/u9-u10-club-team", "U9-U10 Club Team"),
        ("https://club.test/special-clinics", "Special Clinics"),
    ]
    noise = [
        ("https://club.test/photo-gallery", "Photo Gallery"),
        ("https://club.test/makeup-class-booking", "Makeup Class Booking"),
        ("https://club.test/shop/cart", "Cart"),
        ("https://club.test/privacy-policy", "Privacy Policy"),
    ]
    lowest_useful = min(link_score(href, text) for href, text in useful)
    highest_noise = max(link_score(href, text) for href, text in noise)
    assert lowest_useful > highest_noise


def test_other_language_copy_ranks_below_the_page() -> None:
    seed = "https://club.test/"
    assert link_score("https://club.test/zh_HK/contact-us", "", seed) < link_score(
        "https://club.test/contact-us", "", seed
    )


def test_linked_pdf_outranks_plain_menu_pages() -> None:
    seed = "https://club.test/stanley"
    pdf = link_score("https://club.test/s/stanley2027.pdf", "Download", seed)
    assert pdf > link_score("https://club.test/contact-us", "Contact Us", seed)
    assert pdf > link_score("https://club.test/redhill", "Stanley Sports Centre", seed)
    assert link_score("https://club.test/s/privacy.pdf", "Download", seed) < 0


def test_url_key_ignores_www_slash_fragment_and_scheme() -> None:
    assert url_key("https://www.club.test/") == url_key("http://club.test")
    assert url_key("https://club.test/a/#top") == url_key("https://club.test/a")
    assert url_key("https://club.test/a?x=1") != url_key("https://club.test/a")


def _site(pages: dict[str, str]):
    calls: list[str] = []

    def fetch_one(url: str, max_bytes: int) -> FetchResult:
        del max_bytes
        calls.append(url)
        if url.endswith("/robots.txt"):
            return FetchResult(404, url, "text/plain", b"", "")
        path = "/" + url.split("club.test", 1)[1].lstrip("/")
        body = pages.get(path.rstrip("/") or "/", "")
        return FetchResult(200 if body else 404, url, "text/html", body.encode(), "")

    return fetch_one, calls


def test_crawl_spends_its_pages_on_term_venue_and_program_pages(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.enrichment.fetch.check_fetch_url", lambda url: None
    )
    nav = (
        "<nav><a href='https://www.club.test'>Home</a>"
        "<a href='/photo-gallery'>Photo Gallery</a>"
        "<a href='/makeup-class-booking'>Makeup Class Booking</a>"
        "<a href='/zh_HK/'>中文</a>"
        "<a href='/2026-fall-term'>2026 Fall Term</a>"
        "<a href='/venue-locations'>Venue Locations</a>"
        "<a href='/girls-program'>Girls Program</a></nav>"
    )
    body = "<p>" + "Youth basketball training in the city. " * 10 + "</p>"
    paths = [
        "/",
        "/photo-gallery",
        "/makeup-class-booking",
        "/zh_HK",
        "/2026-fall-term",
        "/venue-locations",
        "/girls-program",
    ]
    pages = {path: f"<html><body>{nav}{body}</body></html>" for path in paths}
    fetch_one, _calls = _site(pages)
    result = crawl_site(
        "https://www.club.test/",
        max_pages=4,
        fetch_one=fetch_one,
        sleep=lambda _seconds: None,
        now=lambda: 0,
    )
    fetched = [url_key(page["final_url"]) for page in result["pages"]]  # type: ignore[index]
    assert fetched[0] == "club.test"
    assert set(fetched[1:]) == {
        "club.test/2026-fall-term",
        "club.test/venue-locations",
        "club.test/girls-program",
    }


def test_prompt_drops_text_repeated_on_every_page() -> None:
    footer = " Copyright 2026 Example Club. Powered by a site builder."
    pages = [
        {"final_url": f"https://club.test/{name}", "text": _MENU + text + footer}
        for name, text in (
            ("", "Welcome to the club for young players and their families."),
            ("venues", _VENUE_TEXT),
            ("fall-term", _TERM_TEXT),
        )
    ]
    prompt = prompt_pages(pages)
    assert prompt.count(_MENU.strip()) == 1
    assert prompt.count("Powered by a site builder") == 1
    assert "12 Sample Road" in prompt
    assert "HK$2,400" in prompt


def test_prompt_shares_room_so_a_long_page_does_not_crowd_out_the_rest() -> None:
    pages = [
        {"final_url": "https://club.test/about", "text": "history " * 20_000},
        {"final_url": "https://club.test/fall-term", "text": _TERM_TEXT},
    ]
    prompt = prompt_pages(pages)
    assert "HK$2,400" in prompt


def _pdf(*lines: str) -> bytes:
    """A one-page PDF with one line of Helvetica text per argument."""
    text = " ".join(
        f"BT /F1 12 Tf 50 {700 - 20 * index} Td ({line}) Tj ET"
        for index, line in enumerate(lines)
    ).encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length %d >>\nstream\n" % len(text) + text + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return out


def test_pdf_text_becomes_a_page() -> None:
    from app.services.enrichment.pdf import parse_pdf

    page = parse_pdf(
        "https://club.test/timetable.pdf",
        _pdf("Junior Skills Class Wednesdays 4:30pm - 6:00pm", "Fee: HK$2,400"),
    )
    assert page is not None
    assert "Junior Skills Class Wednesdays" in str(page["text"])
    assert "HK$2,400" in str(page["text"])
    assert page["links"] == [] and page["images"] == []


def test_broken_pdf_is_skipped() -> None:
    from app.services.enrichment.pdf import parse_pdf

    assert parse_pdf("https://club.test/x.pdf", b"%PDF-1.4 not really") is None


def test_crawl_reads_a_linked_pdf_timetable(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.enrichment.fetch.check_fetch_url", lambda url: None
    )
    home = (
        "<html><body><p>"
        + "Youth basketball training in the city. " * 10
        + "</p><a href='/term-timetable.pdf'>Term Timetable</a></body></html>"
    ).encode()
    pdf = _pdf("Junior Skills Class Wednesdays 4:30pm - 6:00pm")
    sizes: dict[str, int] = {}

    def fetch_one(url: str, max_bytes: int) -> FetchResult:
        sizes[url] = max_bytes
        if url.endswith("/robots.txt"):
            return FetchResult(404, url, "text/plain", b"", "")
        if url.endswith(".pdf"):
            return FetchResult(200, url, "application/pdf", pdf, "")
        return FetchResult(200, url, "text/html", home, "")

    result = crawl_site(
        "https://club.test/",
        max_pages=4,
        max_page_bytes=50_000,
        fetch_one=fetch_one,
        sleep=lambda _seconds: None,
        now=lambda: 0,
    )
    pages = result["pages"]  # type: ignore[index]
    pdf_page = next(p for p in pages if str(p["final_url"]).endswith(".pdf"))
    assert "Wednesdays 4:30pm" in str(pdf_page["text"])
    assert sizes["https://club.test/term-timetable.pdf"] > 50_000


def test_site_pdf_served_from_a_file_host_is_read(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.enrichment.fetch.check_fetch_url", lambda url: None
    )
    home = (
        "<html><body><p>"
        + "Youth basketball training in the city. " * 10
        + "</p><a href='/s/timetable.pdf'>Download</a>"
        + "<a href='/s/brochure.pdf'>Download</a>"
        + "<a href='https://files.test/other.html'>Partner</a></body></html>"
    ).encode()
    pdf = _pdf("Junior Skills Class Wednesdays 4:30pm - 6:00pm")

    def fetch_one(url: str, max_bytes: int) -> FetchResult:
        if url.endswith("/robots.txt"):
            return FetchResult(404, url, "text/plain", b"", "")
        if url.startswith("https://club.test/s/"):
            name = url.rsplit("/", 1)[1]
            return FetchResult(302, url, "text/html", b"", f"https://files.test/{name}")
        if url == "https://files.test/timetable.pdf":
            return FetchResult(200, url, "application/pdf", pdf, "")
        if url.startswith("https://files.test/"):
            return FetchResult(200, url, "text/html", home, "")
        return FetchResult(200, url, "text/html", home, "")

    result = crawl_site(
        "https://club.test/",
        max_pages=4,
        fetch_one=fetch_one,
        sleep=lambda _seconds: None,
        now=lambda: 0,
    )
    urls = [str(p["final_url"]) for p in result["pages"]]  # type: ignore[index]
    assert "https://files.test/timetable.pdf" in urls
    assert "https://files.test/brochure.pdf" not in urls
    assert "https://files.test/other.html" not in urls


def test_settings_allow_twenty_pages(db_session) -> None:
    import pytest
    from app.exceptions import ValidationError
    from app.services.enrichment.store import load_settings, update_settings

    assert load_settings(db_session).max_pages == 12
    assert update_settings(db_session, {"max_pages": 20}).max_pages == 20
    with pytest.raises(ValidationError):
        update_settings(db_session, {"max_pages": 21})
