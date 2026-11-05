# Plan: Partner organization rejection

**Status**: Done
**Zone**: yellow

## Goal

Let a full-access `crud` partner key reject one organization at
`POST /v1/partner/organizations/{id}/reject`. The reason, notes, and
listing status match an admin reject decision. The actor is the
authorizer `userSub`, or `api-key:<id>` when `userSub` is omitted.

## Non-goals

- Approve, reopen, force, or bulk field edits.
- A new API Gateway resource. The route rides `/v1/partner/{proxy+}`.
- Letting an organization-scoped key or a `read` key reject, including
  when the key's organization is the target.
- Schema or seed changes.

## Files

- `backend/src/app/api/admin_org_review_actions.py`
- `backend/src/app/api/partner_org_reject.py`
- `backend/src/app/api/partner_routes.py`
- `tests/test_partner_org_reject.py`
- `docs/api/partner.yaml`
- `docs/architecture/lambdas.md`
- `docs/architecture/security.md`
- `docs/architecture/aws-assets-map.md`

## Invariants this change preserves

- Admin approve, reject, reopen, and bulk review.
- Partner organization CRUD, merge, and enrichment.
- A reject still requires a known reason and stores it only while the
  organization is rejected.
- Organization-scoped keys and `read` keys still receive `403`,
  including when the target is the key's own organization.
- A path with anything after `reject` is `404` and writes nothing.
- Invalid notes and listing status are `400` before the lookup.
- The organizations audit trigger records the partner actor. Cleanup
  removes those rows.

## Done when

`pytest tests/test_partner_org_reject.py` passes.
`python3 scripts/check_openapi_routes.py` and
`node scripts/check-lambda-docs.mjs` pass.

## Rollback

Revert this pull request. Admin rejection keeps working.
