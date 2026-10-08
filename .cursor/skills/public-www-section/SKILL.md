---
name: public-www-section
description: Add a public website page or section without breaking the static-export contract.
---

# Public website section

1. Page composition goes in `src/components/pages/`, sections in `src/components/sections/`, shared primitives in `src/components/shared/`.
2. Tests go in `apps/public_www/tests/`. Do not add `*.test.*` files under `src/`.
3. Store SVGs in `public/images/` and reference `/images/...`.
4. Read `NEXT_PUBLIC_*` from `src/lib/site-config.ts`. Components do not touch `process.env`.
5. A new `__NEXT_PUBLIC_FOO__` placeholder in `maintenance/index.html` updates `inject_maintenance_contact_values()` in `scripts/deploy/deploy-public-www.sh` and `validate_maintenance_contact_settings()`.
6. Keep `apps/public_www/scripts/assert-build-env-contract.mjs` in sync with the deploy and promote workflow env blocks.
7. Do not change the promotion contract (`PUBLIC_WWW_PROMOTE_RELEASE_ID`, `PUBLIC_WWW_PROMOTION_BUILD_DIR`) without updating `promote-public-www.yml`.

## Done

`npm run lint` and `npm test` pass in `apps/public_www`.
