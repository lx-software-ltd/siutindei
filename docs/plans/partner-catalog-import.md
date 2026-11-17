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
  `parent_verified_at` on organisations this request created. An
  organisation that is already verified is omitted from the response
  list. A name match this request did not create is left unchanged.
- `approve=true` approves those same new organisations with the
  existing release rules, and only while `review_status` is
  `pending_review`. A blocker leaves that organisation pending and
  lists the issues. A rejected organisation stays rejected. An
  organisation that is already approved is omitted from `approved`.
  It does not force approval and does not roll back the import.
- `dry_run=true` validates, rolls back, and stores the job. It cannot
  be combined with the two flags above.
- Flags accept `true`, `false`, `1`, and `0`. Letter case does not
  matter.
- The live route commits a running import job first, then commits the
  organisations, flags, and completed job together. The same request
  returns that job. A repeat while it is running returns 409. A
  running job older than 150 seconds is run again. The job source is
  `partner`. A data-quality run and category
  enrichment are queued the same way as the Imports page.
- `failed` and `skipped` are also returned at the top of the response.

Hours and map pins stay in the file. This route does not invent them.

## Non-goals

- Changing how `POST /v1/admin/imports` writes. Import history gains
  a Partner API label for jobs this route stores.
- Letting the file set `parent_verified`, `parent_verified_at`, or
  `review_status`. Those fields stay unknown on an organisation row
  and are ignored.
- An S3 object or `allow_updates`. A second post of a changed file
  matches by name and does not duplicate the organisation. The same
  file and flags return the stored job instead of writing again.
- Organization-scoped keys, `read` keys, and `force`.
- A new API Gateway resource. The route rides `/v1/partner/{proxy+}`.
- Schema or seed changes.

## Files

- `backend/src/app/api/partner_imports.py`
- `backend/src/app/api/partner_imports_flags.py`
- `backend/src/app/api/partner_routes.py`
- `tests/test_partner_imports.py`
- `docs/api/partner.yaml`
- `docs/architecture/lambdas.md`
- `docs/architecture/security.md`
- `docs/architecture/aws-assets-map.md`
- `docs/architecture/data-quality.md`
- `docs/architecture/decisions.md`
- `docs/api/admin.yaml`
- `apps/admin_web/src/lib/import-job-results.ts`
- `apps/admin_web/src/lib/api-client-imports.ts`

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
- The flags apply only to organisations this request created. A
  matched or rejected organisation is left alone. Failed and skipped
  rows are left alone and are listed on the response. A match owned
  by another manager is still `managed by provider`.
- Public search hides an eat listing until the organisation is
  parent-verified. Approval filters search only when the review gate
  is on.

## Done when

`pytest tests/test_partner_imports.py tests/test_partner_org_approve.py tests/test_admin_imports.py`
passes. `python3 scripts/check_openapi_routes.py` and
`node scripts/check-lambda-docs.mjs` pass.

## Rollback

Revert this pull request. Admin import and partner approval keep
working.

## Open questions

None.
