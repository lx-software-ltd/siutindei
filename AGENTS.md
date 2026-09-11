# Agents

## Board agent constraints

Board / Cursor Actions runners treat the task brief as **acceptance
criteria**. Do not expand scope past the brief.

Never modify files matching:

- `**/auth/**`
- `**/payments/**`
- `**/migrations/**`
- `infra/**`
- `.github/**`

Evaluate both old and new path names (renames count). Leave auth,
payments, migrations, infrastructure, and GitHub workflow changes to an
owner. Do not commit, push, or open pull requests; the workflow does
that after tests.

## Cursor Cloud specific instructions

### Services overview

| Service | Directory | Runtime | Purpose |
|---------|-----------|---------|---------|
| Python backend | `backend/` | Python 3.12 | Lambda handlers, DB migrations, tests |
| Admin web | `apps/admin_web/` | Node.js 24 (npm) | Next.js admin SPA |
| Public website | `apps/public_www/` | Node.js 24 (npm) | Next.js static marketing site |
| CDK infrastructure | `backend/infrastructure/` | Node.js 24 (npm) | AWS CDK IaC |
| Flutter app | `apps/siutindei_app/` | Flutter stable | Mobile app (not set up in cloud) |

### Running services

- **Admin web dev server**: `cd apps/admin_web && npm run dev` (port 3000)
- **Public www dev server**: `cd apps/public_www && npm run dev` (port 3000)
- **PostgreSQL**: `service postgresql start` then connect at `postgresql+psycopg://postgres:postgres@localhost:5432/backend_test`

### Lint / test / build (run before commit)

Source Node from nvm first:

```bash
export NVM_DIR="/home/ubuntu/.nvm" && . "$NVM_DIR/nvm.sh"
```

#### All projects (matches CI `lint.yml` + `test.yml`)

```bash
# Python — format, lint, unit tests
pre-commit run --all-files
PYTHONPATH=backend/src DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/backend_test \
  python3 -m pytest tests backend -q

# Admin web
cd apps/admin_web && npm ci && npm run lint && npm run typecheck
cd apps/admin_web && npm run generate:api  # then verify generated types are committed

# Public website
cd apps/public_www && npm ci && npm run lint && npm run typecheck && npm test

# CDK infrastructure
cd backend/infrastructure && npm ci && npm run lint && npm run build

# Flutter (when SDK is available)
cd apps/siutindei_app && flutter pub get && flutter analyze && flutter test
```

#### Quick per-package shortcuts

| Package | Lint | Typecheck | Unit tests |
|---------|------|-----------|------------|
| Backend | `ruff check backend/` · `ruff format --check backend/` | — | `pytest tests backend` (see above) |
| Admin web | `npm run lint` | `npm run typecheck` | — |
| Public www | `npm run lint` | `npm run typecheck` | `npm test` |
| CDK | `npm run lint` | `npm run build` | — |
| Flutter | `flutter analyze` | — | `flutter test` |

Public www production build (requires env contract):

```bash
cd apps/public_www
NEXT_PUBLIC_SITE_ORIGIN=http://localhost:3000 \
NEXT_PUBLIC_SITE_NAME="Siu Tin Dei" \
npm run build
```

Admin web E2E (Chromium + dev server on port 3000):

```bash
cd apps/admin_web && npx playwright test
```

### Non-obvious caveats

- The system Python has debian-managed packages (PyJWT, etc.) that conflict with pip. Use `pip install --ignore-installed` when installing backend deps to avoid "Cannot uninstall" errors.
- Alembic migrations require `DATABASE_URL` env var. Run from workspace root: `python3 -m alembic -c backend/db/alembic.ini upgrade head`.
- Node.js is installed via nvm at `/home/ubuntu/.nvm`. Source it before using node/npm: `export NVM_DIR="/home/ubuntu/.nvm" && . "$NVM_DIR/nvm.sh"`.
- PostgreSQL pg_hba.conf must be set to `md5` auth (not `peer`) for password-based connections. After install, run: `sed -i 's/local\s*all\s*all\s*peer/local all all md5/' /etc/postgresql/16/main/pg_hba.conf && service postgresql restart`.
- E2E tests for login/auth-related flows require Cognito env vars. Tests that don't need real auth sessions pass; authenticated flow tests fail without a real Cognito pool. The test fixtures mock auth via `test-fixtures.ts`.
- The admin web `.env.local` needs `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_COGNITO_DOMAIN`, `NEXT_PUBLIC_COGNITO_CLIENT_ID`, `NEXT_PUBLIC_COGNITO_USER_POOL_ID` for full functionality. The dev server starts without them (shows config warnings).
- Public www copies `shared/home_wizard/home_wizard_choices.json` into `apps/public_www/src/data/` for TypeScript bundling; keep both in sync when editing choices.
- Staging activity search fixture: canonical file is `shared/fixtures/activity_search_staging.json` (Git LFS). Generate with `python3 scripts/codegen/generate_activity_search_staging.py`, then `bash scripts/codegen/sync-activity-search-staging-fixture.sh` (copies to `backend/fixtures/` for Lambda bundle/synth and `apps/public_www/public/fixtures/` for static CDN). After clone run `git lfs pull`. Set GitHub Environment variable `STAGING_SEARCH_DATA_ENABLED=true` on the **staging** environment only (public www); production always uses Aurora + live API. Optional: `NEXT_PUBLIC_STAGING_SEARCH_FIXTURE_URL` (staging www) or `STAGING_SEARCH_FIXTURE_URL` dart-define (Flutter).
- Python formatting rule: run `pre-commit run ruff-format --all-files` before any Python commit (per `.cursorrules`).
- Do not file GitHub issues from `NOTE:`, `SECURITY NOTE:`, or
  `next-env.d.ts` comments. Those are documented architecture, not
  defects. See `docs/architecture/security.md` and
  `.github/workflows/close-note-tag-issues.yml`.
