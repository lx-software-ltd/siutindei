# Plan: Move the ops alarms into a nested stack

**Status**: Stage 3 implemented; merge only after the stage 2 runbook
**Zone**: red (approved in chat)

## Goal

Free room in the main API stack, which is at CloudFormation's
500-resource limit, by moving the 16 ops CloudWatch alarms into an
`OpsAlarmsStack` nested stack without deleting or recreating them. New
resources, starting with the per-session WAF rate limit, can then live
in the main stack.

## Non-goals

- Moving the ops-alerts topic, its KMS key, or the email subscription.
  Replacing a confirmed email subscription can unsubscribe it.
- Moving the DLQ alarms. They reference their queues.
- Moving API Gateway routes, Lambda functions, or stateful resources.
- Changing any alarm threshold, name, or target.

## Files

Stage 1 (preparation PR):

- `backend/infrastructure/lib/constructs/ops-alarms.ts`
- `backend/infrastructure/lib/constructs/database.ts`
- `backend/infrastructure/lib/constructs/index.ts`
- `backend/infrastructure/lib/api-stack.ts`
- `backend/infrastructure/scripts/ops_alarms_refactor.py` and its tests
- `backend/infrastructure/scripts/assert-existing-db.ts`
- `docs/deployment/ops-alarms-stack-refactor.md`
- `docs/architecture/aws-assets-map.md`

Stage 3 (follow-up PR): `api-stack.ts` builds the alarms inside
`OpsAlarmsStack` and drops the placeholder. The one-off refactor script
and its tests are deleted.

## Invariants this change preserves

- Every alarm keeps its name, metric, threshold, and ops-alerts action.
- Stage 1 changes alarm properties only from references to the same
  resolved literal values.
- The alarms reference nothing but stack-independent pseudo parameters,
  so the refactor needs no nested stack parameters.
- Logical IDs stay the same in the nested stack. They derive from the
  path below the stack, and the alarms' scope is named `OpsAlarms` in
  both places.

## Done when

- `npm run build`, `npm run test:infra`, and `npx cdk synth` pass.
- The synthesized main stack differs from `main` only in the 16 alarms
  (literal values) and the new nested stack resource.
- `scripts/ops_alarms_refactor.py build` moves 16 alarms verbatim when
  given the synthesized templates, and refuses templates with a
  cross-reference.
- Stage 2 runbook completed in production; stage 3 deployed.

## Rollback

- Stage 1: revert and deploy. The alarms go back to references and the
  empty nested stack is deleted.
- Stage 2: a failed execution rolls back automatically. After a
  successful one, reverse it with a second refactor that maps the
  alarms back to the parent.
- Stage 3: revert to stage 1 code only together with a reverse refactor.

## Open questions

None. Scope chosen in chat (option A).
