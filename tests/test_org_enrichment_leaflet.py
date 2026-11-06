"""Leaflet enrichment: upload or URL, vision text, and a media proposal."""

from __future__ import annotations

import io
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from app.db.models import Organization
from app.db.models.org_enrichment import OrgEnrichmentProposal, OrgEnrichmentRun
from app.exceptions import ValidationError
from app.services.aws_proxy import AwsProxyError
from app.services.enrichment.apply import apply_proposals
from app.services.enrichment.fetch import FetchResult
from app.services.enrichment.leaflet import (
    normalize_leaflet_items,
    presign_leaflet,
    read_leaflets,
    sniff_leaflet,
)
from app.services.enrichment.leaflet_vision import transcript_parts
from app.services.enrichment.proxy_crawl import handle_crawl_event
from app.services.enrichment.run import process_enrichment
from app.services.enrichment.store import start_run
from PIL import Image

_ORG = "11111111-1111-1111-1111-111111111111"


def _jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), (10, 20, 30)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _scan_pdf() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), (1, 2, 3)).save(buffer, format="PDF")
    return buffer.getvalue()


def _org(session, **fields) -> Organization:
    org = Organization(
        name=f"Leaflet Club {uuid4().hex[:8]}", manager_id="mgr-1", **fields
    )
    session.add(org)
    session.flush()
    return org


def test_sniff_accepts_a_picture_or_pdf() -> None:
    assert sniff_leaflet(_jpeg()) == ("jpg", "image/jpeg")
    assert sniff_leaflet(_scan_pdf()) == ("pdf", "application/pdf")
    assert sniff_leaflet(b"hello") is None


def test_transcript_parts_share_a_reply_that_will_not_split() -> None:
    assert transcript_parts('{"parts": ["fee", "time"]}', 2) == ["fee", "time"]
    assert transcript_parts("one block of text", 2) == [
        "one block of text",
        "one block of text",
    ]


def test_start_run_from_a_url_does_not_touch_media(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.enrichment.guard.host_is_blocked",
        lambda host, resolve=None: False,
    )
    org = _org(db_session)
    run = start_run(
        db_session,
        org.id,
        requested_by="admin",
        leaflet={"url": "https://leaflets.example/term.pdf"},
    )
    assert run.source == "leaflet"
    assert run.seed_url == "https://leaflets.example/term.pdf"
    assert run.leaflet_items[0]["kind"] == "url"
    assert org.media_urls in (None, [])


def test_start_run_refuses_a_website_and_a_leaflet(db_session) -> None:
    org = _org(db_session, website="https://ok.test")
    with pytest.raises(ValidationError):
        start_run(
            db_session,
            org.id,
            requested_by="admin",
            website="https://ok.test",
            leaflet={"url": "https://leaflets.example/term.pdf"},
        )


def test_normalize_refuses_more_than_four_and_a_foreign_key() -> None:
    with pytest.raises(ValidationError):
        normalize_leaflet_items(
            _ORG,
            {
                "items": [
                    {"url": f"https://leaflets.example/{index}.pdf"}
                    for index in range(5)
                ]
            },
        )
    with pytest.raises(ValidationError):
        normalize_leaflet_items(
            _ORG,
            {"object_key": "organizations/other/enrichment/leaflets/a.pdf"},
        )


def test_uploaded_picture_is_headed_before_the_run(monkeypatch) -> None:
    monkeypatch.setenv("ORGANIZATION_MEDIA_BUCKET", "media")
    monkeypatch.setenv("ORGANIZATION_MEDIA_BASE_URL", "https://media.example")
    key = f"organizations/{_ORG}/enrichment/leaflets/abc.jpg"

    def head(object_key: str) -> dict[str, object]:
        assert object_key == key
        return {"content_type": "image/jpeg", "content_length": 1200}

    monkeypatch.setattr("app.services.enrichment.leaflet.head_leaflet", head)
    items = normalize_leaflet_items(_ORG, {"object_key": key})
    assert items[0]["url"] == f"https://media.example/{key}"
    assert items[0]["kind"] == "object"


def test_presign_stays_under_the_organization_prefix(monkeypatch) -> None:
    class _S3:
        def generate_presigned_url(self, operation, Params, ExpiresIn):
            assert operation == "put_object"
            assert Params["ContentType"] == "image/png"
            assert Params["Key"].startswith(
                f"organizations/{_ORG}/enrichment/leaflets/"
            )
            assert Params["Key"].endswith(".png")
            return "https://upload.example"

    monkeypatch.setenv("ORGANIZATION_MEDIA_BUCKET", "media")
    monkeypatch.setenv("ORGANIZATION_MEDIA_BASE_URL", "https://media.example")
    monkeypatch.setattr("app.services.aws_clients.get_s3_client", lambda: _S3())
    signed = presign_leaflet(UUID(_ORG), "Flyer.PNG", "image/png")
    assert signed["upload_url"] == "https://upload.example"
    assert signed["object_key"].endswith(".png")


