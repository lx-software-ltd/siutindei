# Plan: Catalog versioning

**Status**: Implemented, with review fixes in revision `0049_catalog_version_fixes`
**Zone**: red (Alembic revisions), then yellow for backend and admin

## Review fixes

Committed history rows stay immutable. A guard trigger allows an open
transaction to finish its snapshot, and later transactions may change
only `reason` and `related_id`, or strip contact fields when an admin
forgets a removed record. `merged` cannot be overwritten. The app and
admin roles lose table-wide `UPDATE`. Snapshot writes from triggers go
through definer functions. Deletes are limited to the current
transaction so a dry-run can drop its own rows.

History for one entity is ordered by version and the console follows
the cursor, so version 1 stays reachable. The import warning names an
admin, an earlier import, or another catalog change. A file that
matches version 1 keeps later edits and says so. Version-1 lookup and
merge-by-name run in SQL. Child edits lock the organization, then the
activity, before the flush. A child roll-up does not move the parent's
`updated_at`. Removed activities, locations, pricing, and schedules can
be forgotten from the organization history so a later import can create
them. Forgetting a record also strips contact fields from its snapshots.

Backfill no longer uses `session_replication_role` or disables triggers.
Revision `0049` fills missing history in batches of 200 and commits each
batch, so a retry continues where it stopped. Catalog triggers no-op
while that flag is set; audit triggers keep running. The deleted-row
batch only picks a real uuid whose earliest INSERT audit row has
`new_values` and whose row is gone, and the drain stops when the next
batch starts with the same id. A delete with no usable INSERT still
gets no tombstone.

Decisions below are approved: review fields bump the version, pricing
and schedule changes bump the parent activity, a changed file overwrites
admin edits with a warning, backfill uses `audit_log`, and a merged
organization is recognized by name.

## Decisions

1. Every catalog row (`organizations`, `locations`, `activities`,
   `activity_pricing`, `activity_schedule`) gets an integer `version`
   that starts at 1 when the row is created or imported. The
   organization also gets `media_version` for its media set
   (`media_urls` and `logo_media_url`).
2. One new table, `catalog_versions`, keeps one row per entity per
   version: the snapshot of that version, who wrote it, which import
   job wrote it, and a `deleted` tombstone when the row is removed.
   The table has no foreign key to the catalog tables, so version 1
   and the tombstone survive a delete and a merge.
3. Bumps happen in PostgreSQL triggers, like `audit_log`. Triggers see
   every write path: admin CRUD, manager routes, partner CRUD keys,
   imports, merge, name and location fix apply, category auto-assign,
   and raw `UPDATE` statements. Application code never computes a
   version.
4. One version per entity per transaction. An import that creates an
   organization with ten activities, pricing, and schedules commits
   the organization at version 1. A later admin request that edits
   the organization and two activities commits version N+1 once.
5. The organization version is a roll-up. A change to a location,
   activity, join, pricing row, schedule, or schedule entry under the
   organization bumps the organization too. Child rows also carry
   their own version. A pricing row, schedule, schedule entry, or
   venue join bumps the parent activity as well.
6. Bookkeeping columns do not bump a version: `updated_at`,
   `version`, `media_version`, `name_key`, `last_imported_at`,
   `import_job_id`, `status_changed_at`. A review decision does bump:
   `review_status`, `reviewed_at`, `reviewed_by`, and `review_notes`.
   Listing `status` bumps, because the public sees it. These columns
   stay in `audit_log` either way.
7. Snapshots are the raw row (`to_jsonb(NEW)` minus the excluded
   columns). A schedule snapshot embeds its entries. An activity
   snapshot embeds its `location_ids`. The import comparison builds a
   normalised compare shape from the snapshot in Python, so the
   trigger stays simple and the comparison rules live in one tested
   module.
8. Imports compare the incoming row with version 1, not with the
   current row. Version 1 is what the file produced the first time, so
   an unchanged source row is recognised whether the admin has since
   edited, approved, or deleted the organization or activity. The
   import result gains a status `unchanged`.
9. A removed organization or activity is never recreated by an import
   whose row matches version 1. A removed row whose source has since
   changed is also not recreated; it is reported with a warning so an
   admin decides. A restore action is a follow-up, not part of this
   plan.
