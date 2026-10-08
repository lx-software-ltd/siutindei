# Plan: Agent harness for siutindei

**Status**: Implemented
**Zone**: red

## Goal

Turn the always-on rulebook into path-scoped rules, short skills, and
checks that fail when a constraint regresses. Draw the red zone to
match this repo, including admin auth and `shared/`. Keep content-kind
board briefs exempt. Leave a research-memo pattern for read-only passes.

## Non-goals

Activating a disabled GitHub ruleset. Adding `CODEOWNERS`. Changing
application behavior, schema, or seed data.

## Files

See the pull request. The zone map is `docs/architecture/zones.md`.
The enforcer is `scripts/ci/board_policy.py`.

## Invariants this change preserves

Board content briefs may only change `content/**` and are not refused
for red-zone names inside that tree. Generic protected names (`auth`,
`payments`, `migrations`, `infra`, `.github`) stay so the lx-software
mirror remains a subset. Secret names, CORS, and the Alembic revision
contract stay as they are.

## Done when

`pytest tests/test_board_policy.py tests/test_agent_harness_checks.py tests/test_alembic_revision_contract.py`
passes, and `python3 scripts/validate_agent_rules.py` passes.

## Rollback

Revert the commits. Deployed Lambdas and the database are unchanged.

## Open questions

None. Admin auth and `shared/` are red. Research memos live under
`docs/research/`. Content-kind briefs stay exempt.
