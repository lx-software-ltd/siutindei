# Plan: Per-session API rate limit

**Status**: Implemented
**Zone**: red (approved in chat)

## Goal

Stop one signed-in browser from exhausting `SiutindeiAdminFunction`. A
regional WAF web ACL on the API Gateway `prod` stage blocks a session
that sends more than 300 requests in 60 seconds to `/v1/admin/*`,
`/v1/manager/*`, or `/v1/user/*`. The session key is the
`Authorization` header, the same key the JWT authorizers cache on.

## Non-goals

- Public search, partner, and listing-event routes.
- Raising Lambda concurrency or changing the existing alarms.
- Per-user API Gateway API keys or usage plans.

## Files

- `backend/infrastructure/lib/constructs/api-rate-limit.ts`
- `backend/infrastructure/lib/constructs/index.ts`
- `backend/infrastructure/lib/api-stack.ts`
- `docs/architecture/security.md`
- `docs/architecture/aws-assets-map.md`

## Invariants this change preserves

- Requests without an `Authorization` header are not counted. Preflights and public routes pass through.
- The mobile API key and its usage plan are unchanged.
- A blocked request gets 429 with a JSON `error` body and the admin web CORS origin, so the console shows the message.
- WAF logs redact `authorization` and `cookie`, and the log group is KMS-encrypted.

## Done when

`npm run build` and `npx cdk synth` pass in `backend/infrastructure`. The
synthesized stack has the web ACL, the stage association, the logging
configuration, and the blocked-requests alarm on the ops-alerts topic.

## Rollback

Revert this change and deploy. The web ACL, association, alarm, and key
are removed; the log group is retained.

## Open questions

None. Limit, scope, and block mode were chosen in chat.
