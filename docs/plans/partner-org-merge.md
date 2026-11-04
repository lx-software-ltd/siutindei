# Plan: Partner organization merge

**Status**: Done
**Zone**: yellow

## Goal

Expose organization merge on the partner API at
`POST /v1/partner/organization-merges`. A full-access `crud` key is the
partner equivalent of an admin. Org-scoped keys and `read` keys receive
`403`. Admin and partner share one request helper. A repeat of a
completed merge does not write again. Media keys that remain after
commit are logged.

## Non-goals

- A new API Gateway resource. The route rides `/v1/partner/{proxy+}`.
- Partner access to duplicate listing, search, or dismiss.
- Admin-web UI or generated admin types.
- Schema or seed changes.

## Files

- `backend/src/app/api/partner_org_merge.py`
- `backend/src/app/api/partner_routes.py`
- `backend/src/app/api/admin_org_duplicates.py`
- `backend/src/app/services/org_merge.py`
- `backend/src/app/services/org_merge_media.py`
- `tests/test_partner_org_merge.py`
- `tests/test_org_merge.py`
- `tests/test_org_merge_media.py`
- `docs/api/partner.yaml`
- `docs/architecture/lambdas.md`
- `docs/architecture/data-quality.md`
- `docs/architecture/security.md`
- `docs/architecture/aws-assets-map.md`

## Invariants this change preserves

- Admin JWT merge stays at `/v1/admin/org-duplicates/merge` and uses the same request helper.
- Org-scoped partner keys cannot merge organizations they do not own,
  and cannot merge across organizations.
- `read` keys still cannot POST.
- Merge writes keep audit attribution as `api-key:<id>`.

## Done when

- `pytest tests/test_partner_org_merge.py tests/test_partner_routes.py tests/test_org_merge.py tests/test_org_merge_media.py tests/test_partner_location_fixes.py tests/test_partner_activity_categories.py`
- `python3 scripts/check_openapi_routes.py`
- `node scripts/check-lambda-docs.mjs`

## Rollback

Revert the pull request. The partner proxy keeps serving other routes.

## Open questions

None. The admin merge body already supports `dry_run`.
