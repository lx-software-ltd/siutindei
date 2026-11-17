# Plan: Partner catalog import

**Status**: Done
**Zone**: yellow

## Goal

Let the current full-access `crud` partner key run a catalog import
file, including `docs/imports/eat-with-kids-visited.json` once that
file is on `main`.

`POST /v1/partner/imports` accepts the same JSON as
`POST /v1/admin/imports`. The body is the file. Flags are query
parameters, so the file does not need new fields.

- `manager_id` replaces a missing or placeholder
  `default_manager_id`. When it is omitted, `BOARD_CATALOG_MANAGER_ID`
  is used. A value that is not that catalog manager is rejected
  before any write. A placeholder with neither a query value nor the
  environment variable is rejected the same way.
- `mark_parent_verified=true` sets `parent_verified` and
  `parent_verified_at` on organisations this file created or matched
  and left unchanged.
- `approve=true` approves those same organisations with the existing
  release rules. A blocker leaves that organisation pending and lists
  the issues. It does not force approval and does not roll back the
  import.
- `dry_run=true` validates and rolls back. It cannot be combined with
  the two flags above.

Hours and map pins stay in the file. This route does not invent them.

## Non-goals

- Changing `POST /v1/admin/imports` or the Imports page.
- Letting the file set `parent_verified`, `parent_verified_at`, or
  `review_status`. Those fields stay unknown on an organisation row
  and are ignored.
- An S3 object, an `import_jobs` row, or `allow_updates`. A second
  post matches by name and does not duplicate the organisation.
- Organization-scoped keys, `read` keys, and `force`.
- A new API Gateway resource. The route rides `/v1/partner/{proxy+}`.
- Schema or seed changes.

## Files

- `backend/src/app/api/partner_imports.py`
- `backend/src/app/api/partner_routes.py`
- `tests/test_partner_imports.py`
- `docs/api/partner.yaml`
- `docs/architecture/lambdas.md`
- `docs/architecture/security.md`
- `docs/architecture/aws-assets-map.md`
- `docs/architecture/data-quality.md`
- `docs/architecture/decisions.md`

## Invariants this change preserves

- Admin and importer imports, including the placeholder manager check.
- Import still cannot set the parent-verified flag or the review
  status from organisation fields.
- Release blockers still refuse approval unless `force` is passed, and
  this route does not accept `force`.
- A full-access `crud` key remains the only partner key that can
  approve an organisation.
- Organization-scoped keys and `read` keys receive `403` before the
  database opens.
- The flags apply only to organisations this file created or left
  unchanged. Failed and skipped rows are left alone. A match owned by
  another manager is still `managed by provider`.

## Done when

`pytest tests/test_partner_imports.py tests/test_partner_org_approve.py tests/test_admin_imports.py`
passes. `python3 scripts/check_openapi_routes.py` and
`node scripts/check-lambda-docs.mjs` pass.

## Rollback

Revert this pull request. Admin import and partner approval keep
working.

## Open questions

None.
