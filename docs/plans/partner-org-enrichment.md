# Plan: Partner website enrichment

**Status**: Done
**Zone**: yellow

## Goal

Expose website enrichment to a full-access `crud` partner key, the
partner equivalent of an admin. The partner routes call the same
helpers as `/v1/admin/organizations/{id}/enrichment` and
`/v1/admin/enrichment-settings`. Org-scoped keys and `read` keys
receive `403`.

## Non-goals

- A new API Gateway resource. The routes ride `/v1/partner/{proxy+}`.
- Admin-web UI.
- Schema or seed changes.
- Category-suggestion enrichment.

## Files

- `backend/src/app/api/admin_enrichment.py`
- `backend/src/app/api/partner_auth.py`
- `backend/src/app/api/partner_org_enrichment.py`
- `backend/src/app/api/partner_routes.py`
- `tests/test_partner_org_enrichment.py`
- `docs/api/partner.yaml`
- `docs/architecture/lambdas.md`
- `docs/architecture/security.md`
- `docs/architecture/aws-assets-map.md`
- `docs/architecture/aws-messaging.md`

## Invariants this change preserves

- Admin and importer JWT behavior on the admin enrichment routes.
- Partner organization CRUD when the path has no `enrichment` tail.
- The enrichment queue message stays `enrichment_run_id` plus `stage`.
- A settings change writes an audit row for the caller. An unchanged
  body does not.

## Done when

- `pytest tests/test_partner_org_enrichment.py tests/test_org_enrichment.py tests/test_partner_routes.py`
- `python3 scripts/check_openapi_routes.py`
- `node scripts/check-lambda-docs.mjs`

## Rollback

Revert the pull request. The partner proxy keeps serving other routes.

## Open questions

None. Full-access `crud` includes settings reads and updates.
