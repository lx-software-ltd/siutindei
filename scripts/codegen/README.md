# Code generation and data sync

This folder holds a generic OpenAPI client generator and the scripts that
build and copy shared data files.

## Current client generation in this repo

- **Admin web** uses `openapi-typescript` against `docs/api/admin.yaml`
  (see `apps/admin_web/package.json#generate:api`). The generated types
  live in `apps/admin_web/src/types/api-admin.generated.ts` and must be
  committed when the spec changes.
- **Public website** and **Flutter** hand-write their search clients against
  `docs/api/search.yaml`; keep them aligned when the API surface changes.
- The historical `packages/api_client_ts` / `packages/api_client_dart`
  paths are not present in this repository. Use the admin_web workflow above
  for TypeScript types, or run `openapi_codegen.sh` into a new package if you
  introduce shared clients later.

## Shared data

| Script | Purpose |
| --- | --- |
| `generate_activity_search_staging.py` | Regenerates the canonical staging search fixture `shared/fixtures/activity_search_staging.json` (Git LFS). |
| `sync-activity-search-staging-fixture.sh [all\|backend\|public-www]` | Copies that fixture into `backend/fixtures/` and `apps/public_www/public/fixtures/`. |
| `generate_home_wizard_choices.py` | Rebuilds `shared/home_wizard/home_wizard_choices.json` from categories flagged `show_in_wizard`. `--write` reads `DATABASE_URL`. |
| `sync-home-wizard-choices.sh [--check]` | Copies the wizard JSON into `apps/public_www/src/data/` and `apps/siutindei_app/assets/home_wizard/`. `--check` fails when a copy is out of sync. |

## OpenAPI client generator usage

1. Install Node.js 24 and a Java runtime (OpenAPI Generator needs one).
2. Run the codegen script with the desired generator.

Example:

```
./scripts/codegen/openapi_codegen.sh \
  --spec docs/api/search.yaml \
  --generator typescript-fetch \
  --output packages/api_client_ts
```

You can use any generator supported by OpenAPI Generator.