10. `audit_log` stays as it is. It is forensic, per table row, has a
    recommended retention delete, and lacks `org_id` on child rows.
    `catalog_versions` is the product feature and is read by the
    importer and the console.
11. The migration backfills every existing row to version 1 with its
    current state. Where `audit_log` still holds the original
    `INSERT` for that row, the backfill prefers that `new_values` as
    version 1 and writes the current state as version 2 when it
    differs. Rows deleted before this feature get a tombstone only
    when `audit_log` has both the `INSERT` and the `DELETE`.
    Organizations imported before this feature may therefore carry
    admin edits in version 1; the plan accepts that.

## Goal

An admin can see which version an organization, its media, its
locations, activities, pricing, and schedules are on, open the history
of each, and see what changed between versions and who changed it. A
re-run of an import file writes nothing for rows that match version 1,
including rows that were later edited or deleted, and still creates
rows that are new to the file.

## Non-goals

- Restoring a deleted organization from its tombstone.
- A `reimport_removed` import flag that recreates removed rows.
- Pruning version history or a retention policy for
  `catalog_versions`.
- Exposing version history on the partner API. Partner reads gain
  the read-only `version` field only.
- Optimistic locking (`If-Match` on `version`) on admin writes.
- Changing merge. Merge still deletes the source organization; the
  tombstone records `merged_into`.
- A stable source id on activities. Activity identity stays
  organization plus normalised name, as the import does today.
- Diffing media file contents. Media is compared by URL list.

## How a version bump works

Trigger set, all in revision `0048_catalog_versions`:

- `BEFORE UPDATE` on each catalog table: when a tracked column
  differs and `NEW.version = OLD.version`, set
  `NEW.version = OLD.version + 1` and `NEW.updated_at = now()`. On
  `organizations`, also bump `media_version` when `media_urls` or
  `logo_media_url` differ. A caller that sets `version` itself (the
  roll-up below) is not bumped twice.
- `AFTER INSERT OR UPDATE OR DELETE` on each catalog table: upsert the
  `catalog_versions` row for `(entity_type, entity_id, version)` with
  the snapshot, `action`, `txid`, `user_id` from
  `app.current_user_id`, `request_id`, and `import_job_id` from a new
  session variable `app.current_import_job_id`. The upsert key means
  the snapshot is the end-of-transaction state when several statements
  touch the same row.
- `AFTER INSERT OR UPDATE OR DELETE` on `locations`, `activities`,
  `activity_locations`, `activity_pricing`, `activity_schedule`, and
  `activity_schedule_entries`: when no `catalog_versions` row for the
  parent organization exists with the current `txid`, run
  `UPDATE organizations SET version = version + 1 WHERE id = org_id`.
  Entries bump their schedule; joins bump their activity. Creating the
  organization in the same transaction already wrote a `txid` row, so
  children created with it leave it at version 1.
- `AFTER DELETE` writes `action = 'deleted'` at `version + 1` with the
  final snapshot. A cascade delete of an organization writes
  tombstones for every child. The child roll-up update then matches
  zero organization rows, which is fine.
- Dry-run imports flush inside the transaction and roll back, so their
  version rows roll back too. `persist_import_change` already deletes
  in-transaction `audit_log` rows as a guard; the same guard covers
  `catalog_versions`.
- The organization merge service annotates the tombstone it just
  caused with `reason = 'merged'` and `related_id = survivor_id` after
  `session.flush()`.

Side effect worth naming: no code path updates `updated_at` on these
five tables today (server default only, no `onupdate`, no trigger).
The `BEFORE UPDATE` trigger fixes that. The location sweep orders by
`updated_at`, so sweep order becomes meaningful.

## Table: catalog_versions

- `id` uuid primary key
- `entity_type` text: `organization`, `media`, `location`,
  `activity`, `pricing`, `schedule`
- `entity_id` uuid, no foreign key
- `org_id` uuid, no foreign key, filled for every type
- `version` integer
- `action` text: `created`, `updated`, `deleted`
- `snapshot` jsonb
- `changed_fields` text[] (null for `created` and `deleted`)
- `txid` bigint
- `user_id` text, `request_id` text, `import_job_id` uuid (no FK)
- `reason` text, `related_id` uuid (merge annotation)
- `created_at` timestamptz

