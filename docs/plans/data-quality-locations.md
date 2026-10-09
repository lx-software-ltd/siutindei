# Plan: Data quality Locations tab

**Status**: Accepted
**Zone**: yellow, plus one red migration under `backend/db/alembic/versions/`

## Decisions

1. Migration `0042_location_fixes` is approved.
2. `rule:single_location` links the activity immediately and stores the proposal as `applied`. A dismissed proposal for that same venue is not linked again.
3. Bulk actions stay **Apply selected** and **Dismiss selected**, with the header checkbox selecting the visible page, then all matching rows.
4. Model-proposed addresses are geocoded through the Nominatim proxy before the proposal is stored, and again on apply when coordinates are still missing or the admin changed the address.
5. Full-access `crud` keys can apply and dismiss (`POST /v1/partner/location-fixes/{id}` and `/bulk`). Org-scoped keys can read only their rows and receive `403` on writes.
6. `activity_no_location` is a warning. It does not block approval.
7. Location sweeps have their own `location_fix_settings.monthly_cost_limit_usd` (default 50). Category-check spend is not counted against it. The model and fallbacks still come from category-check settings.

## Goal

Add a fourth Data quality tab, Locations, that finds organizations and
activities without a usable venue and proposes a fix. Every activity
must end up with at least one `activity_locations` row. Rules resolve
the obvious cases; the model (OpenRouter) resolves the ambiguous ones.
Admins sweep, then apply or dismiss one row or every matching row. A
full-access partner API key sees the same pending proposals on the
organization and activity payloads and on a list route.

## Non-goals

- Changing the `locations` schema or the `activity_locations` join.
- Geocoding every location or fixing `missing_coordinates` (stays an
  org-review blocker; a Nominatim lookup is an optional follow-up).
- Duplicate-location detection or merging locations.
- Auto-applying model verdicts. Rule and model proposals both wait for
  an admin decision.
- New API Gateway resources. `/v1/admin/location-fixes*` and
  `/v1/partner/location-fixes*` ride the existing greedy
  `admin/{proxy+}` and `partner/{proxy+}` routes.

## Findings and proposals

A sweep looks at organizations (and their activities) in
`review_scope`: `pending_review` (default) or `all`.

| Finding | Rule (no model) | Model fallback |
| --- | --- | --- |
| Activity has no `activity_locations` row, org has exactly one location | `link_existing` to that location, source `rule:single_location` | – |
| Activity has no join row but pricing or schedule rows name a location | `link_existing` to that location, source `rule:pricing_schedule` | – |
| Activity has no join row, org has several locations | Activity name carries an HK area tag (`name_sanitizer_areas.HK_AREAS`) matching exactly one location's district → `link_existing`, source `rule:name_area` | Model picks one or more org locations by index from name, description, source URL host; `link_existing`, source `model`, with confidence and rationale |
| Organization has no locations | – | Model infers address and district from org name, translations, description, source URL host; district must be one of the active `geographic_areas` leaves sent in the prompt → `create_location`, source `model` |
| Nothing resolves | – | `unresolved` row so the admin sees the gap and can create a location by hand (link to the Locations CRUD screen) |

Prompts redact contacts and reuse the taxonomy-list pattern from
`category_suggestions/prompt.py`: the model chooses from a closed list
(location indices or area names), never free text for the join target.

## Storage (red: one migration)

`0042_location_fixes` adds two tables. No seed change.

`location_fix_proposals`: `id`, `entity_type`
(`organization|activity`), `entity_id`, `org_id` (FK CASCADE), `kind`
(`link_existing|create_location|unresolved`), `target_location_id`
(FK locations SET NULL), `proposed_location` JSONB (`address`,
`area_id`, `area_name`, `lat`, `lng`, `place_id`), `source`
(`rule:single_location|rule:pricing_schedule|rule:name_area|model`),
`confidence` Numeric(4,3), `rationale`, `status`
(`pending|applied|dismissed`), `scan_run_id`, `decided_by`,
`decided_at`, `created_at`, `updated_at`. Partial unique index: one
`pending` row per `(entity_type, entity_id)`.

`location_scan_runs`: same shape as `category_scan_runs` (status,
`requested_by`, `org_id`, `review_scope`, totals, `batches_done`,
counts per kind, `cost_usd`, `error`, `processed_message_ids`,
timestamps) with the same partial unique index that allows one queued
or running run.

## Flow

`POST /v1/admin/location-fixes/scan` `{review_scope, entity_type?,
org_id?, q?}`:

1. Rules run synchronously, bounded like `name_fix_scan._MAX_SWEEP`.
   Pending rows that no longer apply are deleted (`cleared`). A
   dismissed proposal with the same target or proposed value is not
   recreated (`skipped`).
2. Remaining gaps are chunked into SQS messages
   `{"location_scan_run_id", "entity_type", "entity_ids"}` on the
   existing category-suggestions queue. `backend/lambda/category_suggestions/handler.py`
   dispatches on the new key. Model and fallbacks come from
   `category_suggestion_settings`; spend counts toward the same
   `monthly_cost_limit_usd`.
3. Response: `{scan_run_id, truncated, created, updated, skipped,
   cleared, queued_for_model}`. The summary endpoint reports the active
   run so the tab can poll, as the Categories tab does.

Decide (`POST /v1/admin/location-fixes/{id}` and `/bulk`, with
`dry_run`):

- `apply` on `link_existing` inserts the join row when the target
  location still exists on the same org; otherwise the row fails.
