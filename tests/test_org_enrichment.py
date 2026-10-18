"""Website enrichment: crawl guards, proposals, and apply."""

from __future__ import annotations

import socket
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from app.db.models import Activity, ActivityPricing, ActivitySchedule, Organization
from app.db.models.audit_log import AuditLog
from app.db.models.org_enrichment import OrgEnrichmentProposal, OrgEnrichmentRun
from app.exceptions import AppError
from app.services.aws_proxy import proxy_handler
from app.services.enrichment.apply import _link_run, apply_proposals
from app.services.enrichment.extract import (
    proposals_from_pages,
    validate_model_sheet,
)
from app.services.enrichment.fetch import FetchResult, _follow, crawl_site, fetch_public
from app.services.enrichment.guard import (
    CrawlError,
    host_is_blocked,
    same_site,
)
from app.services.enrichment.match import prepare_proposals
from app.services.enrichment.parse import parse_html
from app.services.enrichment.proxy_crawl import copy_image
from app.services.enrichment.run import (
    EnrichmentStep,
    commit_and_queue,
    process_enrichment,
)
from app.services.enrichment.store import save_proposals, start_run


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
    results, _quality_run = apply_proposals(
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
    results, _quality_run = apply_proposals(
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
    results, _quality_run = apply_proposals(
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

    step = process_enrichment(
        db_session,
        run.id,
        "m1",
        receive_count=1,
        stage="crawl",
        crawl=crawl,
    )
    assert step.acked is True
    assert step.enqueue_stage == "extract"
    assert sent == []
    again = process_enrichment(
        db_session,
        run.id,
        "m1",
        receive_count=2,
        stage="crawl",
        crawl=crawl,
    )
    assert again.enqueue_stage is None
    assert sent == []


def test_extract_is_queued_only_after_commit(monkeypatch) -> None:
    order: list[str] = []

    class _Session:
        def commit(self) -> None:
            order.append("commit")

        def rollback(self) -> None:
            order.append("rollback")

    monkeypatch.setattr(
        "app.services.enrichment.run.enqueue_enrichment",
        lambda run_id, *, stage: order.append(f"enqueue:{stage}"),
    )
    commit_and_queue(
        _Session(),  # type: ignore[arg-type]
        EnrichmentStep(acked=True, run_id=uuid4(), enqueue_stage="extract"),
    )
    assert order == ["commit", "enqueue:extract"]


def test_other_subdomain_robots_are_checked(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.enrichment.fetch.check_fetch_url",
        lambda url, resolve=None: None,
    )
    fetched: list[str] = []

    def fetch_one(url: str, max_bytes: int) -> FetchResult:
        del max_bytes
        fetched.append(url)
        if url.endswith("/robots.txt"):
            if "shop.ok.test" in url:
                return FetchResult(
                    200,
                    url,
                    "text/plain",
                    b"User-agent: *\nDisallow: /\n",
                    "",
                )
            return FetchResult(404, url, "text/plain", b"", "")
        if "shop.ok.test" in url:
            raise AssertionError(url)
        body = (
            "<html><body>"
            + ("Class " * 80)
            + "<a href='https://shop.ok.test/class'>class</a>"
            + "</body></html>"
        ).encode()
        return FetchResult(200, url, "text/html", body, "")

    crawled = crawl_site(
        "https://ok.test/",
        fetch_one=fetch_one,
        sleep=lambda _seconds: None,
        now=lambda: 0,
    )
    assert crawled["pages_fetched"] == 1
    assert any("shop.ok.test/robots.txt" in url for url in fetched)


def test_jsonld_blocks_are_capped() -> None:
    blocks = "".join(
        f'<script type="application/ld+json">{{"name":"Item {index}"}}</script>'
        for index in range(25)
    )
    page = parse_html("https://ok.test/", f"<html><head>{blocks}</head></html>")
    assert len(page["jsonld_raw"]) == 20


def test_fetch_connects_to_the_checked_address(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.enrichment.fetch.public_address",
        lambda host, resolve=None: "1.1.1.1",
    )
    captured: dict[str, str] = {}

    class _Response:
        def __init__(self) -> None:
            self.status = 200
            self.headers = {"Content-Type": "text/html"}
            self.url = "https://1.1.1.1/"
            self._sent = False

        def read(self, amount: int) -> bytes:
            del amount
            if self._sent:
                return b""
            self._sent = True
            return b"hello"

        def __enter__(self):
            return self

        def __exit__(self, *args) -> bool:
            del args
            return False

    class _Opener:
        def open(self, request, timeout=None):
            del timeout
            captured["url"] = request.full_url
            captured["host"] = dict(request.header_items()).get("Host")
            return _Response()

    monkeypatch.setattr(
        "urllib.request.build_opener",
        lambda *handlers: _Opener(),
    )
    result = fetch_public("https://ok.test/page", 100)
    assert result.body == b"hello"
    assert result.truncated is False
    assert "1.1.1.1" in captured["url"]
    assert captured["host"] == "ok.test"


def test_https_uses_the_real_handler_for_the_pinned_address(monkeypatch) -> None:
    import io

    monkeypatch.setattr(
        "app.services.enrichment.fetch.public_address",
        lambda host, resolve=None: "1.1.1.1",
    )
    seen: dict[str, object] = {}
    payload = (
        b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n"
        b"Content-Length: 5\r\nConnection: close\r\n\r\nhello"
    )

    class _Sock:
        def __init__(self) -> None:
            self._buf = payload

        def sendall(self, data: bytes) -> None:
            del data

        def setsockopt(self, *args: object) -> None:
            del args

        def settimeout(self, seconds: float) -> None:
            del seconds

        def makefile(self, mode: str = "rb", *args: object, **kwargs: object):
            del mode, args, kwargs
            return io.BytesIO(self._buf)

        def close(self) -> None:
            return None

    def _connect(address, timeout=None, source_address=None):
        del timeout, source_address
        seen["address"] = address
        return _Sock()

    def _wrap(self, sock, server_hostname=None, **kwargs):
        del self, kwargs
        seen["sni"] = server_hostname
        return sock

    monkeypatch.setattr(socket, "create_connection", _connect)
    monkeypatch.setattr("ssl.SSLContext.wrap_socket", _wrap)
    result = fetch_public("https://ok.test/robots.txt", 100)
    assert seen["address"] == ("1.1.1.1", 443)
    assert seen["sni"] == "ok.test"
    assert result.body == b"hello"
    assert result.status == 200


def test_proxy_crash_fails_the_run_without_a_retry(db_session, monkeypatch) -> None:
    from app.services.aws_proxy import AwsProxyError

    monkeypatch.setattr(
        "app.services.enrichment.run.enqueue_enrichment",
        lambda run_id, *, stage: None,
    )
    org = _org(db_session, website="https://ok.test")
    run = OrgEnrichmentRun(org_id=org.id, status="queued", seed_url="https://ok.test/")
    db_session.add(run)
    db_session.flush()

    def crawl(row, settings):
        del row, settings
        raise AwsProxyError("LambdaInvocationError", "TypeError: server_hostname")

    step = process_enrichment(
        db_session,
        run.id,
        "m-crash",
        receive_count=1,
        stage="crawl",
        crawl=crawl,
    )
    assert step.acked is True
    assert step.enqueue_stage is None
    assert run.status == "failed"
    assert run.error == "The website could not be read"


def test_proxy_timeout_stays_retryable(db_session, monkeypatch) -> None:
    from app.services.aws_proxy import AwsProxyError

    monkeypatch.setattr(
        "app.services.enrichment.run.enqueue_enrichment",
        lambda run_id, *, stage: None,
    )
    org = _org(db_session, website="https://ok.test")
    run = OrgEnrichmentRun(org_id=org.id, status="queued", seed_url="https://ok.test/")
    db_session.add(run)
    db_session.flush()

    def crawl(row, settings):
        del row, settings
        raise AwsProxyError("TimeoutError", "timed out")

    step = process_enrichment(
        db_session,
        run.id,
        "m-timeout",
        receive_count=1,
        stage="crawl",
        crawl=crawl,
    )
    assert step.acked is False


def test_truncated_image_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.enrichment.proxy_crawl.check_fetch_url",
        lambda url, resolve=None: None,
    )
    monkeypatch.setattr(
        "app.services.enrichment.proxy_crawl.fetch_public",
        lambda url, max_bytes, timeout=10, deadline=None: FetchResult(
            200,
            url,
            "image/jpeg",
            b"x" * 8,
            "",
            truncated=True,
        ),
    )
    with pytest.raises(CrawlError, match="too large"):
        copy_image(
            {
                "url": "https://ok.test/a.jpg",
                "org_id": "11111111-1111-1111-1111-111111111111",
            }
        )


def _proposal(run, **fields) -> OrgEnrichmentProposal:
    row = OrgEnrichmentProposal(
        run_id=run.id,
        org_id=run.org_id,
        section=fields.pop("section", "Organization"),
        kind=fields.pop("kind", "update_organization"),
        label=fields.pop("label", "Change"),
        proposed_value=fields.pop("proposed_value"),
        confidence=Decimal("0.900"),
        evidence=[],
        proposed_hash=fields.pop("proposed_hash", uuid4().hex),
        **fields,
    )
    return row


def test_unverified_rows_respect_the_confidence_floor(db_session) -> None:
    org = _org(db_session, website="https://ok.test")
    run = OrgEnrichmentRun(org_id=org.id, status="ready", seed_url="https://ok.test/")
    db_session.add(run)
    db_session.flush()
    kept = save_proposals(
        db_session,
        run,
        [
            {
                "section": "Organization",
                "kind": "update_organization",
                "field": "email",
                "label": "Email",
                "current": None,
                "proposed": {"email": "hello@example.com"},
                "confidence": 0.2,
                "unverified": True,
                "evidence": [],
            }
        ],
        min_confidence=Decimal("0.500"),
    )
    assert kept == 0


def test_stale_run_no_longer_blocks_the_organization(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.enrichment.guard.host_is_blocked",
        lambda host, resolve=None: False,
    )
    org = _org(db_session, website="https://ok.test")
    old = OrgEnrichmentRun(
        org_id=org.id,
        status="running",
        seed_url="https://ok.test/",
        created_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(old)
    db_session.flush()
    fresh = start_run(db_session, org.id, requested_by="admin")
    assert old.status == "failed"
    assert old.error == "Enrichment timed out"
    assert fresh.status == "queued"


def test_existing_rows_are_not_proposed_again(
    db_session, sample_location, sample_activity
) -> None:
    org = sample_location.organization
    items = prepare_proposals(
        db_session,
        org,
        [
            {
                "kind": "create_location",
                "proposed": {"address": "123 Test Street"},
            },
            {
                "kind": "create_activity",
                "proposed": {"name": "Swimming Class"},
            },
        ],
    )
    assert items == []


def test_one_bad_proposal_does_not_undo_the_others(db_session) -> None:
    org = _org(db_session, website="https://ok.test")
    run = OrgEnrichmentRun(org_id=org.id, status="ready", seed_url="https://ok.test/")
    db_session.add(run)
    db_session.flush()
    good = _proposal(
        run,
        field="description",
        label="Description",
        proposed_value={"description": "Saturday art class for children."},
        proposed_hash="hash-good",
    )
    bad = _proposal(
        run,
        section="Locations",
        kind="create_location",
        label="Location",
        proposed_value={"address": "9 Example Road"},
        proposed_hash="hash-bad",
    )
    db_session.add_all([good, bad])
    db_session.flush()
    calls: list[int] = []
    results, _quality_run = apply_proposals(
        db_session,
        org.id,
        [str(bad.id), str(good.id)],
        {str(bad.id): ["not-an-object"]},  # type: ignore[dict-item]
        user_id="admin",
        request_id="req-mix",
    )
    del calls
    by_id = {row["id"]: row["status"] for row in results}
    assert by_id[str(good.id)] == "applied"
    assert by_id[str(bad.id)] == "error"
    assert org.description == "Saturday art class for children."
    audit = db_session.query(AuditLog).filter_by(action="ENRICH_APPLY").one()
    assert audit.new_values["proposal_ids"] == [str(good.id)]


def test_reason_is_marked_for_each_applied_proposal(db_session, monkeypatch) -> None:
    org = _org(db_session, website="https://ok.test")
    run = OrgEnrichmentRun(org_id=org.id, status="ready", seed_url="https://ok.test/")
    db_session.add(run)
    db_session.flush()
    first = _proposal(
        run,
        field="description",
        proposed_value={"description": "Saturday art class for children."},
        proposed_hash="hash-a",
    )
    second = _proposal(
        run,
        field="email",
        label="Email",
        proposed_value={"email": "hello@example.com"},
        proposed_hash="hash-b",
    )
    db_session.add_all([first, second])
    db_session.flush()
    calls: list[int] = []
    monkeypatch.setattr(
        "app.services.enrichment.apply._mark_reason",
        lambda session: calls.append(1),
    )
    apply_proposals(
        db_session,
        org.id,
        [str(first.id), str(second.id)],
        {},
        user_id="admin",
        request_id="req-reason",
    )
    assert calls == [1, 1]


def test_link_run_covers_child_and_media_rows() -> None:
    captured: list[str] = []

    class _Dialect:
        name = "postgresql"

    class _Bind:
        dialect = _Dialect()

    class _Session:
        def get_bind(self):
            return _Bind()

        def execute(self, statement, params=None):
            del params
            captured.append(str(statement))

    _link_run(_Session(), "run-1")  # type: ignore[arg-type]
    assert "children" in captured[0]
    assert "media" in captured[0]
    assert "enrichment" in captured[0]


def test_media_keeps_the_existing_order(db_session) -> None:
    from app.services.enrichment.store import load_settings

    org = _org(
        db_session,
        media_urls=["https://cdn.example/b.png", "https://cdn.example/a.png"],
    )
    settings = load_settings(db_session)
    settings.copy_media = False
    run = OrgEnrichmentRun(org_id=org.id, status="ready", seed_url="https://ok.test/")
    db_session.add(run)
    db_session.flush()
    proposal = _proposal(
        run,
        section="Media",
        kind="add_media",
        label="Photo",
        proposed_value={"source_url": "https://cdn.example/c.png"},
        proposed_hash="hash-media",
    )
    db_session.add(proposal)
    db_session.flush()
    results, _quality_run = apply_proposals(
        db_session,
        org.id,
        [str(proposal.id)],
        {},
        user_id="admin",
        request_id="req-media",
    )
    assert results[0]["status"] == "applied"
    assert org.media_urls == [
        "https://cdn.example/b.png",
        "https://cdn.example/a.png",
        "https://cdn.example/c.png",
    ]


def test_pricing_applies_after_its_activity(
    db_session, sample_location, sample_activity_category
) -> None:
    org = sample_location.organization
    run = OrgEnrichmentRun(org_id=org.id, status="ready", seed_url="https://ok.test/")
    db_session.add(run)
    db_session.flush()
    activity = _proposal(
        run,
        section="Activities",
        kind="create_activity",
        label="Activity · Painting",
        proposed_value={
            "name": "Painting",
            "category_name": sample_activity_category.name,
            "age_min": 5,
            "age_max": 8,
        },
        proposed_hash="hash-activity",
    )
    pricing = _proposal(
        run,
        section="Pricing",
        kind="create_pricing",
        label="Price",
        proposed_value={
            "activity_name": "Painting",
            "pricing_type": "per_class",
            "amount": "120",
            "currency": "HKD",
        },
        proposed_hash="hash-price",
    )
    db_session.add_all([activity, pricing])
    db_session.flush()
    results, _quality_run = apply_proposals(
        db_session,
        org.id,
        [str(pricing.id), str(activity.id)],
        {},
        user_id="admin",
        request_id="req-order",
    )
    assert {row["status"] for row in results} == {"applied"}
    assert (
        db_session.query(ActivityPricing)
        .join(Activity, ActivityPricing.activity_id == Activity.id)
        .filter(Activity.name == "Painting")
        .count()
        == 1
    )


def test_invalid_schedule_does_not_leave_an_empty_row(
    db_session, sample_activity, sample_location
) -> None:
    org = sample_activity.organization
    run = OrgEnrichmentRun(org_id=org.id, status="ready", seed_url="https://ok.test/")
    db_session.add(run)
    db_session.flush()
    good = _proposal(
        run,
        field="description",
        current_value={"description": org.description},
        proposed_value={"description": "Saturday art class for children."},
        proposed_hash="hash-desc",
    )
    schedule = _proposal(
        run,
        section="Schedules",
        kind="create_schedule",
        label="Schedule",
        proposed_value={
            "activity_name": sample_activity.name,
            "entries": [
                {"day_of_week": "nope", "start_time": "10:00", "end_time": "11:00"}
            ],
        },
        proposed_hash="hash-slot",
    )
    db_session.add_all([good, schedule])
    db_session.flush()
    results, _quality_run = apply_proposals(
        db_session,
        org.id,
        [str(schedule.id), str(good.id)],
        {},
        user_id="admin",
        request_id="req-slot",
    )
    by_id = {row["id"]: row["status"] for row in results}
    assert by_id[str(good.id)] == "applied"
    assert by_id[str(schedule.id)] == "error"
    assert db_session.query(ActivitySchedule).count() == 0
    assert org.description == "Saturday art class for children."


def _quality_settings(session, **flags: str):
    from app.db.models import ImportSettings

    row = session.get(ImportSettings, 1)
    if row is None:
        row = ImportSettings(
            id=1,
            skip_deleted_organizations=True,
            name_cleanup="apply",
            unknown_categories="capture",
        )
        session.add(row)
    row.duplicates = flags.get("duplicates", "off")
    row.locations = flags.get("locations", "off")
    row.categories = flags.get("categories", "off")
    session.flush()
    return row


def test_apply_stages_quality_checks_from_import_settings(
    db_session, sample_activity_category
) -> None:
    from uuid import UUID

    from app.db.models import DataQualityRun

    _quality_settings(
        db_session, duplicates="report", locations="check", categories="check"
    )
    org = _org(db_session, website="https://ok.test")
    run = OrgEnrichmentRun(org_id=org.id, status="ready", seed_url="https://ok.test/")
    db_session.add(run)
    db_session.flush()
    description = _proposal(
        run,
        field="description",
        label="Description",
        proposed_value={"description": "Saturday art class for children."},
        proposed_hash="hash-quality-desc",
    )
    activity = _proposal(
        run,
        section="Activities",
        kind="create_activity",
        label="Activity · Painting",
        proposed_value={
            "name": "Painting",
            "category_name": sample_activity_category.name,
            "age_min": 5,
            "age_max": 8,
        },
        proposed_hash="hash-quality-activity",
    )
    db_session.add_all([description, activity])
    db_session.flush()
    results, quality_run_id = apply_proposals(
        db_session,
        org.id,
        [str(description.id), str(activity.id)],
        {},
        user_id="admin",
        request_id="req-quality",
    )
    assert {row["status"] for row in results} == {"applied"}
    assert quality_run_id is not None
    quality = db_session.get(DataQualityRun, UUID(quality_run_id))
    assert quality is not None
    assert quality.trigger == "enrichment"
    assert [item["name"] for item in quality.checks] == [
        "duplicates",
        "locations",
        "categories",
    ]
    assert quality.scope["organization_ids"] == [str(org.id)]
    assert quality.scope["activity_ids"] == [str(activity.entity_id)]
    email = _proposal(
        run,
        field="email",
        label="Email",
        proposed_value={"email": "hello@example.com"},
        proposed_hash="hash-quality-email",
    )
    db_session.add(email)
    db_session.flush()
    _again, second_id = apply_proposals(
        db_session,
        org.id,
        [str(email.id)],
        {},
        user_id="admin",
        request_id="req-quality-2",
    )
    assert second_id is not None
    assert second_id != quality_run_id
    second = db_session.get(DataQualityRun, UUID(second_id))
    assert second is not None
    assert [item["name"] for item in second.checks] == ["duplicates"]
    assert second.scope["activity_ids"] == []


def test_location_apply_runs_locations_without_categories(
    db_session, sample_geographic_area
) -> None:
    from uuid import UUID

    from app.db.models import DataQualityRun

    _quality_settings(db_session, locations="check", categories="check")
    org = _org(db_session, website="https://ok.test")
    run = OrgEnrichmentRun(org_id=org.id, status="ready", seed_url="https://ok.test/")
    db_session.add(run)
    db_session.flush()
    location = _proposal(
        run,
        section="Locations",
        kind="create_location",
        label="Location",
        proposed_value={"address": "9 Example Road"},
        proposed_hash="hash-quality-location",
    )
    db_session.add(location)
    db_session.flush()
    results, quality_run_id = apply_proposals(
        db_session,
        org.id,
        [str(location.id)],
        {str(location.id): {"area_id": str(sample_geographic_area.id)}},
        user_id="admin",
        request_id="req-location-quality",
    )
    assert results[0]["status"] == "applied"
    assert quality_run_id is not None
    quality = db_session.get(DataQualityRun, UUID(quality_run_id))
    assert quality is not None
    assert [item["name"] for item in quality.checks] == ["locations"]
    assert quality.scope["activity_ids"] == []


def test_contact_apply_skips_location_and_category_checks(db_session) -> None:
    from app.db.models import DataQualityRun
    from sqlalchemy import select

    _quality_settings(db_session, locations="check", categories="check")
    org = _org(db_session, website="https://ok.test")
    run = OrgEnrichmentRun(org_id=org.id, status="ready", seed_url="https://ok.test/")
    db_session.add(run)
    db_session.flush()
    proposal = _proposal(
        run,
        field="email",
        label="Email",
        proposed_value={"email": "hello@example.com"},
        proposed_hash="hash-quality-contact",
    )
    db_session.add(proposal)
    db_session.flush()
    results, quality_run_id = apply_proposals(
        db_session,
        org.id,
        [str(proposal.id)],
        {},
        user_id="admin",
        request_id="req-contact-quality",
    )
    assert results[0]["status"] == "applied"
    assert quality_run_id is None
    assert db_session.scalars(select(DataQualityRun)).all() == []


def test_quality_stage_failure_keeps_the_apply(db_session, monkeypatch) -> None:
    from app.db.models import DataQualityRun
    from sqlalchemy import select

    def explode(*_args, **_kwargs):
        raise RuntimeError("settings unavailable")

    monkeypatch.setattr(
        "app.services.data_quality.runs.stage_enrichment_run",
        explode,
    )
    _quality_settings(db_session, duplicates="report")
    org = _org(db_session, website="https://ok.test")
    run = OrgEnrichmentRun(org_id=org.id, status="ready", seed_url="https://ok.test/")
    db_session.add(run)
    db_session.flush()
    proposal = _proposal(
        run,
        field="description",
        label="Description",
        proposed_value={"description": "Saturday art class for children."},
        proposed_hash="hash-quality-stage-fail",
    )
    db_session.add(proposal)
    db_session.flush()
    results, quality_run_id = apply_proposals(
        db_session,
        org.id,
        [str(proposal.id)],
        {},
        user_id="admin",
        request_id="req-stage-fail",
    )
    assert results[0]["status"] == "applied"
    assert quality_run_id is None
    assert org.description == "Saturday art class for children."
    assert db_session.scalars(select(DataQualityRun)).all() == []


def test_apply_skips_quality_run_when_checks_are_off(db_session) -> None:
    from app.db.models import DataQualityRun
    from sqlalchemy import select

    _quality_settings(db_session)
    org = _org(db_session, website="https://ok.test")
    run = OrgEnrichmentRun(org_id=org.id, status="ready", seed_url="https://ok.test/")
    db_session.add(run)
    db_session.flush()
    proposal = _proposal(
        run,
        field="description",
        label="Description",
        proposed_value={"description": "Saturday art class for children."},
        proposed_hash="hash-quality-off",
    )
    db_session.add(proposal)
    db_session.flush()
    results, quality_run_id = apply_proposals(
        db_session,
        org.id,
        [str(proposal.id)],
        {},
        user_id="admin",
        request_id="req-off",
    )
    assert results[0]["status"] == "applied"
    assert quality_run_id is None
    assert db_session.scalars(select(DataQualityRun)).all() == []


def test_failed_apply_does_not_stage_a_quality_run(db_session) -> None:
    from app.db.models import DataQualityRun
    from sqlalchemy import select

    _quality_settings(db_session, duplicates="report")
    org = _org(db_session, description="Kept by an editor")
    run = OrgEnrichmentRun(org_id=org.id, status="ready", seed_url="https://ok.test/")
    db_session.add(run)
    db_session.flush()
    proposal = _proposal(
        run,
        field="description",
        label="Description",
        current_value={"description": "old"},
        proposed_value={"description": "Saturday art class for children."},
        proposed_hash="hash-quality-stale",
    )
    db_session.add(proposal)
    db_session.flush()
    results, quality_run_id = apply_proposals(
        db_session,
        org.id,
        [str(proposal.id)],
        {},
        user_id="admin",
        request_id="req-stale-quality",
    )
    assert results[0]["status"] == "error"
    assert quality_run_id is None
    assert db_session.scalars(select(DataQualityRun)).all() == []


def test_apply_route_enqueues_the_quality_run(db_session, monkeypatch) -> None:
    import json

    from app.api.admin_enrichment import handle_org_enrichment

    _quality_settings(db_session, duplicates="report", locations="check")
    org = _org(db_session, website="https://ok.test")
    run = OrgEnrichmentRun(org_id=org.id, status="ready", seed_url="https://ok.test/")
    db_session.add(run)
    db_session.flush()
    proposal = _proposal(
        run,
        field="description",
        label="Description",
        proposed_value={"description": "Saturday art class for children."},
        proposed_hash="hash-quality-route",
    )
    db_session.add(proposal)
    db_session.flush()
    enqueued: list[str | None] = []

    class _OpenSession:
        def __enter__(self):
            return db_session

        def __exit__(self, *_args) -> bool:
            return False

    monkeypatch.setattr("app.api.admin_enrichment.get_engine", lambda: None)
    monkeypatch.setattr(
        "app.api.admin_enrichment.Session",
        lambda _engine: _OpenSession(),
    )
    monkeypatch.setattr(
        "app.api.admin_enrichment._set_session_audit_context",
        lambda _session, _event: None,
    )
    monkeypatch.setattr(db_session, "commit", db_session.flush)
    monkeypatch.setattr(
        "app.services.data_quality.runs.enqueue_staged_run",
        lambda run_id: enqueued.append(run_id),
    )
    response = handle_org_enrichment(
        {
            "httpMethod": "POST",
            "path": f"/v1/admin/organizations/{org.id}/enrichment/apply",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"ids": [str(proposal.id)]}),
            "requestContext": {
                "requestId": "req-route",
                "authorizer": {"groups": "admin", "userSub": "admin-user"},
            },
        },
        "POST",
        str(org.id),
    )
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert body["results"][0]["status"] == "applied"
    assert body["data_quality_run_id"]
    assert enqueued == [body["data_quality_run_id"]]


def test_dismiss_does_not_enqueue_a_quality_run(db_session, monkeypatch) -> None:
    import json

    from app.api.admin_enrichment import handle_org_enrichment
    from app.db.models import DataQualityRun
    from sqlalchemy import select

    _quality_settings(db_session, duplicates="report")
    org = _org(db_session, website="https://ok.test")
    run = OrgEnrichmentRun(org_id=org.id, status="ready", seed_url="https://ok.test/")
    db_session.add(run)
    db_session.flush()
    proposal = _proposal(
        run,
        field="description",
        label="Description",
        proposed_value={"description": "Saturday art class for children."},
        proposed_hash="hash-quality-dismiss",
    )
    db_session.add(proposal)
    db_session.flush()
    enqueued: list[str | None] = []

    class _OpenSession:
        def __enter__(self):
            return db_session

        def __exit__(self, *_args) -> bool:
            return False

    monkeypatch.setattr("app.api.admin_enrichment.get_engine", lambda: None)
    monkeypatch.setattr(
        "app.api.admin_enrichment.Session",
        lambda _engine: _OpenSession(),
    )
    monkeypatch.setattr(
        "app.api.admin_enrichment._set_session_audit_context",
        lambda _session, _event: None,
    )
    monkeypatch.setattr(db_session, "commit", db_session.flush)
    monkeypatch.setattr(
        "app.services.data_quality.runs.enqueue_staged_run",
        lambda run_id: enqueued.append(run_id),
    )
    response = handle_org_enrichment(
        {
            "httpMethod": "POST",
            "path": f"/v1/admin/organizations/{org.id}/enrichment/dismiss",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"ids": [str(proposal.id)]}),
            "requestContext": {
                "requestId": "req-dismiss",
                "authorizer": {"groups": "admin", "userSub": "admin-user"},
            },
        },
        "POST",
        str(org.id),
    )
    body = json.loads(response["body"])
    assert body["results"][0]["status"] == "dismissed"
    assert "data_quality_run_id" not in body
    assert enqueued == []
    assert db_session.scalars(select(DataQualityRun)).all() == []
