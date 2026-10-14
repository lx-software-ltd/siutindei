# Plan: Catalog versions production recovery

**Status**: Implemented in this branch. Phase 4 production deploy runs when this merges; the stack deploy itself is not part of the change.
**Zone**: red (`backend/db/**`, `.github/workflows/deploy-backend.yml`),
then yellow (`apps/admin_web/src/**`), plus one operator step

## Symptom

The organization "Stanley Main Beach Water Sports Centre"
(`abd5abbe-9280-43fe-b651-fd2ff3a1a116`) was created by a board-catalog
import on 2026-10-12 and changed by a second import on 2026-10-14. The
second import added a Chinese name, replaced the source note, moved the
activity's source category, and added a second location. Those are
tracked fields, so the audit trail shows two states. The admin console
shows a single "Version 1 · Latest" pill with no history.

## Root cause

Three defects stack. Each one needs its own fix; fixing only the
console would hide the other two.

1. **Backfill never terminates for `activity_pricing`.**
   `catalog_backfill_deleted_batch` in `backend/db/catalog_version_backfill.sql`
   picks every `audit_log` DELETE record id that has no
   `catalog_versions` row at version 1. `catalog_backfill_deleted` then
   skips any id that still has a live row or has no `INSERT` audit row,
   and writes nothing for it. The candidate predicate and the writer
   predicate disagree, so the same ids are picked on every call,
   `count` never reaches 0, and `_drain()` in
   `backend/db/alembic/versions/0049_catalog_version_fixes.py` raises
   `RuntimeError: catalog_backfill_deleted_batch did not finish for activity_pricing`
   after `_BATCH_CAP` iterations. Production has pricing rows that were
   deleted before audit logging covered their inserts, which is exactly
   the skipped case.