Indexes: unique `(entity_type, entity_id, version)`; `(org_id,
created_at)`; `(txid, entity_type, org_id)`; and version-1 lookup
expressions over the snapshot: `lower(trim(snapshot->>'name'))` for
organizations and activities, `snapshot->>'place_id'`,
`snapshot->>'source_id'`, and `lower(trim(snapshot->>'address'))`
for locations, each partial on `version = 1`.

Grants: `siutindei_admin` and `siutindei_app` get `SELECT, INSERT,
UPDATE`, matching `audit_log`, because the trigger runs as the caller.

Seed: `seed_data.sql` does not change. `version` has server default 1
and the triggers write version-1 rows for the seed inserts. Each seed
statement is its own transaction, so a later child insert bumps the
organization past version 1. The new table is left empty by the seed
and filled by triggers.

## Import comparison

A new module `backend/src/app/services/catalog_versions.py` owns the
compare shape and the lookups. The importer calls it after today's
normalisation (vetting columns, truncation, flat-org expansion, name
cleanup) and before any write, so the two sides are compared after the
same preparation.

Compare shapes, built the same way from an incoming row and from a
version-1 snapshot:

- Organization: normalised name, description, name and description
  translations, the nine contact and social columns, `media_urls`
  (ordered), `logo_media_url`, `place_id`, `status`, `source`,
  `source_id`, `source_url`, `source_note`, `description_source`,
  and `website`. A file that omits `website` keeps the version-1
  value. A file that includes a different `website` does not match.
  Not `manager_id`: imports never write it on update and the catalog
  manager can change between files.
- Activity: normalised name, description, translations, `age_min`
  and `age_max`, `source_url`, `source_note`, and
  `source_category_name`. Not `category_id`, because a label resolved
  to Pending categorisation in version 1 and to a real category later
  is a taxonomy change, not a source change.
- Location: normalised address, `area_id`, `lat` and `lng` to six
  decimals, `place_id`.
- Pricing: location address, `pricing_type`, `amount`, `currency`,
  `sessions_count`, `free_trial_class_offered`.
- Schedule: location address, sorted `languages`, sorted UTC entry
  tuples. UTC on both sides makes the file timezone irrelevant.
- Media: ordered `media_urls` and `logo_media_url`.

Version-1 candidates for an incoming organization come from
`catalog_versions` where `version = 1` and the snapshot matches
`place_id`, then `source` plus `source_id`, then normalised name, in
that order, the same as today's live match. Live organizations are
still matched first by today's code; the version lookup adds removed
organizations and renamed ones.

Decision matrix for an organization row:

| Version-1 match | Compare shape | Live row | Result |
| --- | --- | --- | --- |
| yes | equal | exists | `unchanged`; children still evaluated |
| yes | equal | deleted | `unchanged`, warning `removed`; children skipped |
| yes | differs | exists, `allow_updates` true | `updated` to version N+1 |
| yes | differs | exists, `allow_updates` false | `skipped` as today |
| yes | differs, current row also differs from v1 | exists, `allow_updates` true | `updated`, warning `admin_edits_overwritten` |
| yes | differs | deleted | `skipped`, warning `removed_since_import` |
| no | — | matched by today's rules | today's behaviour |
| no | — | none | `created` at version 1 |

Activities use the same matrix inside their organization, keyed by
normalised name and by the cleaned name that `find_cleaned_activity`
already tries. Locations, pricing, and schedules use their identity
keys above. An activity new to the file on a live organization is
still created. Nothing is created under a removed organization.

The importer sets `SET LOCAL app.current_import_job_id` next to the
audit context so version rows carry the job. Retry and dry run use the
same path. `summary` and each result gain the `unchanged` count and
status; `allow_updates` keeps its meaning.

## Admin

- Organization screen title shows a `v{N}` badge after the status
  badges (`OrganizationWorkspaceTitle`). The editor gets read-only
  `Version` and a `History` disclosure (`AdminDisclosure`) that lists
  versions newest first: when, actor email (same Cognito lookup as
  Audit Logs), source (import job link, admin, partner key, merge),
  and changed fields. Selecting a version shows that snapshot
  read-only. The form above still edits the live row and writes a new
  version.
