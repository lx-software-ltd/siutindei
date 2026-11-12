# Plan: Partner organization approval

**Status**: Done
**Zone**: yellow

`force` on this route is covered by
`docs/plans/partner-org-force-approve.md`.

## Goal

Let a full-access `crud` partner key approve one organization at
`POST /v1/partner/organizations/{id}/approve`. Notes and listing status
match an admin approve decision. Release blockers still refuse the
release. The actor is the authorizer `userSub`, or `api-key:<id>` when
`userSub` is omitted.

## Non-goals

- Changing the reject route.
- Reopen, force, bulk review, or a reason on approve.
- A new API Gateway resource. The route rides `/v1/partner/{proxy+}`.
- Letting an organization-scoped key or a `read` key approve, including
  when the key's organization is the target.
- Schema or seed changes.

## Files

- `backend/src/app/api/admin_org_review_actions.py`
- `backend/src/app/api/partner_org_approve.py`
- `backend/src/app/api/partner_routes.py`
- `tests/test_partner_org_approve.py`
- `docs/api/partner.yaml`
- `docs/architecture/lambdas.md`
- `docs/architecture/security.md`
- `docs/architecture/aws-assets-map.md`
- `docs/architecture/data-quality.md`
- `docs/architecture/decisions.md`

## Invariants this change preserves

- Admin approve, reject, reopen, and bulk review.
- Partner reject, organization CRUD, merge, and enrichment.
- Approve still clears `review_reason` and stays blocked while release
  blockers remain. `force` stays on the admin console.
- Organization-scoped keys and `read` keys still receive `403`,
  including when the target is the key's own organization.
- A path with anything after `approve` is `404` and writes nothing.
- Invalid notes, listing status, reason, and action are `400` before
  the lookup.
- The organizations audit trigger records the partner actor. Cleanup
  removes those rows.

## Done when

`pytest tests/test_partner_org_approve.py` passes.
`python3 scripts/check_openapi_routes.py` and
`node scripts/check-lambda-docs.mjs` pass.

## Rollback

Revert this pull request. Admin approval and partner rejection keep
working.

## Open questions

None.
