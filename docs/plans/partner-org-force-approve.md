# Plan: Partner organization force approval

**Status**: Implemented
**Zone**: yellow

## Goal

Let a full-access `crud` partner key pass `force: true` on
`POST /v1/partner/organizations/{id}/approve`, matching an admin
approve decision. Release blockers still refuse the release when
`force` is omitted or false.

## Non-goals

- Changing the reject route. Reject still refuses `force`.
- Reopen or bulk review on the partner API.
- Letting an organization-scoped key or a `read` key force-approve.
- Schema or seed changes.

## Files

- `backend/src/app/api/admin_org_review_actions.py`
- `backend/src/app/api/partner_org_approve.py`
- `tests/test_partner_org_approve.py`
- `docs/api/partner.yaml`
- `docs/architecture/decisions.md`
- `docs/architecture/data-quality.md`

## Invariants this change preserves

- Admin approve, reject, reopen, and bulk review, including admin
  `force`.
- Partner reject still refuses `force`.
- Omitted or `false` `force` still returns `400` with `issues` while
  blockers remain.
- Organization-scoped keys and `read` keys still receive `403`.
- Invalid `force` (not a boolean), notes, listing status, reason, and
  action are `400` before the lookup.
- Approve still clears `review_reason`.

## Done when

`pytest tests/test_partner_org_approve.py` passes.
`python3 scripts/check_openapi_routes.py` and
`node scripts/check-lambda-docs.mjs` pass.

## Rollback

Revert this pull request. Partner approval without `force` and partner
rejection keep working.

## Open questions

None.
