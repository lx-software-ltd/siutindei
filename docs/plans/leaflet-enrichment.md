# Plan: Enrich one organization from a leaflet

**Status**: Done
**Zone**: yellow, plus red for the migration and `openrouter_client.py`. Both were approved in chat.

## Goal

An admin, or a full-access partner `crud` key, starts enrichment from up to four leaflet files. Each file is an uploaded JPEG, PNG, or WebP, or a PDF, or a public URL of one of those. The worker reads the leaflet and writes the same proposal rows as website enrichment. Nothing is written to the catalog until a row is applied. Each picture is an `add_media` proposal, selected in the admin card when the run is ready.

## Non-goals

- A headless browser, or rendering PDF pages to bitmaps.
- Auto-apply.
- Importer upload. Importers may still start a run from a public URL on the existing enrichment POST. The upload presign stays admin and partner only.
- Replacing the website crawl.

## Decisions

1. A picture is stored under `organizations/{id}/enrichment/leaflets/` as soon as it is uploaded or copied, so the vision model can fetch a public bucket URL. It is not added to `media_urls` until the media proposal is applied. Apply uses the stored object and does not download it again.
2. The default vision model is `qwen/qwen3-vl-30b-a3b-instruct`. `org_enrichment_settings.leaflet_model` overrides it, then `OPENROUTER_VISION_MODEL`.
3. A PDF with readable text uses that text. A PDF with little or no text sends the largest embedded image from each of up to four pages to the vision model. Pillow is on the admin bundle because some PDF images only decode with it.
4. One run accepts up to four files. Each file is one page in the extract prompt. At most eight images are sent in one vision call.
5. Fetch, then transcribe, then extract are separate queue deliveries so each stays inside the 120 second function.
6. Partner keys use the same bodies on `/v1/partner/organizations/{id}/enrichment` and `.../enrichment/leaflet-upload`. The partner `{proxy+}` route already reaches the admin function.

## Files

- `backend/db/alembic/versions/0063_leaflet_enrich.py` (red)
- `backend/src/app/services/openrouter_client.py` (red): user content may be a list of parts
- `backend/src/app/db/models/org_enrichment.py`
- `backend/src/app/services/enrichment/leaflet.py`, `pdf.py`, `proxy_crawl.py`, `run.py`, `store.py`, `apply_rows.py`, `constants.py`
- `backend/src/app/api/admin_enrichment.py`
- `docs/api/admin.yaml`, `docs/api/partner.yaml`, architecture docs
- `apps/admin_web` leaflet dialog, settings field, e2e

## Invariants this change preserves

- Nothing is written to the catalog before apply, including `media_urls`.
- `source`, `source_id`, `source_url`, and `place_id` are never written.
- A proposed value still needs a quote on the leaflet text, except the picture proposal itself, which is the file the caller supplied.
- Public URL fetches stay on the proxy, with `check_fetch_url` on every hop.
- `type: "http"` stays prefix allow-listed. OpenRouter is still only called through `openrouter_client`.
- The importer group cannot apply, dismiss, or presign a leaflet upload.
- The transcript is not logged.

## Done when

- `pytest tests/test_org_enrichment_leaflet.py tests/test_org_enrichment.py tests/test_partner_org_enrichment.py tests/test_alembic_revision_contract.py tests/test_admin_import_auth.py tests/test_cognito_group_authorizer.py tests/test_openrouter_reply_room.py`
- `python3 scripts/check_openapi_routes.py`
- `node scripts/check-lambda-docs.mjs`
- `pre-commit run ruff-format --all-files`
- Admin `npm run lint`, `npm run typecheck`, and the organizations Playwright spec
- `alembic upgrade head` on a fresh database

## Rollback

Revert the branch. Downgrade to `0062_location_status` drops `source`, `leaflet_items`, and `leaflet_model`. Objects under `organizations/*/enrichment/leaflets/` stay in the bucket until a later cleanup. Applied proposals stay.

## Seed

`org_enrichment_settings` is inserted by `0055_org_enrichment`. `leaflet_model` is nullable, so that row needs no new value. `source` is NOT NULL with server default `website`, and existing runs receive it. No `seed_data.sql` change.

## Open questions

None.
