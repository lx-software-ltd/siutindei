# Plan: Partner API key rate limit

**Status**: Done
**Zone**: red (approved in chat: fix the review findings)

## Goal

Count `/v1/partner/*` in the existing API WAF. Partner requests send
`x-partner-key`, not `Authorization`, so the signed-in session rule
never counts them. A third rule uses the same 300 requests / 60 seconds
limit and aggregates on `x-partner-key`.

## Non-goals

- A new API Gateway usage plan.
- Changing the limit or the window.
- Counting public search or listing-event routes.

## Files

- `backend/infrastructure/lib/constructs/api-rate-limit.ts`
- `docs/architecture/security.md`
- `docs/architecture/aws-assets-map.md`

## Invariants this change preserves

- Requests without `Authorization` are still not counted by the session rule.
- Requests without `x-partner-key` are not counted by the partner rule.
- A blocked request still gets 429 with the same JSON body.
- WAF logs redact `authorization`, `cookie`, and `x-partner-key`.
- The blocked-requests alarm still uses one alarm. Its metric is the sum of both rate rules, so a partner-key block pages ops too.
- No new CloudFormation resource. The rule is added to the existing web ACL.
