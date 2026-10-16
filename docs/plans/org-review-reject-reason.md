# Plan: Reject reason and "added since rejected" signal

**Status**: Implemented
**Zone**: red (migration under `backend/db/**`); the rest is yellow

## Goal

An admin who rejects an organization records why. "Not relevant"
(for example adult-only yoga) is one of the reasons. Catalog can
filter rejected organizations by reason.

When a rejected organization later gains an activity, Catalog shows
it as a warning so an admin can look again.
The admin then either reopens it or rejects it again, which clears the
warning. Imports still never change review state.

## Non-goals

- A fourth `review_status` value. `rejected` keeps meaning "not
  released". The reason explains it.
- Automatically reopening an organization from an import. The review
  gate decision in `docs/architecture/decisions.md` and the
  catalog-versioning invariant ("`review_status` and approval are
  untouched by any import") stay as they are.
- Detecting children's activities from the age range. Board-flat
  imports synthesise 0–18 (`default_age_range`), so the age range
  cannot tell adult and child classes apart.
- Turning on `ORG_REVIEW_GATE_ENABLED` or changing public search.
- Reasons on activities or venues. Review stays per organization.
- Backfilling reasons for organizations already rejected. They show
  as "No reason".

## Design

### Data

New nullable column `organizations.review_reason` (text).

- Allowed values: `not_relevant`, `duplicate`, `poor_data`, `other`.
  CHECK `organizations_review_reason_check`:
  `review_reason IS NULL OR review_reason IN (...)`.
- CHECK `organizations_review_reason_rejected_check`:
  `review_reason IS NULL OR review_status = 'rejected'`. A reason
  never sits on a pending or approved row.
- No index. Rejected rows are few, and `review_status` is already
  indexed (`organizations_review_status_idx`).
- Not added to `catalog_tracked()` exclusions in
  `backend/db/catalog_version_triggers.sql`. It is a review field, and
  review fields bump the catalog version, the same as `review_notes`.
  No trigger change.

### Decision rules

In `backend/src/app/api/admin_org_review_actions.py`, `_apply_decision`:

- `reject` requires `reason`, one of the allowed values. A missing or
  unknown reason returns 400 with `field="reason"`. Approve and
  reopen return 400 when a reason is sent.
- `approve` and `reopen` clear `review_reason`. A `reason` on these
  actions returns 400.
- Rejecting an already rejected organization is allowed. It updates
  the reason and `reviewed_at`. This is how an admin dismisses the
  "added since rejected" warning without adding new state.
- Bulk `reject` takes the same `reason` and applies it to every
  selected organization. `set_fields` does not accept `review_reason`;
  it stays a decision-only field, so the CHECK cannot be violated
  through bulk fields.
- The existing optional `status` on a decision is unchanged. The
  console uses it to also set listing status to `hidden` (see UI).

### "Added since rejected" warning

New warning issue code `activity_added_since_rejected`:

- The organization has `review_status = 'rejected'`, a stored
  `review_reason` (any allowed value), and at least one activity with
  `activities.created_at > organizations.reviewed_at`. A rejected row
  with no reason does not warn.
- Severity `warning`, entity `organization`. Message:
  "New activity added after this organization was rejected".
- Python check in `collect_issues` (`backend/src/app/services/org_review.py`)
  and SQL predicate in `_issue_predicates`
  (`backend/src/app/services/org_review_sql.py`). These must agree.
  The existing parity test (`summarize_catalog == summarize_snapshots`)
  covers it once a fixture triggers the code.
- Warning codes outside `BLOCKER_ISSUE_CODES` are filtered in Python
  after loading every matching organization (`_needs_warning_scan`).
  This code has a cheap SQL predicate, so add it to a new
  `SQL_FILTERABLE_ISSUE_CODES` (blockers plus this code). The list
  path then filters it in SQL and pages normally.
- Any write path that creates an activity counts: import, admin CRUD,
  manager routes, and partner keys. A merge that moves activities
  keeps their original `created_at`, so it does not trigger the
  warning. This is accepted.
- `snapshot_for_org` already drives the Readiness card, so the warning
  shows there with no extra wiring. `openIssue` in
  `organization-readiness.tsx` routes it to the Activities section for
  that organization.

### Import feedback

In `backend/src/app/api/admin_imports_upsert.py`, on the
create-activity branch of `upsert_activity`, when the parent
  organization is rejected and has a reason, append a warning to the
  activity result: "organization was rejected; new activity flagged
  for review". Dry runs report it too. No state changes.

### List filter and summary

- `GET /v1/admin/org-review` gains `review_reason` (enum of the
  allowed values, plus `none` for rejected rows without a reason).
  Parsed in `_parse_filters`, applied in
  `_load_filtered_organizations`.
- `review_reason` is added to `_serialize_queue_item` and
  `_serialize_organization`.
- `OrgReviewSummary` gains `by_review_reason` (counts over rejected
  rows, key `none` for null), computed in `summarize_catalog` and
  `summarize_snapshots`.
- Export: add `review_reason` next to `review_notes` in
  `admin_imports_export.py`. Import pops and ignores it, the same way
  as `review_notes`, with no warning.

### Admin UI

- Readiness card (`organization-readiness.tsx`): Reject opens a small
  inline form under the action bar, not a one-click action. It has:
  - Reason select (required): Not relevant, Duplicate, Poor data,
    Other.
  - Notes (optional, existing `notes`).
  - "Hide from public listing" checkbox, checked by default for every
    reason. It sends `status: 'hidden'`. This matters while the review
    gate is off.
  - Confirm and Cancel buttons (`secondary`).
- When the organization is rejected, the card shows the reason and
  notes as read-only values.
- Catalog (`review-queue-panel.tsx`):
  - Bulk Reject opens the same form, reusing the pattern in
    `bulk-fields-dialog.tsx`.
  - New filter "Reject reason", shown only when Review is set to
    Rejected, so the filter bar does not grow for everyone.
  - Add `activity_added_since_rejected` to `ISSUE_OPTIONS` as
    "Added since rejected".
  - KPI card "Added since rejected", from
    `by_issue.activity_added_since_rejected`.
  - Review status cell shows "Rejected · Not relevant" as one
    `StatusBadge` label. This keeps one fact per cell under the
    admin-web table rule.
- Client: `api-client-org-review.ts` types and request bodies.
  Regenerate `src/types/api-admin.generated.ts` with
  `npm run generate:api`.

## Files

Red (needs human approval before any write):

- `backend/db/alembic/versions/0054_org_review_reason.py`: add the
  column and both CHECKs. Downgrade drops them. `down_revision` is
  `0053_translation_fixes`.
- `backend/db/seed/seed_data.sql`: no change expected. The column is
  nullable, and seed organizations are `approved` or default to
  pending, so both CHECKs hold. Confirm and record this in the PR.

Yellow:

- `backend/src/app/db/models/organization.py`: column and CHECKs.
- `backend/src/app/services/org_review.py`: `REVIEW_REASONS`, warning
  check, `summarize_snapshots` reason counts.
- `backend/src/app/services/org_review_sql.py`: predicate,
  `SQL_FILTERABLE_ISSUE_CODES`, `by_review_reason`.
- `backend/src/app/api/admin_org_review_actions.py`: reason parsing
  and decision rules.
- `backend/src/app/api/admin_org_review.py`: filter, serializer,
  SQL-filterable issue path.
- `backend/src/app/api/admin_resource_organization.py`: serialize
  `review_reason`.
- `backend/src/app/api/admin_imports_upsert.py`: import warning.
- `backend/src/app/api/admin_imports_importer.py`: pop `review_reason`.
- `backend/src/app/api/admin_imports_export.py`: export field.
- `docs/api/admin.yaml`: `OrgReviewDecisionRequest.reason`,
  `OrgReviewBulkRequest.reason`, list `review_reason` parameter,
  `OrgReviewListItem.review_reason`, `Organization.review_reason`,
  `OrgReviewSummary.by_review_reason`, import schema note.
- `apps/admin_web/src/lib/api-client-org-review.ts`
- `apps/admin_web/src/types/api-admin.generated.ts` (generated)
- `apps/admin_web/src/components/admin/organization-readiness.tsx`
- `apps/admin_web/src/components/admin/org-review/review-queue-panel.tsx`
- `apps/admin_web/src/components/admin/org-review/reject-form.tsx`
  (new, shared by Readiness and bulk Reject)

Tests (written first):

- `tests/test_org_review.py`
- `tests/test_admin_imports.py`
- `tests/test_catalog_versions_triggers.py` (PostgreSQL)
- `tests/test_alembic_revision_contract.py` (existing, must pass)
- `apps/admin_web/tests/components/admin/organization-readiness.test.tsx`
- `apps/admin_web/tests/components/admin/reject-form.test.tsx` (new)
- `apps/admin_web/e2e/org-review.spec.ts` and
  `apps/admin_web/e2e/fixtures/test-fixtures.ts`

Green docs:

- `docs/architecture/database-schema.md`: column, CHECKs, seed
  assessment line.
- `docs/architecture/decisions.md`: extend "Organization review gate"
  with reasons and the warning, and restate that imports never reopen
  an organization.

## Test cases

Backend (`tests/test_org_review.py` unless noted):

- Reject with `reason=not_relevant` stores it, with `reviewed_at`
  and `reviewed_by`.
- Reject without a reason stores null.
- Unknown reason returns 400 with `field="reason"`.
- Approve or reopen with a `reason` returns 400.
- Approve and reopen clear an existing reason.
- Rejecting again updates the reason and `reviewed_at`.
- Bulk reject applies the reason to each organization. A bulk
  `set_fields` with `review_reason` returns "Unsupported bulk fields".
- The list filters `review_reason=not_relevant` and `none`.
- Warning present: rejected as `not_relevant`, with an activity whose
  `created_at` is after `reviewed_at`.
- Warning absent in each of these cases: the activity is older than
  `reviewed_at`; the reason is `duplicate`; the organization is
  pending or approved; the organization was rejected again after the
  new activity.
- `issue=activity_added_since_rejected` pages in SQL and returns the
  same rows as the Python check.
- The `summarize_catalog == summarize_snapshots` parity holds with a
  fixture that triggers the new code and has rejected rows with and
  without a reason.
- Import (`tests/test_admin_imports.py`), on an organization rejected
  as not relevant: a new activity is created and its result carries
  the warning; `review_status` and `review_reason` are unchanged;
  `allow_updates` false behaves the same; a file `review_reason` is
  ignored.
- Export includes `review_reason`.
- PostgreSQL (`tests/test_catalog_versions_triggers.py`): setting
  `review_reason` bumps the organization version, and
  `changed_fields` includes it.
- The DB rejects a reason on a non-rejected row (CHECK).

Frontend:

- Readiness: Reject reveals the form; Confirm is disabled until a
  reason is picked; Not relevant pre-checks "Hide from public
  listing"; the request body has `action`, `reason`, `notes`, and
  `status`; a rejected organization shows its reason.
- Catalog e2e: bulk reject with Not relevant, filter by reason, and
  the "Added since rejected" issue filter shows a fixture row.

## Invariants this change preserves

- Imports never change `review_status`, and now never change
  `review_reason` either. New imported organizations start
  `pending_review` with no reason.
- `review_status` keeps its three values. The public search gate and
  `v_catalog_health` are unchanged.
- Approve still refuses on blockers unless `force` is set. The new
  code is a warning and never blocks.
- Review fields still bump the catalog version. Bookkeeping columns
  still do not.
- `summarize_catalog` and `summarize_snapshots` still return equal
  counts.
- Existing decision and bulk calls without `reason` behave as today.
- Skip-existing imports still create missing children on a skipped
  organization.

## Done when

- `pytest tests/test_org_review.py tests/test_admin_imports.py tests/test_alembic_revision_contract.py`
- `pytest tests/test_catalog_versions_triggers.py` against PostgreSQL
  (`DATABASE_URL` set)
- `alembic upgrade head`, then load `seed_data.sql`, then
  `alembic downgrade -1` and `upgrade head` again, on the local
  database
- `python3 scripts/check_openapi_routes.py`
- `node scripts/check-lambda-docs.mjs`
- In `apps/admin_web`: `npm run generate:api` (committed output),
  `npm run lint`, `npm run typecheck`, `npx vitest run`, and
  `npx playwright test e2e/org-review.spec.ts`
- `pre-commit run ruff-format --all-files` before the Python commit
- The PR states the seed decision and links this plan

## Delivery

This ships as one pull request. The column is unused without the
decision API, and the API cannot store a reason without the column.

## Rollback

Revert the pull request, then `alembic downgrade` to
`0053_translation_fixes`. That drops the column and both CHECKs.
Reasons are lost, but `catalog_versions` snapshots keep them. The
hooks ask before `alembic downgrade`. Downgrade only after the
previous application code is running, because the new code reads the
column.

## Open questions

Resolved:

- Reasons are `not_relevant`, `duplicate`, `poor_data`, and `other`.
- The API requires a reason on reject.
- The warning covers every stored reason, not only `not_relevant`.
  A rejected organization with no reason does not warn.
- "Hide from public listing" defaults on for every reason.
- Catalog has an "Added since rejected" count as well as the issue
  filter.
