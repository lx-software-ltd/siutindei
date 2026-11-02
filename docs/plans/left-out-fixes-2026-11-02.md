# Plan: Fix the drift the 2026-11-02 docs refresh only reported

**Status**: Done
**Zone**: red (approved by the repository owner in chat)

## Goal

Fix the code and red-zone items that `docs-refresh-2026-11-02.md` listed
as non-goals, then mark them resolved in the docs.

## Non-goals

- Turning on the `main-protection` ruleset. That is a GitHub settings
  change a repository admin makes; see `docs/architecture/github-rulesets.md`.
- Tightening CSP `img-src` (remediation P3-4). Media URLs can be on any
  HTTPS host, so it stays an accepted risk.

## Files

- Search caching (yellow, red fixture): `backend/src/app/api/search.py`
  sends `public, max-age=60, s-maxage=300` on public 200s. Partner search
  and errors keep `no-store`. `manager_id` leaves `schemas.py`,
  `docs/api/search.yaml`, the staging generator, and
  `shared/fixtures/activity_search_staging.json`.
- Public website tests (green, CI): a Playwright smoke suite in
  `apps/public_www/e2e/`. `test.yml` and `lint.yml` now run public_www
  lint, unit, and e2e jobs.
- Mobile release config (red): `scripts/deploy/build_amplify_config.py`
  builds `AMPLIFY_CONFIG` from the API stack outputs, and
  `deploy-mobile.yml` and `deploy-ios.yml` pass it with
  `--dart-define-from-file`. The Android manifest gains `INTERNET`, the
  hosted-UI redirect scheme, and the Custom Tabs query.
- Design tokens (yellow): `designTokensProvider` watches
  `designTokensNotifierProvider`.
- Logging (yellow and red): the silent `except Exception:` handlers
  either log or catch the specific error.
- Deploy secret (red): `deploy-backend.yml` exports
  `CDK_PARAM_OPENROUTER_API_KEY`.
- READMEs (red): `backend/db/README.md` and
  `backend/infrastructure/params/README.md`.

## Invariants this change preserves

- Partner search responses and every error response stay `no-store`.
- An unset `CDK_PARAM_OPENROUTER_API_KEY` is skipped, so `cdk deploy`
  keeps the previous `OpenRouterApiKey` value.
- Overriding `designTokensProvider` still pins tokens.

## Done when

- `pytest tests backend` against a migrated database
- `npm run lint`, `npm run typecheck`, `npm test`, and `npm run test:e2e`
  in `apps/public_www`
- `flutter analyze` and `flutter test` in `apps/siutindei_app`
- `python3 scripts/check_openapi_routes.py`,
  `node scripts/check-lambda-docs.mjs`,
  `python3 scripts/validate_agent_rules.py`, and `scripts/check-pii.sh`

## Rollback

Revert the commits. A reverted search Lambda goes back to `no-store`, and
CloudFront drops cached entries within 300 seconds.

## Open questions

- Set `CDK_PARAM_OPENROUTER_API_KEY`, `AWS_ACCOUNT_ID`, and `AWS_REGION`
  on the environments the mobile workflows use before the next release.
