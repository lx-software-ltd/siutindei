"""Website enrichment: crawl guards, proposals, and apply."""

from __future__ import annotations

import socket
from decimal import Decimal
from urllib.parse import urlparse

import pytest
from app.db.models import Organization
from app.db.models.org_enrichment import OrgEnrichmentProposal, OrgEnrichmentRun
from app.exceptions import AppError
from app.services.aws_proxy import proxy_handler
from app.services.enrichment.apply import apply_proposals
from app.services.enrichment.extract import (
    proposals_from_pages,
    validate_model_sheet,
)
from app.services.enrichment.fetch import FetchResult, _follow, crawl_site
from app.services.enrichment.guard import (
    CrawlError,
    host_is_blocked,
    same_site,
)
from app.services.enrichment.parse import parse_html
from app.services.enrichment.run import process_enrichment
from app.services.enrichment.store import start_run


def _infos(ip: str):
    def _resolve(host, port, *args, **kwargs):
        del host, port, args, kwargs
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]

    return _resolve


def test_private_hosts_are_blocked() -> None:
    assert host_is_blocked("loop.test", resolve=_infos("127.0.0.1"))
    assert host_is_blocked("lan.test", resolve=_infos("10.1.2.3"))
    assert host_is_blocked("cgnat.test", resolve=_infos("100.64.1.1"))
    assert host_is_blocked("127.0.0.1")
    assert not host_is_blocked("public.test", resolve=_infos("1.1.1.1"))


def test_redirect_to_a_private_host_is_not_fetched(monkeypatch) -> None:
    def _check(url: str, *, resolve=None) -> None:
        del resolve
        host = (urlparse(url).hostname or "").lower()
        try:
            __import__("ipaddress").ip_address(host)
        except ValueError:
            return
        if host_is_blocked(host):
            raise CrawlError("refusing private or disallowed host")

    monkeypatch.setattr("app.services.enrichment.fetch.check_fetch_url", _check)

    def fetch_one(url: str, max_bytes: int) -> FetchResult:
        del max_bytes
        if "127.0.0.1" in url:
            raise AssertionError(url)
        return FetchResult(302, url, "text/html", b"", "http://127.0.0.1/secret")

    with pytest.raises(CrawlError):
        _follow("https://ok.test/start", fetch_one=fetch_one, max_bytes=1000)


def test_same_site_uses_the_registrable_domain() -> None:
    assert same_site("www.example.com", "example.com")
    assert same_site("shop.example.com", "example.com")
    assert same_site("www.school.edu.hk", "school.edu.hk")
    assert not same_site("a.com.hk", "b.com.hk")
    assert not same_site("example.com", "example.org")


def test_robots_disallow_stops_the_crawl(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.enrichment.fetch.check_fetch_url",
        lambda url, resolve=None: None,
    )

    def fetch_one(url: str, max_bytes: int) -> FetchResult:
        del max_bytes
        if url.endswith("/robots.txt"):
            return FetchResult(
                200,
                url,
                "text/plain",
                b"User-agent: *\nDisallow: /\n",
                "",
            )
        raise AssertionError(url)

    crawled = crawl_site(
        "https://ok.test/",
        fetch_one=fetch_one,
        sleep=lambda _seconds: None,
        now=lambda: 0,
    )
    assert crawled["status"] == "failed"
    assert "robots" in str(crawled["error"])


def test_page_cap(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.enrichment.fetch.check_fetch_url",
        lambda url, resolve=None: None,
    )
    body = (
        "<html><body>"
        + ("Class " * 80)
        + "<a href='https://ok.test/a'>a</a>"
        + "<a href='https://ok.test/b'>b</a>"
        + "<a href='https://ok.test/c'>c</a>"
        + "</body></html>"
    ).encode()

    def fetch_one(url: str, max_bytes: int) -> FetchResult:
        del max_bytes
        if url.endswith("/robots.txt"):
            return FetchResult(404, url, "text/plain", b"", "")
        return FetchResult(200, url, "text/html", body, "")

    crawled = crawl_site(
        "https://ok.test/",
        max_pages=2,
        fetch_one=fetch_one,
        sleep=lambda _seconds: None,
        now=lambda: 0,
    )
    assert crawled["pages_fetched"] == 2


def test_jsonld_and_phone_become_proposals() -> None:
    html = """
    <html lang="en"><head>
      <meta property="og:description" content="Saturday art classes for children in Kowloon.">
      <script type="application/ld+json">
        {"email":"hello@example.com","telephone":"+85221234567"}
      </script>
    </head><body><p>Saturday art classes.</p></body></html>
    """
    page = parse_html("https://ok.test/", html)
    page["final_url"] = "https://ok.test/"
    found = proposals_from_pages([page], {})
    fields = {item["field"]: item for item in found}
    assert "description" in fields
    assert fields["email"]["proposed"]["email"] == "hello@example.com"
    assert fields["phone"]["proposed"]["phone_country_code"] == "HK"
    assert fields["phone"]["proposed"]["phone_number"] == "21234567"


def test_unsupported_quote_is_downgraded() -> None:
    pages = [
        {
            "final_url": "https://ok.test/",
            "url": "https://ok.test/",
            "text": "Saturday art classes for children in the hall.",
            "jsonld_raw": [],
            "og": {},
        }
    ]
    sheet = {
        "organization": {
            "description": {
                "value": "A description that was not on the page.",
                "confidence": 0.9,
                "evidence": [
                    {
                        "url": "https://ok.test/",
                        "quote": "this sentence was not fetched",
                    }
                ],
            }
        }
    }
    found = validate_model_sheet(sheet, pages, {})
    assert found[0]["unverified"] is True
    assert found[0]["confidence"] <= 0.5


