# Plan: Clear today's CI warnings that sit in yellow code

**Status**: Implemented
**Zone**: yellow

## Goal

Replace deprecated SQLAlchemy `ARRAY.Comparator.any()` calls with `any_()`
so search, schedule lookup, and feedback-label checks keep the same
`value = ANY(column)` SQL without the SQLAlchemy 2.1 deprecation warning.

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
- `tests/test_array_any_deprecation.py`

## Invariants this change preserves

- Compiled SQL stays `value = ANY (column)` for schedule languages and
  feedback-label id arrays.
- No schema, seed, or API change.

## Done when

`pytest tests/test_array_any_deprecation.py` passes with no
`SADeprecationWarning`, and `pytest tests/test_repositories.py::TestActivityScheduleRepository::test_find_by_language`
still passes.

## Rollback

Revert the four files. The previous comparator emits the same SQL.

## Open questions

None.
