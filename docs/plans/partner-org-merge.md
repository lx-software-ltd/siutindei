# Plan: Partner organization merge

**Status**: Done
**Zone**: yellow

## Goal

Expose the existing organization-merge service on the partner API, and
restrict it to a full-access `crud` key (the partner equivalent of an
admin). Org-scoped keys and `read` keys receive `403`. The request and
response stay the same as `POST /v1/admin/org-duplicates/merge`.

## Non-goals

- A new API Gateway resource. The route rides `/v1/partner/{proxy+}`.
- Partner access to duplicate listing, search, or dismiss.
- Admin-web UI or generated admin types.
- Schema or seed changes.

## Files

- `backend/src/app/api/partner_org_merge.py`
- `backend/src/app/api/partner_routes.py`
- `tests/test_partner_org_merge.py`
- `docs/api/partner.yaml`
- `docs/architecture/lambdas.md`
- `docs/architecture/data-quality.md`
- `docs/architecture/security.md`
- `docs/architecture/aws-assets-map.md`

## Invariants this change preserves

- Admin JWT merge at `/v1/admin/org-duplicates/merge` is unchanged.
- Org-scoped partner keys cannot merge organizations they do not own,
  and cannot merge across organizations.
- `read` keys still cannot POST.
- Merge writes keep audit attribution as `api-key:<id>`.

## Done when

- `pytest tests/test_partner_org_merge.py tests/test_partner_routes.py`
- `python3 scripts/check_openapi_routes.py`
- `node scripts/check-lambda-docs.mjs`

## Rollback

Revert the pull request. The partner proxy keeps serving other routes.

## Open questions

None. The admin merge body already supports `dry_run`.
