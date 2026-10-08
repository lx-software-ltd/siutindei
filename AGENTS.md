# Agent Operating Instructions

Applies to Cursor agents working in this repository.

## Bootstrap

1. Always-applied constraints are in `.cursor/rules/00-repository-core.mdc`. Path-scoped rules in `.cursor/rules/` attach for the area you edit.
2. Procedures live in `.cursor/skills/*/SKILL.md`: `db-migration`, `admin-api-endpoint`, `admin-crud-screen`, `public-www-section`, `verify-change`, and `cursor-cloud`.
3. `.cursorrules` is a legacy pointer. Do not add rules there.

## Zones

Autonomy follows blast radius. The map is `docs/architecture/zones.md`. The stricter zone wins. If scope grows into a stricter zone, stop and ask.

- **Red.** Plan in chat and wait for explicit approval before any write. A human pairs on the change.
- **Yellow.** Write a short plan under `docs/plans/` from `docs/plans/_template.md`, add or update tests first, then implement. A read-only pass leaves a memo under `docs/research/`.
- **Green.** Implement and verify. Summarise intent in the pull request.

Board agents do not edit red-zone paths and do not commit, push, or open pull requests. The enforcer is `scripts/ci/board_policy.py`. Briefs of `kind: content` stay exempt and may only change `content/**`.

## Cursor Cloud

| Service | Path | Dev command | Port |
| --- | --- | --- | --- |
| Admin web | `apps/admin_web/` | `npm run dev` | 3000 |
| Public website | `apps/public_www/` | `npm run dev -- -p 3100` | 3100 |
| Backend | `backend/` | `pytest tests backend` | n/a |

PostgreSQL is `postgresql+psycopg://postgres:postgres@localhost:5432/backend_test`. Source nvm before Node. Before committing Python, run `pre-commit run ruff-format --all-files`. Read `.cursor/skills/cursor-cloud/SKILL.md` before running services.

## Evidence

A change is done when the `verify-change` skill's checks pass and the pull request template is filled in. Hooks format edits and block destructive shell commands. Cloud agents do not fire the `stop` hook; CI remains the merge gate.

## Hooks

`.cursor/hooks.json` denies force-push, pushes to `main` or `staging`, `git reset --hard`, deleting those refs, `rm -rf` outside `/tmp`, destructive SQL, `cdk deploy` or `destroy`, and `aws delete-*`. It asks before `git commit --amend` and `alembic downgrade`.
