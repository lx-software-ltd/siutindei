# Plan: Three-way merge for catalog imports

**Status**: Implemented on this branch. Revision `0059` is red.
**Zone**: red (one Alembic revision), then yellow for backend and admin

## Problem

The importer compares a file row with catalog version 1 and decides
per row. When the file differs from version 1 and `allow_updates` is
true, every field the file carries is written over the live row. The
`admin_edits_overwritten` warning tells the admin afterwards; it does
not stop the write. When `allow_updates` is false, the row is skipped
whole, so a genuine source change (a new phone number, a moved venue,
a changed schedule) never lands either.

The row is the wrong unit. The admin edits a few fields; the source
changes a few fields; they rarely overlap. Deciding per field, with a
record of what the source last said, keeps accurate admin work and
still lets genuine changes through.

## Decisions

1. The base of the comparison is what the source last said for that
   record, not version 1. A new table `import_baselines` stores the
   normalised compare shape of the file row the last time any import
   saw that entity, including dry runs that are later confirmed live,
   skipped rows, and rows that produced proposals. Version 1 stays
   the fallback for entities that have no baseline row yet, which is
   today's behaviour.
2. Each field present in the file is decided on its own. With base
   `B`, live `L`, and file `F`, after the same normalisation
   `catalog_version_shape` already applies:

   | Source | Admin | Decision |
   | --- | --- | --- |
   | `F = B` | any | keep `L`; the source did not change |
   | `F ≠ B` | `L = B` | apply `F`; a genuine change nobody edited |
   | `F ≠ B` | `L = F` | nothing; the admin already made that change |
   | `F ≠ B` | `L ≠ B`, `L ≠ F` | conflict; record a proposal, keep `L` |

   Fields the file omits are never touched, as today.
3. Conflicts go to a queue, not to the row. A new table
   `import_change_proposals` holds one pending row per
   `(entity_type, entity_id, field)` with the base, current, and
   proposed values, the import job, and `status` `pending`,
   `applied`, or `dismissed`. A later import with a different
   proposed value for the same field replaces the pending row. A
   later import whose value equals the baseline raises nothing.
4. Accept writes the field through the existing admin update path,
   so `catalog_versions`, `audit_log`, and the version bump work
   unchanged and the history shows the admin as the actor. Dismiss
   marks the proposal and writes nothing. Either way the baseline
   already holds `F`, so the same source value does not come back as
   a conflict on the next run.
5. Imports · Settings gains two choices. `existing_rows` is `apply`
   (today: file wins), `merge` (this plan, the new default), or
   `propose` (every change to an existing row is queued, nothing is
   auto-applied). `approved_organizations` is `merge` or `propose`
   (default `propose`): an organization whose `review_status` is
   `approved` has been vetted, so even clean source changes wait for
   a decision there. Organizations still `pending_review` merge
   automatically. No new column on `organizations`.
6. `allow_updates=false` keeps its meaning: an existing row is left
   as it is and no proposal is written. It is the hard off switch.
   The board import calls the API without the flag, so it follows
   the settings above. The admin chooses the policy from Settings,
   not the caller.
7. Child identity gains a fallback through the baseline. An activity
   whose stored name the admin changed is still found when the file
   name matches the normalised name in its baseline row, so a rename
   no longer makes the next import create a duplicate. Organizations
   already have this through version-1 lookup; the baseline lookup
   runs before it. Locations fall back the same way on address.
8. Dry run follows the same path and writes nothing: the result shows
   which fields would be applied and which would be proposed, so the
   board Preview is an exact forecast.
9. Rows that match the baseline on every field stay `unchanged`. A
   row with at least one auto-applied field is `updated`. A row whose
   only changes became proposals is `proposed`, a new status. A row
   can be `updated` and still carry `Proposed: description, website`
   in its warnings.

## Goal

A board import never overwrites a field an admin has changed since
the source last reported it. A field the source changed and nobody
edited is applied. Where both changed, the admin sees the three values
side by side and decides in one click. Approved organizations can be
set so that every source change waits for that click.

## Non-goals

- Field-level locks or a per-organization "protected" flag. The
  `approved_organizations` setting covers the vetted case without a
  new column. Revisit if admins ask for finer control.
- Changing `catalog_versions`, its triggers, or the version-1
  lookups. They stay as the fallback and as history.