2. **The failed deploy wedged the stack and the self-heal did not fire.**
   Deploy Backend run 38347521711 (PR #647) committed `0047 → 0048`,
   then failed on `0048 → 0049` about eleven times. CloudFormation
   rolled back and re-invoked `RunMigrations` with the previous Lambda
   bundle, which does not know revision `0048_catalog_versions`, so the
   rollback itself failed and `lxsoftware-siutindei` is in
   `UPDATE_ROLLBACK_FAILED`. `continue_rollback_for_wedged_stacks()` in
   `.github/workflows/deploy-backend.yml` is meant to add
   `--resources-to-skip RunMigrations`, but the "RunMigrations blocked
   the rollback" line never appeared: `describe-stack-resources` either
   failed (its stderr is discarded) or did not report the resource as
   `UPDATE_FAILED`. The plain `continue-update-rollback` then failed as
   well. No backend deploy has succeeded since.

   Production is therefore in a mixed state: `alembic_version` says
   `0048_catalog_versions`; the `0049` triggers and guard are installed;
   live backfill finished for all five tables; deleted backfill finished
   for organizations, locations, and activities only; the four backfill
   helper functions still exist; and the admin Lambda is still the
   pre-#647 bundle.

3. **The console fabricates a version when the API is missing.**
   The admin web was deployed on 2026-10-14 and calls
   `GET /v1/admin/versions`, which the old admin Lambda does not route
   (404). `useCatalogVersion` in
   `apps/admin_web/src/components/admin/version-history.tsx` treats the
   error as an empty list, and `VersionSwitcher` renders a synthetic
   "Version 1 · Latest" row. The user sees a confident wrong answer
   instead of an error.

A fourth, smaller consequence: version 2 of the Stanley organization
was written by the old Lambda, which does not call
`set_import_job_context()`, so its `import_job_id` is `NULL`. The guard
trigger makes committed rows immutable except for `reason` and
`related_id`, so after recovery that row will be labelled with the
importer's account rather than the import file. This is accepted; see
Open questions.

## Goal

Production shows two versions for the Stanley organization and every
other entity edited since 2026-10-13, the `0049` migration completes,
the stack returns to a deployable state, the deploy workflow unwedges
itself the next time this pattern happens, and the console never shows
"Version N · Latest" for a history it could not load.

## Non-goals

- Changing what counts as a tracked field or how versions are numbered.
- Writing tombstones for rows that were deleted before audit logging
  recorded their insert (decision 11 in `catalog-versioning.md` stands).
- Rewriting `import_job_id` on already-committed version rows.
- Preventing admin-web deploys from running ahead of backend deploys
  (tracked as an open question, not part of this fix).

## Phases

Phase 0 is an operator action. Phases 1 and 2 are red and need
explicit approval in chat before any write. Phase 3 is yellow and can
start in parallel once this plan is accepted. Phase 4 is verification.

### Phase 0: unwedge the stack (operator, not agent)

```
aws cloudformation continue-update-rollback \
  --stack-name lxsoftware-siutindei \
  --resources-to-skip RunMigrations \
  --region ap-southeast-1
aws cloudformation wait stack-rollback-complete \
  --stack-name lxsoftware-siutindei --region ap-southeast-1
```

Skipping `RunMigrations` is safe: migrations are forward-only and the
database already holds everything `0048` created. Afterwards confirm
`SELECT version_num FROM alembic_version` returns
`0048_catalog_versions` and that
`catalog_backfill_deleted_batch(text)` still exists (if it was dropped
by hand, `0049` re-creates it anyway).

The workflow's `force_migration_run` input is not needed; Phase 1
changes a file under `backend/db/alembic/versions/`, which changes
`MigrationsHash` and re-triggers `RunMigrations`.

### Phase 1: make the deleted backfill terminate (red)

Files: `backend/db/catalog_version_backfill.sql`,
`backend/db/alembic/versions/0049_catalog_version_fixes.py`,
`tests/test_catalog_versions_triggers.py`.

Tests first, against PostgreSQL, using the existing
`_install_backfill` / `_drop_backfill` / `_rows` helpers next to
`test_backfill_prefers_the_audit_insert`:

- An `audit_log` DELETE row with no matching INSERT row and no live
  row: `catalog_backfill_deleted_batch('organizations')` returns 0 on
  the first call and writes no `catalog_versions` rows.
- An INSERT row followed by a DELETE row with no live row: one call
  returns 1 and leaves version 1 `created` (from the INSERT
  `new_values`) and version 2 `deleted` (from the DELETE `old_values`);
  a second call returns 0.
- A DELETE row whose record still exists (re-created id): the batch
  function does not pick it, because the live backfill owns it.
- A `record_id` that is not a UUID is never picked.

Then change the candidate query in `catalog_backfill_deleted_batch` so
it matches the writer exactly:

```sql
WHERE table_name = etable
  AND action = 'DELETE'
  AND record_id ~* '^[0-9a-f-]{36}$'
  AND EXISTS (
      SELECT 1 FROM audit_log inserted
      WHERE inserted.table_name = etable
        AND inserted.record_id = audit_log.record_id
        AND inserted.action = 'INSERT')
  AND NOT EXISTS (<live row with that id in etable>)
  AND NOT EXISTS (<catalog_versions row at version 1>)
```

The live-row check must be built with `format('%I', etable)` like the
live batch does. `catalog_backfill_deleted` keeps its own guards; they
become redundant rather than wrong.

In `0049_catalog_version_fixes.py`, make `_drain` fail fast instead of
spinning: stop when a call returns the same non-zero count as the
previous call and the number of missing rows (a cheap
`SELECT count(*)` of the candidate query, or a second helper returning
the ids) did not shrink, and include the table, the function, and up
to five sample ids in the `RuntimeError`. Keep the 200-row batches and
the per-batch commit. The revision id does not change.

Editing `0049` in place is acceptable because production is stamped at
`0048` and no environment has `0049` applied; CI's
`tests/test_alembic_revision_contract.py` guards the chain. Adding a
`0050` instead would not help: `0049` would still fail first.

Update `docs/plans/catalog-versioning.md` with one line under
"Review fixes" that names this defect.

### Phase 2: let the deploy workflow unwedge itself (red)

File: `.github/workflows/deploy-backend.yml`,
`continue_rollback_for_wedged_stacks()`.

- Do not discard `describe-stack-resources` stderr. Print it, so an
  IAM denial is visible in the run log.
- Widen the match: treat `RunMigrations` as blocking when its status is
  `UPDATE_FAILED` **or** when the latest stack event for it mentions
  `Can't locate revision`. Query
  `describe-stack-events --max-items 50` filtered on
  `LogicalResourceId=='RunMigrations'`.
- If the first `continue-update-rollback` fails with a message that
  names `RunMigrations`, retry once with
  `--resources-to-skip RunMigrations`.
- After the waiter succeeds, print the resulting stack status, and
  fail the step loudly if it is still not `UPDATE_ROLLBACK_COMPLETE`.

Check that the deploy role is allowed `cloudformation:DescribeStackResources`
and `cloudformation:DescribeStackEvents` on the managed stacks; if the
policy lives in `backend/infrastructure/**`, that edit is also red and
goes in the same approval.

Record the manual recovery command in
`docs/architecture/aws-assets-map.md` next to the existing rollback
caveat so the next operator does not have to rediscover it.

### Phase 3: stop fabricating versions in the console (yellow)

Files: `apps/admin_web/src/components/admin/version-history.tsx`,
`apps/admin_web/tests/components/admin/version-history.test.tsx`,
`apps/admin_web/e2e/fixtures/test-fixtures.ts`, one e2e spec.

Tests first:

- Vitest: when `listEntireCatalogHistory` rejects, `VersionSwitcher`
  renders a disabled "Versions unavailable" control, does not render
  "Latest", and does not open a menu. The manager-mode pill is
  unchanged.
- Vitest: when the call resolves with zero items, the current
  behaviour stays (a single synthetic row labelled with the entity's
  current version).
- Playwright: add a fixture flag that makes `**/admin/versions**`
  return 404 and assert the organizations row shows "Versions
  unavailable" rather than "Version 1 · Latest".

Then:

- `useCatalogVersion` returns `isError` and the error alongside
  `items`, `latestVersion`, and `selectedVersion`.
- `VersionSwitcher` branches on `isError` before building `rows`; the
  synthetic `'current'` row is only created when the query succeeded.
- `catalogLatestVersion` stays as is.
- No change to `api-client-versions.ts` or to the backend.

### Phase 4: deploy and verify

1. Merge Phase 1 and Phase 2 (one pull request or two, both red).
   The push to `main` under `backend/**` starts Deploy Backend. Watch
   the migration Lambda log for `0048 -> 0049` and five
   `catalog_backfill_deleted_batch` drains returning 0.
2. Merge Phase 3. Deploy Admin Web runs.
3. In production, `GET /v1/admin/versions?entity_type=organization&entity_id=abd5abbe-9280-43fe-b651-fd2ff3a1a116`
   returns two rows: version 1 `created` (2026-10-12, import) and
   version 2 `updated` (2026-10-14) with `changed_fields` covering
   `name_zh`, `source_note`, and the organization roll-up from the new
   location and the activity's category change.
4. The console shows "Version 2 · Latest" for that organization with
   both versions in the menu.

## Invariants this change preserves

- Committed `catalog_versions` rows stay immutable except `reason` and
  `related_id` (`catalog_versions_guard`).
- A deleted record gets a tombstone only when `audit_log` holds both
  its INSERT and its DELETE (decision 11).
- Backfill commits every 200 rows and is safe to retry.
- `catalog_tracked()` and the version-bump rules do not change.
- Migrations stay forward-only; `downgrade()` in `0049` stays a no-op.
- The revision chain `0048 -> 0049` is unchanged.
- The manager-mode version pill is unchanged.

## Done when

Phase 1

```
cd backend
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/backend_test \
  pytest tests/test_catalog_versions_triggers.py
pytest tests/test_alembic_revision_contract.py
pre-commit run ruff-format --all-files
```

plus a manual `alembic upgrade head` against a database that was
stamped at `0048`, holds one DELETE-only audit row per table, and has
the triggers from `0049` already installed (mirrors production).

Phase 2

- Paste the edited `continue_rollback_for_wedged_stacks()` body into a
  file under `/tmp` and run `bash -n` on it.
- One Deploy Backend run that reaches `UPDATE_COMPLETE`, and its log
  shows the describe calls without an access error.

Phase 3

```
cd apps/admin_web
npx vitest run tests/components/admin/version-history.test.tsx
npm run lint && npm run typecheck
npx playwright test e2e/organizations.spec.ts
```

Production

- Deploy Backend green; migration log shows `0049` applied once.
- `alembic_version` is `0049_catalog_version_fixes`.
- The versions endpoint returns two rows for the Stanley organization
  and the console shows "Version 2 · Latest".

## Rollback

- Phase 0 is already a rollback; it cannot be undone and does not need
  to be.
- Phase 1: the predicate change is forward-only. If `0049` fails again
  the stack will roll back; Phase 2 makes that recoverable. The data
  written so far is idempotent, so a retry starts where it stopped.
- Phase 2: revert the workflow commit. The manual command in Phase 0
  remains the fallback.
- Phase 3: revert the admin-web commit; the console goes back to the
  synthetic row.

## Open questions

1. Should rows deleted before audit logging covered their insert get a
   single `deleted` tombstone built from `old_values`? Default: no,
   keep decision 11, and skip them. Reopen if reviewers want deletions
   visible for those rows.
2. Edit `0049` in place (chosen, since nothing has applied it) or add
   `0050`? A `0050` only makes sense if someone has a staging database
   stamped at `0049`.
3. The Stanley version 2 row has `import_job_id = NULL` and will show
   the importer's account instead of the import file. Accept, or add a
   narrow guard exception that allows `import_job_id` to go from `NULL`
   to a value? Default: accept.
4. Should Deploy Admin Web check that the admin Lambda bundle is at
   least as new as the commit it is deploying, so the console cannot
   call routes that are not live yet? Out of scope here; worth a
   separate plan.
