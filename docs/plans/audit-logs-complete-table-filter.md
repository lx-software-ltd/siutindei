# Plan: Complete A–Z Audit logs table filter

**Status**: Accepted
**Zone**: yellow

## Goal

The Audit logs Table filter lists every table that can appear in
`audit_log`, and the names are sorted A–Z after **All tables**.

Today the admin dropdown is an older subset (and still names dropped
tables), while the API whitelist is a different subset. Filtering by a
missing table is rejected; rows for those tables only show under All
tables.

## Non-goals

- Adding audit triggers to tables that are not audited
  (`listing_events`, `catalog_versions`, data-quality scans, and the
  other product tables without an `*_audit_trigger`).
- Changing stored `audit_log` rows or the list query when no table
  filter is set.
- Adding a new API to discover tables at runtime.

## Files

- `docs/plans/audit-logs-complete-table-filter.md`
- `apps/admin_web/src/lib/audit-tables.ts`
- `apps/admin_web/src/components/admin/audit-logs-panel.tsx`
- `apps/admin_web/tests/lib/audit-tables.test.ts`
- `apps/admin_web/e2e/audit-logs.spec.ts`
- `backend/src/app/api/admin_audit.py`
- `tests/test_admin_audit_tables.py`
- `docs/architecture/audit-logging.md`

## Invariants this change preserves

- **All tables** still means no `table` query parameter.
- A selected table still goes to `GET /v1/admin/audit-logs?table=…`.
- Dropped tables (`organization_access_requests`,
  `organization_suggestions`) stay out of the filter. Historical rows
  remain visible under All tables.
- `listing_events` and `catalog_versions` stay out of the filter.
- Sensitive fields are still redacted in API responses.

## Done when

- The Table filter options are **All tables** plus the audited names
  in A–Z order.
- The API accepts each of those names and rejects unknown names.
- Playwright `audit-logs.spec.ts` asserts the option list.
- `npm test`, `npm run lint`, and `npm run typecheck` pass in
  `apps/admin_web`.
- `pytest tests/test_admin_audit_tables.py` passes.

## Rollback

Revert the pull request.

## Open questions

None.