- Merging inside a text field (word-level diff). A field is one unit.
- Partner API access to the queue. Partner reads do not change.
- Undoing an accepted proposal. History already keeps the previous
  version.
- Scheduling or batching the queue by email.

## Files

Red, waits for explicit approval before any write:

- `backend/db/alembic/versions/0059_import_merge.py`:
  `import_baselines` (`entity_type`, `entity_id`, `org_id`, `source`,
  `payload` jsonb, `import_job_id`, `created_at`, `updated_at`;
  unique `(entity_type, entity_id)`; expression indexes on
  `lower(trim(payload->>'name'))` and `lower(trim(payload->>'address'))`
  scoped by `org_id`), `import_change_proposals` (`id`,
  `entity_type`, `entity_id`, `org_id`, `field`, `base_value`,
  `current_value`, `proposed_value` jsonb, `import_job_id`, `status`,
  `decided_by`, `decided_at`, `created_at`, `updated_at`; unique
  partial index on `(entity_type, entity_id, field)` where
  `status = 'pending'`; check on `status` and `entity_type`), and two
  columns on `import_settings` with check constraints. Grants follow
  `name_fix_proposals`. `seed_data.sql` does not change; the tables
  start empty and the settings columns have server defaults.

Yellow, backend:

- `backend/src/app/db/models/import_baseline.py`,
  `import_change_proposal.py`, `import_settings.py`, and
  `models/__init__.py`.
- `backend/src/app/db/repositories/import_baseline.py` and
  `import_change_proposal.py`.
- `backend/src/app/services/import_merge.py`: the per-field decision
  table, built on `catalog_version_shape` for normalisation. Pure
  functions, SQLite-testable.
- `backend/src/app/services/catalog_version_match.py`: `_live_status`
  and `_status_for_snapshot` load the baseline before version 1 and
  return a field plan instead of a row status.
- `backend/src/app/api/admin_imports_version.py` and
  `admin_imports_upsert.py`: apply only the fields the plan allows,
  write proposals and the baseline, and report `proposed`.
- `backend/src/app/api/admin_imports_children.py`,
  `admin_imports_schedule.py`: same for locations, activities,
  pricing, and schedules. A schedule's `weekly_entries` is one field.
- `backend/src/app/services/import_names.py` and
  `admin_imports_lookups.py`: baseline name fallback for activities,
  address fallback for locations.
- `backend/src/app/api/admin_import_changes.py`: list, accept,
  dismiss, bulk accept per organization; dispatched from `admin.py`.
- `backend/src/app/services/import_settings.py`: read the two new
  fields; PUT validates them.
- `backend/src/app/api/admin_imports_results.py` and
  `admin_imports_jobs.py`: `proposed` count in `summary`.

Yellow, admin web:

- `apps/admin_web/src/lib/api-client-import-changes.ts`,
  `admin-query-keys.ts`, `types/admin.ts`, generated types.
- `components/admin/import-changes-panel.tsx`: new Data quality tab
  "Import changes", table-first with expand-in-place per the
  `admin-crud-screen` skill. Columns: organization, record, field,
  current, proposed, import job, when. Expanded row shows base,
  current, and proposed with the version-history actor for the
  current value. Actions: Accept, Keep mine, Accept all for this
  organization.
- `components/admin/imports-settings-panel.tsx`: the two selects with
  one line of help each.
- `components/admin/imports-panel.tsx` and
  `org-review/import-history-panel.tsx`: `proposed` count and the
  `Proposed:` warning.
- `components/admin/organization-workspace-title.tsx`: a pending
  proposals count next to the version badge, linking to the tab
  filtered to that organization.
- `e2e/import-changes.spec.ts`, `e2e/imports.spec.ts`,
  `e2e/fixtures`.

Green, docs and API:

- `docs/api/admin.yaml`: `/v1/admin/import-changes`,
  `/v1/admin/import-changes/{id}/accept`, `.../dismiss`,
  `/v1/admin/import-changes/accept-all`; `proposed` on import
  results and summary; the two settings fields. `npm run
  generate:api` output committed.
- `docs/architecture/data-quality.md` (import semantics paragraph),
  `database-schema.md`, `lambdas.md`, `decisions.md` (new decision
  "Import three-way merge"), `docs/imports/*` wording.

## Invariants this change preserves

- `review_status`, `reviewed_at`, `reviewed_by`, `review_notes`, and
  `manager_id` are never written by an import. Accept goes through
  the admin path and may not change them either.
