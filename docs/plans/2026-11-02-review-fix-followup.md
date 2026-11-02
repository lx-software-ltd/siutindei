# Plan: Fix the review findings on the remediation branch

**Status**: Approved (user asked to fix every issue in the 2026-11-02 review of PR #779)
**Zone**: red (stricter of the paths below). Yellow paths follow this plan and get tests first. Red paths are included because the user explicitly asked for those fixes: the CloudFront function, `api-stack.ts`, `scripts/deploy/deploy-public-www.sh`, and `promote-public-www.yml`.

## Goal

Correct the defects found when the remediation branch was checked against the spec: broken production HTML size, staging listings shipped as production pages, the location-fixes 500, the edge redirect, one-year caching of unhashed files, and the smaller functional gaps that have a safe code fix.

## Non-goals

- Rewriting the location, name, and translation service modules into one generic implementation. The lifecycle crash is fixed; deleting those modules would change sweep behaviour.
- Replacing `google.maps.Marker` with `AdvancedMarkerElement`. That API needs a Cloud map id this app does not have, and a demo id would watermark production maps.
- Forcing the admin dashboard under 160 KB gzip. The Cognito SDK is split out; React and the Next.js router remain in the first load.
- Collapsing every remaining jscpd clone in the admin pricing and data-quality panels.

## Files

- `apps/public_www/**` for CSP, static pages, search, home, and maps. With staging pages off, `generateStaticParams` still returns one placeholder id per locale because static export rejects an empty list. `activity:prune-placeholder` deletes those files before CSP injection. The sitemap stays empty of activity urls.
- `backend/src/**` for the location-fixes crash, card JSON, `q`, and the search hot path.
- `docs/api/search.yaml` for `q` max length and card required fields.
- `backend/infrastructure/lib/functions/public-www-path-rewrite.js` and its test.
- `backend/infrastructure/lib/api-stack.ts` for the search cache-key list and the fixture copy.
- `scripts/deploy/deploy-public-www.sh` so unhashed files keep the document cache policy.
- `.github/workflows/promote-public-www.yml` and `lighthouse-public-www.yml` for Git LFS.
- `apps/admin_web/src/**` for the categories import, dropdown cache, and Cognito split.

## Invariants this change preserves

- Public search default stays `view=full`.
- Admin and manager HTTP paths stay the same.
- Production search stays on Aurora (`STAGING_SEARCH_DATA_ENABLED=false`).
- Unprefixed routes still redirect, and the locale query string is the viewer's original string.
- No secrets, PII, or `Cors.ALL_ORIGINS`.

## Done when

Public www lint, typecheck, and the affected vitest files pass. Admin lint and typecheck pass. Backend pytest for the search and proposal tests passes, and `pre-commit run ruff-format` is clean on the Python edits. A production-mode public build does not read the staging fixture and does not emit a CSP tag larger than 8 KB.

## Rollback

Revert the branch. No new migration.

## Open questions

None.
