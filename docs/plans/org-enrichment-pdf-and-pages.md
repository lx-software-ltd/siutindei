# Plan: Read PDFs and crawl up to 20 pages

**Status**: Done
**Zone**: red (settings check constraint), yellow (enrichment services, admin settings form)

The requester asked for PDFs and more than eight pages after the red-zone
migration was named in chat. That instruction is the approval for the
migration below.

## Goal

Timetables, fee sheets, and term brochures published as PDF reach the model. A run can read up to 20 pages, with 12 by default.

## Non-goals

No OCR of scanned PDFs, no images from PDFs, no links followed out of a PDF. No change to the proxy Lambda timeout, memory, or IAM. No JavaScript rendering.

## Files

- `backend/db/alembic/versions/0056_org_enrichment_pages.py` (red): `max_pages` check becomes 1 to 20, default 12. The settings row moves from the old default 6 to 12. Downgrade caps values at 8 and restores the old check and default.
- `backend/src/app/db/models/org_enrichment.py`: the same check and default.
- `backend/requirements.txt`: `pypdf==6.21.1`, pure Python, for the proxy Lambda bundle.
- `backend/src/app/services/enrichment/pdf.py` (new): text from at most 30 PDF pages, stopping at the page text limit or the crawl deadline. A broken, encrypted, or image-only PDF is skipped.
- `backend/src/app/services/enrichment/fetch.py`: PDF links are queued and fetched with their own byte limit. `application/pdf` is parsed by `pdf.py`. Site builders such as Squarespace redirect the site's own `/s/x.pdf` link to a file host. That redirect is accepted only when the link was on the site, ends in `.pdf`, and the answer is a PDF.
- `backend/src/app/services/enrichment/parse.py`: a PDF link starts two points ahead, so it beats plain menu pages. Skip words still sink it.
- `backend/src/app/utils/logging.py`: pypdf logs at error level only.
- `backend/src/app/services/enrichment/constants.py`: PDF byte limit, crawl budget 60s, prompt 90,000 characters, extract timeout 90s.
- `backend/src/app/services/enrichment/proxy_crawl.py`, `store.py`: page clamp 1 to 20. The JSON-LD sent back per page is capped, so 20 pages stay well under the Lambda 6 MB response limit.
- `apps/admin_web/src/components/admin/organization-enrichment-settings.tsx`: the form allows 20.
- `docs/api/admin.yaml`, `docs/architecture/database-schema.md`: the new range and default.
- `tests/test_org_enrichment_depth.py`.

## Invariants this change preserves

PDF fetches go through the same pinned, public-only fetch, robots check, and one-second pacing as HTML. Every redirect hop is still checked by `check_fetch_url`. Links on a PDF page are never followed, so a file host cannot widen the crawl. Every proposed value still needs a quote that is on a fetched page or PDF. The crawl stage stays inside the 120s admin function (60s budget plus proxy overhead). The extract stage stays inside it too (90s model timeout).

## Seed assessment

`backend/db/seed/seed_data.sql` has no `org_enrichment_settings` rows. Migration `0055_org_enrichment` inserts the singleton, and `0056` only changes its check, default, and old-default value. Existing seed SQL still runs.

## Done when

- `pytest tests/test_org_enrichment.py tests/test_org_enrichment_depth.py tests/test_alembic_revision_contract.py` passes.
- `alembic upgrade head` then the seed file runs on a fresh database.
- `pytest tests backend` passes on Postgres. `pre-commit run` passes on the changed files. Admin lint and typecheck pass.
- A live crawl of a provider site with a PDF timetable returns the PDF text.

## Rollback

`alembic downgrade 0055_org_enrichment` caps `max_pages` at 8, then revert the commits.

## Open questions

None.
