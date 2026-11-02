---
name: cursor-cloud
description: Run and test this repo on a Cursor cloud agent VM.
---

# Cursor cloud

Source Node before npm: `export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh"`.

PostgreSQL is `postgresql+psycopg://postgres:postgres@localhost:5432/backend_test`. Alembic needs `DATABASE_URL`. Local auth is `md5`, not `peer`.

Run pytest from the repo root with both of these. Database-backed tests error with a usage message when `TEST_DATABASE_URL` is unset. SQLite is not supported.

```bash
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/backend_test \
  PYTHONPATH=backend/src:backend \
  pytest
```

Install backend deps with `pip install --ignore-installed` so Debian packages such as PyJWT do not block the install.

Admin Playwright reuses a server already listening on port 3000 and then skips the mock `NEXT_PUBLIC_*` values. Stop a plain `npm run dev` before `npx playwright test`.

`scripts/codegen/sync-home-wizard-choices.sh` copies `shared/home_wizard/home_wizard_choices.json` into `apps/public_www/src/data/` and `apps/siutindei_app/assets/home_wizard/`. `scripts/codegen/sync-activity-search-staging-fixture.sh all` copies `shared/fixtures/activity_search_staging.json` (Git LFS) into `backend/fixtures/` and `apps/public_www/public/fixtures/`. `sync-home-wizard-choices.sh --check` verifies the wizard copies.

`scripts/check-pii.sh` fails when tracked source matches `scripts/pii-denylist.sha256`. The file stores digests only.

Do not file GitHub issues from `NOTE:`, `SECURITY NOTE:`, or `next-env.d.ts` comments.

## Done

The command you needed ran, or you reported the missing tool.
