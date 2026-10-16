# Plan: Enrich one organization from its website

**Status**: Accepted
**Zone**: yellow, plus red for the migration, the HTTP proxy, the
authorizer, and `api-stack.ts`

## Decisions

1. Crawl runs as `type: "crawl"` on the existing out-of-VPC proxy.
   The prefix allow-list on `type: "http"` stays as it is.
2. Same-site means the same registrable domain (eTLD+1). Multi-part
   public suffixes such as `com.hk` and `co.uk` are a vendored list,
   so two different `.com.hk` hosts are not the same site. Subdomains
   of that registrable domain are in scope. Raw IP hosts are refused.
3. Media is copied into `ORGANIZATION_MEDIA_BUCKET` under
   `organizations/{id}/enrichment/`. The copyright notice is stored on
   the proposal and as S3 object metadata. The card states it.
4. A new activity whose category resolves is created. On an
   organization still in review, an unknown category uses Pending
   categorisation so the existing readiness blocker applies, and the
   next category sweep does the model check. On an approved
   organization an unknown category is not applied, because Pending
   categorisation would drop the activity out of search. Nothing is
   auto-assigned.
5. The monthly budget default is 25 USD. One run is a few cents on
   the current model, and 25 USD is half the location and translation
   sweep caps because this runs one organization at a time.
6. The board keeps its own enrich duty. The importer group may
   `GET` and `POST /v1/admin/organizations/{id}/enrichment`. Apply
   and dismiss stay admin-only.

## Goal

An admin presses Enrich from website on the Details card. The worker
crawls that organization's website, proposes organization, media,
location, activity, pricing, and schedule changes, and writes nothing
until an admin applies a row.

## Non-goals

- A headless browser. A script-only page ends as `render_required`.
- Auto-apply, even for JSON-LD.
- Crawling social hosts.
- A per-URL fetch cache in the proxy. The proxy has no database, so
  each run fetches its own pages.
- Replacing the board's catalog-enrich duty.

## Files

- `backend/db/alembic/versions/0055_org_enrichment.py` (red)
- `backend/src/app/db/models/org_enrichment.py`
- `backend/src/app/services/enrichment/`
- `backend/src/app/services/aws_proxy.py` (red) and
  `backend/infrastructure/lib/api-stack.ts` (red)
- `backend/lambda/authorizers/cognito_group/handler.py` (red)
- `backend/src/app/api/admin_enrichment.py`, `admin.py`
- `backend/lambda/category_suggestions/handler.py`
- `docs/api/admin.yaml`, architecture docs
- `apps/admin_web` Details card, enrichment card, e2e fixture

## Invariants this change preserves

- `type: "http"` remains prefix allow-listed.
- `source`, `source_id`, `source_url`, and `place_id` are never
  written. A stored pin is never replaced.
- Apply goes through the existing validators. Catalog versions record
  reason `enrichment` on PostgreSQL.
- The importer group cannot apply or dismiss.
- Contact values are not written to logs or the enrich audit row.
- Crawl time plus the model call stay inside the 120 second function
  by splitting crawl and extract across two queue messages. The crawl
  budget is 20 seconds so one request per second still fits.

## Done when

- `pytest tests/test_org_enrichment.py tests/test_cognito_group_authorizer.py tests/test_admin_import_auth.py`
- `python3 scripts/check_openapi_routes.py`
- `node scripts/check-lambda-docs.mjs`
- `pytest tests/test_alembic_revision_contract.py`
- `npm run lint` and `npm run typecheck` in `apps/admin_web`
- Playwright `e2e/organizations.spec.ts` covers the button
- `pre-commit run ruff-format --all-files` before the Python commit

## Rollback

Revert the branch. Downgrade to `0054` drops the enrichment tables.
Organizations, media, and catalog rows already applied stay.
Copied objects under `organizations/*/enrichment/` stay in the bucket
until a later cleanup.

## Seed

`org_enrichment_settings` is inserted by the migration. The run and
proposal tables stay empty. `seed_data.sql` is unchanged.

## Open questions

None.
