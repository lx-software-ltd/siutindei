# Agent work zones

Autonomy follows blast radius. A person draws this map. A change that
touches more than one zone uses the stricter zone. If implementation
spreads into a stricter zone, stop and ask.

Board briefs of `kind: content` stay exempt from this map. They may
only change `content/**`, including paths that would otherwise be red
because a directory name matches. The enforcer is
`scripts/ci/board_policy.py`.

## Red

Plan in chat and wait for explicit approval before any write. A human
pairs on the change.

- `backend/db/**`
- `backend/infrastructure/**`
- `backend/lambda/auth/**`
- `backend/lambda/authorizers/**`
- `backend/lambda/aws_proxy/**`
- `backend/src/app/auth/**`
- `backend/src/app/services/aws_proxy.py`
- `backend/src/app/services/openrouter_client.py`
- `apps/admin_web/src/app/auth/**`
- `apps/siutindei_app/lib/features/auth/**`
- `shared/**`
- `.github/workflows/deploy-*.yml`
- `.github/workflows/promote-*.yml`
- `.github/workflows/board-*.yml`
- `.github/workflows/verify-rulesets.yml`
- `scripts/deploy/**`
- `scripts/ci/**`
- `scripts/check-pii.sh`
- `scripts/check_pii.py`
- `scripts/pii-denylist.sha256`
- `scripts/test_check_pii.py`
- `.cursor/hooks.json`
- `.cursor/hooks/**`
- `.pre-commit-config.yaml`

`.github/**` is also refused by the board policy, because workflow
edits ship with the same blast radius as a deploy.

## Yellow

Write a short plan from `docs/plans/_template.md` before editing. Add
or update tests first, then implement.

- Remaining `backend/src/**` and `backend/lambda/**`
- `apps/admin_web/src/**` outside the red auth routes
- `apps/siutindei_app/**` outside the red auth feature
- `docs/api/**`

## Green

Implement and verify. Summarise intent in the pull request.

- `apps/public_www/**` outside deploy scripts
- `docs/**` outside `docs/api/**`
- Test-only edits that do not sit on a red path

Hooks still format edits and block destructive commands in every zone.
CI remains the merge gate.