def test_picture_becomes_a_vision_page_and_a_media_marker() -> None:
    key = f"organizations/{_ORG}/enrichment/leaflets/flyer.jpg"
    body = _jpeg()
    prepared = read_leaflets(
        _ORG,
        [
            {
                "kind": "object",
                "key": key,
                "url": f"https://media.example/{key}",
                "name": "flyer.jpg",
            }
        ],
        read_object=lambda object_key: body,
    )
    page = prepared["pages"][0]
    assert page["vision_urls"] == [f"https://media.example/{key}"]
    assert page["leaflet_media"]["object_key"] == key
    assert prepared["bytes_fetched"] == len(body)


def test_text_pdf_skips_vision(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.enrichment.leaflet._pdf_text",
        lambda url, body: "Saturday art class for children. " * 5,
    )
    key = f"organizations/{_ORG}/enrichment/leaflets/term.pdf"
    prepared = read_leaflets(
        _ORG,
        [
            {
                "kind": "object",
                "key": key,
                "url": "https://media.example/term.pdf",
                "name": "term.pdf",
            }
        ],
        read_object=lambda object_key: b"%PDF-1.4 text",
        put_image=lambda key, body, content_type: (_ for _ in ()).throw(
            AssertionError(key)
        ),
    )
    assert "vision_urls" not in prepared["pages"][0]
    assert "Saturday art" in prepared["pages"][0]["text"]
    assert "leaflet_media" not in prepared["pages"][0]


def test_scanned_pdf_sends_its_largest_page_image() -> None:
    stored: list[tuple[str, bytes, str]] = []
    key = f"organizations/{_ORG}/enrichment/leaflets/scan.pdf"
    prepared = read_leaflets(
        _ORG,
        [
            {
                "kind": "object",
                "key": key,
                "url": "https://media.example/scan.pdf",
                "name": "scan.pdf",
            }
        ],
        read_object=lambda object_key: _scan_pdf(),
        put_image=lambda object_key, body, content_type: (
            stored.append((object_key, body, content_type))
            or f"https://media.example/{object_key}"
        ),
    )
    assert stored
    assert stored[0][2] == "image/jpeg"
    assert prepared["pages"][0]["vision_urls"] == [
        f"https://media.example/{stored[0][0]}"
    ]


def test_proxy_stores_a_public_leaflet(monkeypatch) -> None:
    puts: list[dict[str, object]] = []

    class _S3:
        def put_object(self, **kwargs: object) -> None:
            puts.append(kwargs)

    monkeypatch.setenv("ORGANIZATION_MEDIA_BUCKET", "media")
    monkeypatch.setenv("ORGANIZATION_MEDIA_BASE_URL", "https://media.example")
    monkeypatch.setattr(
        "app.services.enrichment.proxy_crawl.check_fetch_url",
        lambda url, resolve=None: None,
    )
    monkeypatch.setattr(
        "app.services.enrichment.proxy_crawl.fetch_public",
        lambda url, max_bytes, timeout=10, deadline=None: FetchResult(
            200, url, "application/octet-stream", _jpeg(), "", False
        ),
    )
    monkeypatch.setattr("app.services.aws_clients.get_client", lambda service: _S3())
    result = handle_crawl_event(
        {"op": "leaflet", "url": "https://cdn.example/a.jpg", "org_id": _ORG}
    )
    assert result["result"]["content_type"] == "image/jpeg"
    assert str(result["result"]["key"]).startswith(
        f"organizations/{_ORG}/enrichment/leaflets/"
    )
    assert puts[0]["ContentType"] == "image/jpeg"


def test_proxy_refuses_a_file_that_is_not_a_leaflet(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.enrichment.proxy_crawl.check_fetch_url",
        lambda url, resolve=None: None,
    )
    monkeypatch.setattr(
        "app.services.enrichment.proxy_crawl.fetch_public",
        lambda url, max_bytes, timeout=10, deadline=None: FetchResult(
            200, url, "text/plain", b"not a leaflet", "", False
        ),
    )
    result = handle_crawl_event(
        {"op": "leaflet", "url": "https://cdn.example/a.txt", "org_id": _ORG}
    )
    assert result["error"]["message"] == "leaflet must be a picture or a PDF"


