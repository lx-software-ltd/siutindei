# Plan: Clear today's CI warnings that sit in yellow and green code

**Status**: Implemented
**Zone**: yellow

## Goal

Clear the warnings from 9 November 2026 (Hong Kong time, through 17:43)
that sit outside the red zone.

- Replace deprecated SQLAlchemy `ARRAY.Comparator.any()` calls with
  `any_()` so search, schedule lookup, and feedback-label checks keep the
  same `value = ANY(column)` SQL.
- Join the test session with `join_transaction_mode="create_savepoint"`
  so a test's `commit()` and `rollback()` stay inside the fixture
  transaction.
- Set the public site's `turbopack.root` to the monorepo root.
- Load the Vitest config as `vitest.config.mts`, and include `*.mts` in
  the public site typecheck.

## Non-goals

- CloudFormation template validation, `CfnResource.addDependency`, and
  deploy workflows. Those paths are red.
- npm `rimraf@3` / `glob@7` / `inflight` pulled in by `@lhci/cli`'s
  `chrome-launcher`. No compatible parent release drops them.
- Flutter Gradle, Android Gradle Plugin, and Kotlin major upgrades.
- Pinning `ubuntu-latest`. That notice is a GitHub runner announcement,
  and the deploy workflows that use it are red.

## Files

- `backend/src/app/db/queries.py`
- `backend/src/app/db/repositories/schedule.py`
- `backend/src/app/db/repositories/feedback_label.py`
- `tests/conftest.py`
- `tests/test_array_any_deprecation.py`
- `tests/test_db_session_isolation.py`
- `apps/public_www/next.config.ts`
- `apps/public_www/vitest.config.mts`
- `apps/public_www/tsconfig.json`

## Invariants this change preserves

- Compiled SQL stays `value = ANY (column)` for schedule languages and
  feedback-label id arrays.
- A row committed on `db_session` is invisible to a second connection.
- No schema, seed, or API change.
- `turbopack.root` is the directory Next was already selecting.

## Done when

- `pytest tests/test_array_any_deprecation.py tests/test_db_session_isolation.py`
  passes, and the enrichment timeout test emits no `SAWarning`.
- `pytest tests/test_repositories.py::TestActivityScheduleRepository::test_find_by_language`
  passes.
- `npm test`, `npm run lint`, and `npm run typecheck` pass in
  `apps/public_www`, and `tsc` lists `vitest.config.mts`.
- `next dev` on port 3100 does not log the lockfile-root warning.

## Rollback

Revert the commits on this branch. The previous comparator emits the same
SQL. Restoring `Session(bind=connection)` returns the previous join mode.
Removing `turbopack.root` and restoring `vitest.config.ts` returns the
previous frontend warnings.

## Open questions

None.
