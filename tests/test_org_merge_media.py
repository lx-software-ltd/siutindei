"""Failed media deletes stay visible after a committed merge."""

from __future__ import annotations

from app.services.org_merge_media import delete_merged_media


def test_delete_reports_keys_when_the_client_fails(monkeypatch, caplog) -> None:
    monkeypatch.setenv("ORGANIZATION_MEDIA_BUCKET", "media-bucket")

    class Client:
        def delete_object(self, **_kwargs: object) -> None:
            raise RuntimeError("denied")

    monkeypatch.setattr(
        "app.services.aws_clients.get_s3_client",
        lambda region_name=None: Client(),
    )
    with caplog.at_level("ERROR"):
        failed = delete_merged_media(
            ["organizations/src/logo.png"],
            survivor_id="survivor-id",
        )
    assert failed == ["organizations/src/logo.png"]
    assert "organizations/src/logo.png" in caplog.text
    assert "survivor-id" in caplog.text


def test_delete_reports_keys_when_the_bucket_is_unset(monkeypatch, caplog) -> None:
    monkeypatch.delenv("ORGANIZATION_MEDIA_BUCKET", raising=False)
    with caplog.at_level("ERROR"):
        failed = delete_merged_media(
            ["organizations/src/logo.png"],
            survivor_id="survivor-id",
        )
    assert failed == ["organizations/src/logo.png"]
    assert "media bucket is unset" in caplog.text


def test_delete_reports_every_key_when_the_client_cannot_be_built(
    monkeypatch, caplog
) -> None:
    monkeypatch.setenv("ORGANIZATION_MEDIA_BUCKET", "media-bucket")

    def explode(region_name: str | None = None) -> None:
        raise RuntimeError("no client")

    monkeypatch.setattr("app.services.aws_clients.get_s3_client", explode)
    with caplog.at_level("ERROR"):
        failed = delete_merged_media(
            ["organizations/src/a.png", "organizations/src/b.png"],
            survivor_id="survivor-id",
        )
    assert failed == ["organizations/src/a.png", "organizations/src/b.png"]
    assert "organizations/src/a.png" in caplog.text


def test_delete_of_no_keys_is_a_no_op(monkeypatch) -> None:
    monkeypatch.delenv("ORGANIZATION_MEDIA_BUCKET", raising=False)
    assert delete_merged_media([]) == []
