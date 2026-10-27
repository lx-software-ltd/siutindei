# Plan: Replace an open category review from a later scan

**Status**: Done
**Zone**: yellow

## Goal

A later category check must be able to store a verdict for an activity
that already has a pending review. The older pending review is
dismissed in the same transaction, then the new verdict is inserted.
Storing a batch that still fails is retried, and the third receive
counts the batch as failed so the scan run can finish.

## Non-goals

- Redriving or purging the dead-letter queue. The running worker still
  has the old code.
- Changing which activities the candidate query selects.
- Changing auto-apply rules or the review decision API.

## Files

- `docs/plans/category-review-one-pending.md`
- `backend/src/app/db/models/category_scan.py`
- `backend/src/app/services/category_suggestions/scan_apply.py`
- `backend/src/app/services/category_suggestions/scan.py`
- `docs/architecture/category-suggestions.md`
- `docs/architecture/database-schema.md`
- `tests/test_category_scan.py`
- `tests/test_category_scan_guards.py`

## Invariants this change preserves

- One activity still has at most one `pending` review
  (`activity_cat_reviews_one_pending`, already created in revision
  `0051`).
- A review already stored for the same scan run is left as it is.
- Confirm, auto-apply, and propose still use the same thresholds.
- OpenRouter failures still retry and record the batch only on the
  third receive.

## Done when

- `pytest tests/test_category_scan.py tests/test_category_scan_guards.py tests/test_category_discover.py tests/test_category_recheck_followups.py`
- `pre-commit run ruff-format --all-files`

## Rollback

Revert the commit. No migration and no seed change. After this code is
deployed, redrive or purge
`lxsoftware-siutindei-category-suggestion-dlq`.

## Open questions

None. The newer verdict replaces the older pending review, which is
what revision `0051` did with duplicate pending rows.
