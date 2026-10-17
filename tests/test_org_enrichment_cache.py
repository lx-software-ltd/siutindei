"""Website enrichment: when an earlier run's proposals may be reused."""

from __future__ import annotations

from decimal import Decimal

from app.db.models import Organization
from app.db.models.org_enrichment import OrgEnrichmentProposal, OrgEnrichmentRun
from app.services.enrichment.run import _hash_pages, process_enrichment

_PAGES = [
    {
        "url": "https://ok.test/",
        "final_url": "https://ok.test/",
        "text": "North Club. Junior Skills Class Wednesdays 4:30pm. " * 5,
        "jsonld_raw": [],
        "og": {},
        "images": [],
        "links": [],
    }
]


def _org(session) -> Organization:
    org = Organization(name="North Club", manager_id="mgr-1", website="https://ok.test")
    session.add(org)
    session.flush()
    return org


def _ready_run(session, org, input_hash: str) -> OrgEnrichmentRun:
    run = OrgEnrichmentRun(
        org_id=org.id,
        status="ready",
        seed_url="https://ok.test/",
        pages=_PAGES,
        input_hash=input_hash,
        cost_usd=Decimal("0.01"),
        model="test/model",
    )
    session.add(run)
    session.flush()
    session.add(
        OrgEnrichmentProposal(
            run_id=run.id,
            org_id=org.id,
            section="Organization",
            kind="update_organization",
            field="organization.description",
            label="Description",
            proposed_value={"value": "Old description"},
            proposed_hash="old",
            confidence=Decimal("0.9"),
            evidence=[{"url": "https://ok.test/", "quote": "North Club"}],
        )
    )
    session.flush()
    return run


def _extract(session, org, model_calls: list[str]) -> OrgEnrichmentRun:
    run = OrgEnrichmentRun(org_id=org.id, status="queued", seed_url="https://ok.test/")
    session.add(run)
    session.flush()

    def complete(prompt: str):
        model_calls.append(prompt)
        return {}, Decimal("0.02"), "test/model"

    process_enrichment(
        session,
        run.id,
        "m-crawl",
        receive_count=1,
        stage="crawl",
        crawl=lambda row, settings: {
            "status": "ok",
            "pages": _PAGES,
            "pages_fetched": 1,
        },
        complete=complete,
    )
    process_enrichment(
        session,
        run.id,
        "m-extract",
        receive_count=1,
        stage="extract",
        complete=complete,
    )
    return run


def test_same_pages_and_same_extraction_code_reuse_the_result(
    db_session, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.services.enrichment.run.enqueue_enrichment", lambda run_id, *, stage: None
    )
    org = _org(db_session)
    _ready_run(db_session, org, _hash_pages(_PAGES))
    calls: list[str] = []

    run = _extract(db_session, org, calls)

    assert calls == []
    assert run.status == "ready" and run.model == "cache"


def test_result_from_older_extraction_code_is_not_reused(
    db_session, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.services.enrichment.run.enqueue_enrichment", lambda run_id, *, stage: None
    )
    monkeypatch.setattr(
        "app.services.enrichment.run.EXTRACTION_VERSION", "older-prompt"
    )
    org = _org(db_session)
    _ready_run(db_session, org, _hash_pages(_PAGES))
    monkeypatch.setattr("app.services.enrichment.run.EXTRACTION_VERSION", "new-prompt")
    calls: list[str] = []

    run = _extract(db_session, org, calls)

    assert len(calls) == 1
    assert run.status == "ready" and run.model == "test/model"


def test_hash_without_a_version_is_never_reused(db_session, monkeypatch) -> None:
    """Runs made before this change hashed only the page text."""
    import hashlib

    monkeypatch.setattr(
        "app.services.enrichment.run.enqueue_enrichment", lambda run_id, *, stage: None
    )
    org = _org(db_session)
    text = "\n".join(str(page["text"]) for page in _PAGES)
    _ready_run(db_session, org, hashlib.sha256(text.encode()).hexdigest())
    calls: list[str] = []

    _extract(db_session, org, calls)

    assert len(calls) == 1