- Media screen header shows `Media v{N}` and the same history list
  limited to `entity_type = media`.
- Locations, Activities, Pricing, and Schedules tables add a
  `Version` column with `priority='tertiary'` and the same read-only
  value and history disclosure in the expanded editor.
- Catalog gains a filter `Changed since import` with values Any,
  Unchanged (version 1), Changed (version above 1), and a column
  showing the version. Removed organizations are not listed here;
  that is the restore follow-up.
- Imports results and Import history show `unchanged` next to
  `created` and `updated`, and show `removed` warnings per row. A dry
  run therefore previews exactly what a live run would write.
- Manager dashboard shows the badge and version column read-only. No
  history for managers in this plan.
- Audit Logs panel does not list `catalog_versions`; it is not audited.

## API

- `docs/api/admin.yaml`: `version` on `Organization`, `Location`,
  `Activity`, `Pricing`, `Schedule`; `media_version` on
  `Organization`; import result `status` enum gains `unchanged`;
  summary counts gain `unchanged`; new `GET /v1/admin/versions` with
  `entity_type`, `entity_id`, `org_id`, cursor, and limit, and
  `GET /v1/admin/versions/{id}`. The admin greedy `{proxy+}` already
  routes these to the admin Lambda, so `api-stack.ts` does not change.
- `docs/api/partner.yaml`: read-only `version` on organization and
  activity reads.
- `npm run generate:api` output committed with the spec change.

## Files

Red, waits for explicit approval before any write:

- `backend/db/alembic/versions/0048_catalog_versions.py`: columns,
  table, triggers, and grants. It follows `0047_org_website`.
- `backend/db/alembic/versions/0049_catalog_version_fixes.py`:
  immutability grants and the batched backfill.

Yellow, backend:

- `backend/src/app/db/models/organization.py`, `location.py`,
  `activity.py`: `version`, `media_version`.
- `backend/src/app/db/models/catalog_version.py` and
  `backend/src/app/db/models/__init__.py`.
- `backend/src/app/db/repositories/catalog_version.py`.
- `backend/src/app/db/audit.py`: `set_audit_context` accepts
  `import_job_id` and sets the session variable.
- `backend/src/app/services/catalog_versions.py`: compare shapes,
  version-1 lookup, decision helper.
- `backend/src/app/api/admin_imports_upsert.py`,
  `admin_imports_importer.py`, `admin_imports_children.py`,
  `admin_imports_items.py`, `admin_imports_results.py`,
  `admin_imports.py`: call the decision helper, `unchanged` status,
  job id in session context.
- `backend/src/app/api/admin_resource_*.py` serializers: `version`
  and `media_version`.
- `backend/src/app/api/admin_versions.py` and the dispatch in
  `admin.py`.
- `backend/src/app/api/partner_routes.py`: `version` on reads.
- `backend/src/app/services/org_merge.py`: tombstone annotation.
- `backend/src/app/api/admin_imports_utils.py`: dry-run guard covers
  `catalog_versions`.

Yellow, admin web:

- `apps/admin_web/src/lib/api-client-versions.ts`,
  `admin-query-keys.ts`, `types/admin.ts`, generated types.
- `components/admin/organization-workspace-title.tsx`,
  `components/shared/organizations-panel.tsx`, `locations-panel.tsx`,
  `activities-panel.tsx`, `pricing-panel.tsx`, `schedules-panel.tsx`,
  `components/admin/media-panel.tsx`: badge, column, history
  disclosure.
- `components/admin/version-history.tsx` (new, shared disclosure and
  diff view).
- `components/admin/org-review/review-queue-panel.tsx`: filter and
  column.
- `components/admin/imports-panel.tsx`,
  `org-review/import-history-panel.tsx`: `unchanged` and `removed`.
- `e2e/organizations.spec.ts`, `locations.spec.ts`,
  `activities.spec.ts`, `pricing.spec.ts`, `schedules.spec.ts`,
  `media.spec.ts`, `imports.spec.ts`, `org-review.spec.ts`, and
  `e2e/fixtures`.

Green, docs:

