# Plan: Point staging smoke at the resolve-step origin

**Status**: Implemented
**Zone**: yellow (`.github/workflows/smoke-public-www-staging.yml`), green (`apps/public_www`)

## Goal

Smoke Public Website Staging run 45530677204 failed with
`SMOKE_BASE_URL is required` because the smoke step still reads
`steps.resolve_staging_site_origin.outputs.staging_site_origin` after the
resolve step id became `resolve_public_site_config`. Point `SMOKE_BASE_URL` at `vars.STAGING_SITE_ORIGIN` with a fallback to
that step output. `SUMMARY_TARGET_URL` already uses the resolve-step
output; the optional-var prefix cannot go on that unmarked line until
the actions pin's template matches.

Silence siutindei-only `npm ci` install warnings by mirroring
evolvesprouts: `allowScripts.unrs-resolver` and an `@lhci/cli`
`chrome-launcher` 0.15.2 override.

## Non-goals

- Moving `env:` out of `# template:set` (the current actions pin still
  expects `SMOKE_BASE_URL` in the value block).
- Editing `deploy-public-www-staging.yml` unless it still uses the stale
  step id (it already uses `resolve_public_site_config`).
- Adding a populated GitHub Actions variable. `STAGING_SITE_ORIGIN` is
  an optional override and is currently unset.
- `npm audit fix`, hiding fund/audit lines, or bumping the actions pin
  for `npm ci --no-audit --no-fund`.

## Files

- `docs/plans/staging-smoke-origin.md` (this plan)
- `tests/test_smoke_public_www_staging.py` (workflow expression lock)
- `.github/workflows/smoke-public-www-staging.yml`
- `apps/public_www/package.json`
- `apps/public_www/package-lock.json`

## Invariants this change preserves

- `# template:set` / `# template:end` stay around the smoke `env:` block.
- Origin still comes from CDK `PublicWwwStagingDomainName` via
  `scripts/deploy/resolve-public-www-build-env.sh` when the optional
  var is unset.
- Top-level `uuid` override in `apps/public_www/package.json` stays.
- Production `npm audit --omit=dev` stays clean without a blind
  `npm audit fix`.

## Done when

- `SMOKE_BASE_URL` uses
  `${{ vars.STAGING_SITE_ORIGIN || steps.resolve_public_site_config.outputs.staging_site_origin }}`.
- `SUMMARY_TARGET_URL` stays
  `${{ steps.resolve_public_site_config.outputs.staging_site_origin }}`
  so unmarked template text still matches the current actions pin.
- `pytest tests/test_smoke_public_www_staging.py`
- `npm test` in `apps/public_www` for the smoke script
- `npm ci` in `apps/public_www` has no `npm warn deprecated inflight`,
  `rimraf@3`, `glob@7`, or `npm warn install-scripts` / `unrs-resolver`
- `npm audit --omit=dev` in `apps/public_www` stays clean

## Rollback

Revert the workflow expressions to the previous step id (broken) or
restore the commit. Unset `vars.STAGING_SITE_ORIGIN` has no effect
because the step-output fallback remains.

## Open questions

None.