- `apply` on `create_location` creates the location through the
  existing validators in `admin_resource_location.py` (area exists,
  address unique per org, coordinate ranges), then links the org's
  orphan activities when that location is now the org's only one. The
  admin may override `address` and `area_id` in the request body.
- `dismiss` marks the row. `unresolved` rows accept only dismiss.
- Audit context is set with `_set_session_audit_context`; table
  triggers record the writes.

Org review: add activity blocker `activity_no_location` ("Activity has
no location") in `org_review.py` and `org_review_sql.py`, linking to
`section=data-quality&tab=locations&organization=…`. `no_locations`
stays as is.

## Partner API

- `GET /v1/partner/organizations` (list and detail) gains
  `pending_location_fixes` next to `pending_name_fixes`, covering the
  org and its activities.
- `GET /v1/partner/activities` (list and detail) gains `location_ids`
  and `pending_location_fix`, so a key can tell whether an activity
  has a venue at all.
- `GET /v1/partner/location-fixes` lists pending proposals, filtered
  to the key's org when org-scoped. Writes for full-access `crud`
  keys are an open question below.

## Files

Backend (yellow unless noted):

- `backend/db/alembic/versions/0042_location_fixes.py` (red)
- `backend/src/app/db/models/location_fix.py`, export in `models/__init__.py`
- `backend/src/app/services/location_fixes.py` (list, get, summary, decide, bulk)
- `backend/src/app/services/location_fix_scan.py` (rules, candidate selection, run creation)
- `backend/src/app/services/location_fix_model.py` (prompt, batch processing, parsing)
- `backend/src/app/api/admin_location_fixes.py`; dispatch in `admin.py`
- `backend/src/app/api/partner_location_fixes.py`; dispatch in `partner_routes.py`; keys in `partner_name_fixes.partner_get_organizations` and `partner_category_reviews.partner_get_activities`
- `backend/lambda/category_suggestions/handler.py` (new message key)
- `backend/src/app/services/org_review.py`, `org_review_sql.py`

Admin web:

- `components/admin/data-quality/data-quality-page.tsx` (tab)
- `components/admin/data-quality/locations-panel.tsx` (new, modeled on `names-panel.tsx`)
- `lib/api-client-data-quality.ts`, `lib/admin-query-keys.ts`, `lib/admin-section-params.ts` (`location-fix` param)
- Generated OpenAPI types via `npm run generate:api`

Docs and specs:

- `docs/api/admin.yaml`, `docs/api/partner.yaml`
- `docs/architecture/data-quality.md`, `database-schema.md`, `lambdas.md`

Tests (written first):

- `tests/test_location_fix_scan.py`, `tests/test_location_fixes.py`, `tests/test_location_fix_model.py`, `tests/test_partner_location_fixes.py`, `tests/test_org_review.py` (new blocker)
- `apps/admin_web/tests/components/admin/locations-panel.test.tsx`
- `apps/admin_web/e2e/data-quality.spec.ts` and mock routes in `e2e/fixtures/test-fixtures.ts`

## UI

Toolbar order matches Names: summary line, **Sweep pending**, **Sweep
all orgs**, **Apply selected**, **Dismiss selected**. The header
checkbox selects the visible page, then all matching rows; the bulk
call sends `ids` or the current filters. Filters: Name, Record
(organizations and activities), Kind, Source, Status (default
pending), plus the `organization` URL param from the review queue.
Columns: Record, Current ("No location" or "0 of 3 venues"),
Proposed (address · district, or the target venue), Source and
confidence. The expanded row shows the rationale and, for
`create_location`, an editable address and area select before Apply.
While a model run is active the sweep buttons are disabled and the
summary shows batch progress.

## Invariants this change preserves

- OpenRouter is called only through `app.services.openrouter_client`.
- Prompts redact emails and phone numbers; no PII in logs.
- One queued or running location run at a time; stale runs fail after
  the same 11-minute window as category checks.
- Location writes go through the existing validators; `area_id` is
  always a real `geographic_areas` row.
- No CDK, auth, or `shared/**` changes.

## Done when

- `pytest tests backend` passes, including the new test files.
- `pre-commit run ruff-format --all-files` is clean.
- `npm run test` and `npm run e2e` in `apps/admin_web/` pass with the
  new Locations specs.
- `npm run generate:api` output is committed.
- Manual check on the cloud VM: sweep creates rule proposals for a
  seeded orphan activity, Apply inserts the join row, the org-review
  blocker clears, and `GET /v1/partner/organizations` shows
  `pending_location_fixes`.

## Rollback

Revert the pull request. Downgrade drops the two tables; applied join
rows and created locations are valid catalog data and stay.

## Open questions

1. Red-zone approval for `0042_location_fixes`.
2. Should `rule:single_location` proposals auto-apply (as the 0031
   backfill did) or wait for Apply like every other row?
3. Keep "Apply selected" / "Dismiss selected" with the select-all
   checkbox, or add literal "Apply all" / "Dismiss all" buttons that
   skip selection?
4. For orgs with no locations, should `create_location` also geocode
   the proposed address through the Nominatim proxy to fill `lat` and
   `lng`?
5. Partner writes (`POST /v1/partner/location-fixes/{id}` and
   `/bulk` for full-access `crud` keys) in this change or later?
6. Is `activity_no_location` a blocker (prevents approval without
   force) or a warning?
7. Share `monthly_cost_limit_usd` with category checks, or a separate
   limit?