def test_proxy_routes_crawl(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.enrichment.proxy_crawl.handle_crawl_event",
        lambda event: {"result": {"status": "ok"}},
    )
    body = proxy_handler({"type": "crawl", "op": "site"}, None)
    assert body["result"]["status"] == "ok"


def _org(session, **fields) -> Organization:
    org = Organization(name="North Club", manager_id="mgr-1", **fields)
    session.add(org)
    session.flush()
    return org


def test_start_run_requires_a_website(db_session) -> None:
    org = _org(db_session)
    with pytest.raises(AppError) as exc:
        start_run(db_session, org.id, requested_by="admin")
    assert exc.value.status_code == 422


def test_start_run_refuses_a_spent_budget(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.enrichment.guard.host_is_blocked",
        lambda host, resolve=None: False,
    )
    org = _org(db_session, website="https://ok.test")
    spent = OrgEnrichmentRun(
        org_id=org.id,
        status="ready",
        seed_url="https://ok.test/",
        cost_usd=Decimal(25),
    )
    db_session.add(spent)
    db_session.flush()
    with pytest.raises(AppError) as exc:
        start_run(db_session, org.id, requested_by="admin")
    assert exc.value.status_code == 422


def test_apply_description(db_session) -> None:
    org = _org(db_session, website="https://ok.test")
    run = OrgEnrichmentRun(org_id=org.id, status="ready", seed_url="https://ok.test/")
    db_session.add(run)
    db_session.flush()
    proposal = OrgEnrichmentProposal(
        run_id=run.id,
        org_id=org.id,
        section="Organization",
        kind="update_organization",
        field="description",
        label="Description",
        current_value=None,
        proposed_value={"description": "Saturday art class for children."},
        confidence=Decimal("0.900"),
        evidence=[],
        proposed_hash="hash-1",
    )
    db_session.add(proposal)
    db_session.flush()
    results = apply_proposals(
        db_session,
        org.id,
        [str(proposal.id)],
        {},
        user_id="admin",
        request_id="req-1",
    )
    assert results == [{"id": str(proposal.id), "status": "applied"}]
    assert org.description == "Saturday art class for children."


def test_apply_refuses_a_stale_field(db_session) -> None:
    org = _org(db_session, description="Kept by an editor")
    run = OrgEnrichmentRun(org_id=org.id, status="ready", seed_url="https://ok.test/")
    db_session.add(run)
    db_session.flush()
    proposal = OrgEnrichmentProposal(
        run_id=run.id,
        org_id=org.id,
        section="Organization",
        kind="update_organization",
        field="description",
        label="Description",
        current_value={"description": "old"},
        proposed_value={"description": "Saturday art class for children."},
        confidence=Decimal("0.900"),
        evidence=[],
        proposed_hash="hash-2",
    )
    db_session.add(proposal)
    db_session.flush()
    results = apply_proposals(
        db_session,
        org.id,
        [str(proposal.id)],
        {},
        user_id="admin",
        request_id="req-2",
    )
    assert results[0]["status"] == "error"
    assert org.description == "Kept by an editor"


def test_approved_org_refuses_an_unknown_category(db_session) -> None:
    org = _org(db_session, review_status="approved")
    run = OrgEnrichmentRun(org_id=org.id, status="ready", seed_url="https://ok.test/")
    db_session.add(run)
    db_session.flush()
    proposal = OrgEnrichmentProposal(
        run_id=run.id,
        org_id=org.id,
        section="Activities",
        kind="create_activity",
        label="Activity · Painting",
        proposed_value={
            "name": "Painting",
            "category_name": "Not a real category",
            "age_min": 5,
            "age_max": 8,
        },
        confidence=Decimal("0.800"),
        evidence=[],
        proposed_hash="hash-3",
    )
    db_session.add(proposal)
    db_session.flush()
    results = apply_proposals(
        db_session,
        org.id,
        [str(proposal.id)],
        {},
        user_id="admin",
        request_id="req-3",
    )
    assert results[0]["status"] == "error"
    assert "category" in results[0]["error"]


def test_processed_message_is_not_crawled_twice(db_session, monkeypatch) -> None:
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "app.services.enrichment.run.enqueue_enrichment",
        lambda run_id, *, stage: sent.append((str(run_id), stage)),
    )
    org = _org(db_session)
    run = OrgEnrichmentRun(org_id=org.id, status="queued", seed_url="https://ok.test/")
    db_session.add(run)
    db_session.flush()
    page = {
        "url": "https://ok.test/",
        "final_url": "https://ok.test/",
        "text": "x" * 300,
        "jsonld": [],
        "jsonld_raw": [],
        "og": {},
        "links": [],
        "images": [],
        "social": [],
        "mailtos": [],
        "tels": [],
    }

    def crawl(row, settings):
        del row, settings
        return {
            "status": "ok",
            "pages": [page],
            "pages_fetched": 1,
            "bytes_fetched": 10,
            "error": "",
        }

    assert process_enrichment(
        db_session,
        run.id,
        "m1",
        receive_count=1,
        stage="crawl",
        crawl=crawl,
    )
    assert sent == [(str(run.id), "extract")]
    assert process_enrichment(
        db_session,
        run.id,
        "m1",
        receive_count=2,
        stage="crawl",
        crawl=crawl,
    )
    assert sent == [(str(run.id), "extract")]