- `allow_updates=false` still skips existing rows and still creates
  missing children.
- A removed organization or child is still not recreated; the
  version-1 tombstone rules run before the merge.
- Owner-set listing `status` still wins over the importer's status.
- The same `object_key` with the same `dry_run` and `allow_updates`
  still returns the stored job.
- Dry runs write nothing: baselines and proposals roll back with the
  rest of the transaction.
- `catalog_versions` history is unchanged; an accepted proposal is
  one admin version, an auto-applied field is one import version.
- Entities with no baseline behave exactly as today, so the first
  import after deploy does not reinterpret the catalog.

## Tests first

- `tests/test_import_merge.py`, SQLite: the four-row decision table
  per entity type; omitted fields untouched; schedule entries as one
  field; normalisation (timezone, six-decimal pins, name cleanup)
  on all three sides; `propose` mode queues clean changes; approved
  organization queues clean changes under `propose`.
- `tests/test_import_baselines.py`: baseline written on `unchanged`,
  `skipped`, `updated`, and `proposed`; version-1 fallback when no
  baseline; renamed activity found through the baseline; dry run
  leaves no baseline.
- `tests/test_import_change_proposals.py`: pending row replaced by a
  newer proposed value; dismissed value does not return while the
  source still says it; accept writes one admin version and marks
  `applied`; accept-all requires an organization or an import job; a proposal
  whose entity was deleted is dismissed on read.
- `tests/test_import_versions.py` and `tests/test_admin_imports.py`
  updated: `test_changed_source_updates_and_warns_when_admin_edited`
  becomes "changed source on an admin-edited field proposes and
  keeps the edit"; a new case for "changed source on an untouched
  field applies while the edited field stays".
- `tests/test_alembic_revision_contract.py` for `0059`.
- Playwright: Import changes tab accept and keep, settings selects,
  `proposed` in import results.

## Done when

- `pytest tests/test_import_merge.py tests/test_import_baselines.py tests/test_import_change_proposals.py tests/test_import_versions.py tests/test_admin_imports.py tests/test_import_retry.py tests/test_import_names.py tests/test_alembic_revision_contract.py`
- `TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/backend_test pytest tests/test_catalog_versions_triggers.py tests/test_import_baselines.py`
- `alembic upgrade head` then `seed_data.sql` on a fresh database;
  `alembic downgrade 0058_entry_order_idx` on a copy.
- `python3 scripts/check_openapi_routes.py`,
  `python3 scripts/check_python_file_length.py`,
  `node scripts/check-lambda-docs.mjs`.
- `npm run lint`, `npm run typecheck`, and
  `npx playwright test e2e/import-changes.spec.ts e2e/imports.spec.ts e2e/org-review.spec.ts`
  in `apps/admin_web`.
- `pre-commit run ruff-format --all-files` before the Python commit.
- A browser pass: import a file; edit an activity's description and
  an organization's phone; change the file so the source moves the
  phone and the activity's age range; re-import. The age range is
  applied, the phone appears in Import changes with both values, the
  description is untouched. Accept the phone and confirm one admin
  version. Set the organization to approved, change the file again,
  and confirm the change waits in the queue.

## Rollout

1. Ship with `existing_rows = merge` and
   `approved_organizations = propose` as server defaults. The first
   import after deploy writes baselines for every row it sees and
   decides against version 1 as today, so the behaviour change is
   gradual and the dry run shows it before anything is written.
2. Keep `SiutindeiBoardCatalogImportEnabled` false until one board
   dry run against production data shows the expected `proposed`
   rows and no unexpected `updated` rows.

## Rollback

`alembic downgrade 0058_entry_order_idx` drops both tables and the
two settings columns; pending proposals are lost, baselines are lost
and the importer falls back to version 1. Setting
`existing_rows = apply` restores today's behaviour without a rollback.

## Open questions

- Should a pending proposal block the public listing of that field?
  Proposed answer: no. The live value is the admin's and stays
  public; the queue is admin-only.
- Should `approved_organizations = propose` also queue new children
  (a new activity under an approved organization)? Proposed answer:
  no. Creating is not overwriting, and a new activity is already
  `pending_review` through its organization's review flow.
- Should accept-all exist on the import job (accept every proposal
  this job raised)? Proposed answer: yes if it is cheap after the
  per-organization version; otherwise a follow-up.
