---
name: cursor-cloud
description: Run and test this repo on a Cursor cloud agent VM.
---

# Cursor cloud

Source Node before npm: `export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh"`.

PostgreSQL is `postgresql+psycopg://postgres:postgres@localhost:5432/backend_test`. Alembic needs `DATABASE_URL`. Local auth is `md5`, not `peer`.

Install backend deps with `pip install --ignore-installed` so Debian packages such as PyJWT do not block the install.

Admin Playwright reuses a server already listening on port 3000 and then skips the mock `NEXT_PUBLIC_*` values. Stop a plain `npm run dev` before `npx playwright test`.

Public www copies `shared/home_wizard/home_wizard_choices.json` into `apps/public_www/src/data/`. The staging search fixture is `shared/fixtures/activity_search_staging.json` (Git LFS). Keep the copies in sync.

`scripts/check-pii.sh` fails when tracked source matches `scripts/pii-denylist.sha256`. The file stores digests only.

Do not file GitHub issues from `NOTE:`, `SECURITY NOTE:`, or `next-env.d.ts` comments.

## Done

The command you needed ran, or you reported the missing tool.