def test_stages_transcribe_then_extract_and_keep_the_picture_pending(
    db_session, monkeypatch
) -> None:
    monkeypatch.setenv("ORGANIZATION_MEDIA_BASE_URL", "https://media.example")
    org = _org(db_session)
    key = f"organizations/{org.id}/enrichment/leaflets/flyer.jpg"
    page_url = f"https://media.example/{key}"
    run = OrgEnrichmentRun(
        org_id=org.id,
        status="queued",
        source="leaflet",
        seed_url=page_url,
        leaflet_items=[{"kind": "object", "key": key, "url": page_url}],
    )
    db_session.add(run)
    db_session.flush()
    text = "Saturday art class for children in Wan Chai."

    def prepare(row: OrgEnrichmentRun) -> dict[str, object]:
        return {
            "pages": [
                {
                    "url": page_url,
                    "final_url": page_url,
                    "text": "",
                    "vision_urls": [page_url],
                    "leaflet_media": {
                        "source_url": page_url,
                        "object_key": key,
                        "label": "Leaflet · flyer.jpg",
                    },
                }
            ],
            "items": list(row.leaflet_items or []),
            "bytes_fetched": 40,
        }

    step = process_enrichment(
        db_session,
        run.id,
        "m-leaflet",
        receive_count=1,
        stage="leaflet",
        prepare=prepare,
    )
    assert step.enqueue_stage == "transcribe"
    assert org.media_urls in (None, [])

    def transcribe(urls: list[str], model_name: str):
        assert urls == [page_url]
        assert model_name
        return [text], Decimal("0.02"), "vision-test"

    step = process_enrichment(
        db_session,
        run.id,
        "m-vision",
        receive_count=1,
        stage="transcribe",
        transcribe=transcribe,
    )
    assert step.enqueue_stage == "extract"
    assert run.pages[0]["text"] == text
    assert run.cost_usd == Decimal("0.02")

    def complete(prompt: str):
        assert "Saturday art class" in prompt
        return (
            {
                "organization": {
                    "description": {
                        "value": "Saturday art class for children in Wan Chai.",
                        "confidence": 0.9,
                        "evidence": [{"url": page_url, "quote": "Saturday art class"}],
                    }
                }
            },
            Decimal("0.03"),
            "extract-test",
        )

    step = process_enrichment(
        db_session,
        run.id,
        "m-extract",
        receive_count=1,
        stage="extract",
        complete=complete,
    )
    assert step.enqueue_stage is None
    assert run.status == "ready"
    assert run.cost_usd == Decimal("0.05")
    from sqlalchemy import select

    rows = list(
        db_session.scalars(
            select(OrgEnrichmentProposal).where(OrgEnrichmentProposal.run_id == run.id)
        ).all()
    )
    media = next(row for row in rows if row.kind == "add_media")
    assert media.proposed_value["leaflet"] is True
    assert media.proposed_value["object_key"] == key
    assert org.media_urls in (None, [])
    description = next(row for row in rows if row.field == "description")
    assert description.proposed_value["description"].startswith("Saturday art")

    def copy_image(url: str, org_id: str) -> str:
        raise AssertionError(url)

    results, _quality = apply_proposals(
        db_session,
        org.id,
        [str(media.id)],
        {},
        user_id="admin",
        request_id="req",
        copy_image=copy_image,
    )
    assert results[0]["status"] == "applied"
    assert org.media_urls == [page_url]


def test_unreadable_leaflet_fails_without_a_retry(db_session) -> None:
    org = _org(db_session)
    run = OrgEnrichmentRun(
        org_id=org.id,
        status="queued",
        source="leaflet",
        seed_url="https://media.example/x",
        leaflet_items=[],
    )
    db_session.add(run)
    db_session.flush()

    def prepare(row: OrgEnrichmentRun) -> dict[str, object]:
        from app.services.enrichment.leaflet import LeafletReadError

        raise LeafletReadError("leaflet must be a picture or a PDF")

    step = process_enrichment(
        db_session,
        run.id,
        "m-bad",
        receive_count=1,
        stage="leaflet",
        prepare=prepare,
    )
    assert step.acked is True
    assert run.status == "failed"
    assert run.error == "leaflet must be a picture or a PDF"


def test_leaflet_proxy_failure_uses_the_leaflet_sentence(db_session) -> None:
    org = _org(db_session)
    run = OrgEnrichmentRun(
        org_id=org.id,
        status="queued",
        source="leaflet",
        seed_url="https://media.example/x",
    )
    db_session.add(run)
    db_session.flush()

    def prepare(row: OrgEnrichmentRun) -> dict[str, object]:
        raise AwsProxyError("LambdaInvocationError", "down")

    step = process_enrichment(
        db_session,
        run.id,
        "m-down",
        receive_count=1,
        stage="leaflet",
        prepare=prepare,
    )
    assert step.acked is True
    assert run.error == "The leaflet could not be read"