- `docs/architecture/database-schema.md`, `audit-logging.md`,
  `data-quality.md` (import semantics paragraph), `decisions.md`
  (new decision "Catalog versioning"), `docs/imports/*` wording.

## Invariants this change preserves

- Imports never write `manager_id` on update. Skip mode still leaves
  an existing row unchanged and still imports missing children.
- The same `object_key` with the same `dry_run` and `allow_updates`
  still returns the stored job.
- Dry runs still write nothing after rollback, including version rows.
- `review_status` and approval are untouched by any import. A review
  decision bumps the organization version.
- `organization_merges` forwarding by `source_id` and `place_id` still
  resolves to the survivor before any version-1 lookup runs.
- Public search, `v_catalog_health`, and the partner search are not
  affected; no new column is read there.
- Seed inserts and `alembic upgrade head` still run in order.

## Tests first

- `tests/test_catalog_versions_triggers.py`, PostgreSQL only
  (`pytest.skip` on SQLite): create gives version 1 and a `created`
  row; a tracked update gives version 2 and `changed_fields`; a
  bookkeeping-only update does not bump; child rows created in the
  organization's transaction leave it at version 1; a child change in
  a later transaction bumps the organization once; media change bumps
  `media_version` and `version`; delete writes a tombstone; cascade
  delete writes child tombstones; merge annotates `merged_into`;
  `updated_at` moves on a tracked update.
- `tests/test_catalog_versions_compare.py`, SQLite: compare shapes
  are equal for the same row from a snapshot and from a file,
  including timezone-shifted schedules, six-decimal pins, Chinese
  name translations, and a category label that later resolved.
- `tests/test_import_versions.py`, SQLite with version rows inserted
  directly: identical file re-run writes nothing and reports
  `unchanged`; re-run after delete does not recreate and warns
  `removed`; changed source on an unedited live row updates to
  version 2; file equal to version 1 after an admin edit leaves the
  edit in place; activity under a removed organization is not
  created; new activity on a live organization is created; retry
  keeps the stored flag.
- `tests/test_admin_imports.py` and `tests/test_import_retry.py`
  updated for the `unchanged` status and summary.
- `tests/test_alembic_revision_contract.py` for the revision id.
- Playwright specs above, with fixtures aligned to the spec.

## Done when

- `pytest tests/test_catalog_versions_compare.py tests/test_import_versions.py tests/test_admin_imports.py tests/test_import_retry.py tests/test_org_merge.py tests/test_alembic_revision_contract.py`
- `TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/backend_test pytest tests/test_catalog_versions_triggers.py`
- `alembic upgrade head` then `seed_data.sql` on a fresh database, and
  `alembic downgrade 0045_hk_neighbourhoods` on a copy.
- `python3 scripts/check_openapi_routes.py` and
  `node scripts/check-lambda-docs.mjs`
- `npm run lint`, `npm run typecheck`, and
  `npx playwright test e2e/organizations.spec.ts e2e/media.spec.ts e2e/imports.spec.ts e2e/org-review.spec.ts e2e/activities.spec.ts e2e/locations.spec.ts e2e/pricing.spec.ts e2e/schedules.spec.ts`
  in `apps/admin_web`
- `pre-commit run ruff-format --all-files` before the Python commit
- A browser pass: import a file, edit an activity, re-import the same
  file, confirm the edit stays and the result says `unchanged`;
  delete an organization, re-import, confirm it is not recreated.

## Order of work

The approved implementation lands together. Catalog history is
`0048_catalog_versions`, after `0047_org_website`. Review fixes are
`0049_catalog_version_fixes`.

## Rollback

`alembic downgrade 0046_deleted_org_import` drops the triggers, the
table, and the columns; version history is lost. Reverting the
importer returns to live-row matching. Admin changes are front-end
only.

## Open questions

None. Review fields bump the version. Pricing and schedules bump the
parent activity. When the file and the admin have both changed a live
row, `allow_updates` lets the file win and records
`admin_edits_overwritten`. Backfill prefers the `audit_log` insert.
A merge snapshot name resolves to the survivor. Forgetting a deleted
organization marks its tombstones `forgotten` so that import can
create the identity again. `0047_org_website` already exists on main,
so catalog history is `0048_catalog_versions`.
