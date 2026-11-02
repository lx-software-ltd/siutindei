# Plan: Documentation refresh after the 2026-11-02 merges

**Status**: Done
**Zone**: yellow (`docs/api/search.yaml` wording only), otherwise green

## Goal

Bring living docs, skills, and READMEs back in line with the code after
#778, #779, and #780, plus older drift found in the same pass.

## Non-goals

- Code changes. Drift that is a code bug is reported, not fixed. All of
  it except the ruleset is fixed in `left-out-fixes-2026-11-02.md`:
  - The search Lambda's `Cache-Control: no-store` disables the
    CloudFront edge cache; the docs now say so.
  - `deploy-mobile.yml` and `deploy-ios.yml` do not pass
    `AMPLIFY_CONFIG`, and `AmplifyService` throws without it.
  - Runtime design-token updates do not reach `designTokensProvider`.
  - The `main-protection` ruleset is disabled and has no required
    status checks, so `verify-rulesets.yml` fails.
  - A few `except Exception:` blocks still swallow errors without
    logging (`catalog_locks.py`, `enrichment/fetch.py`).
- Red-zone READMEs. `backend/db/README.md` (Python version, the
  `postgresql+psycopg://` URL) and `backend/infrastructure/params/README.md`
  (`PublicWwwOriginVerifySecret`) are reported, not edited.
- Rewriting historical plans beyond their status line.

## Files

- Public website: `docs/architecture/public-www.md`,
  `apps/public_www/README.md`, `.cursor/skills/public-www-section/SKILL.md`,
  `docs/deployment/launch-checklist.md`, `docs/legal/README.md`,
  `docs/remediation/public-www-and-api-remediation.md`.
- Search contract wording: `docs/api/search.yaml` (`view=card` drops a
  duplicate English name, `place_id` is `null` in full view). No
  schema, path, or parameter changes.
- Admin and API: `docs/architecture/admin-web-ui.md`,
  `apps/admin_web/README.md`, `.cursor/skills/admin-crud-screen/SKILL.md`,
  `.cursor/skills/admin-api-endpoint/SKILL.md`, ticket references in
  `organization-suggestions.md`, `audit-logging.md`, `overview.md`, and
  `aws-assets-map.md`.
- Repo and tooling: `AGENTS.md` (hook list), `SECURITY.md` (CORS, WAF,
  PyJWT pin), `scripts/codegen/README.md`, `docs/architecture/zones.md`,
  the `cursor-cloud` and `verify-change` skills, and
  `.cursor/rules/flutter-app.mdc` (directory names only).
- Mobile: markdown only under `apps/siutindei_app/**` (README,
  CONTRIBUTING, `docs/**`, `android/README.md`,
  `lib/config/tokens/README.md`), plus `docs/deployment/android-play-store.md`
  and `ios-testflight.md`. Samples now show Riverpod 3 `Notifier`, the
  real `--dart-define` names, JDK 17, and the flat `test/` layout. No Dart
  or Gradle source changes.
- Backend and infrastructure: `lambdas.md`, `aws-assets-map.md` (routes,
  alarms, parameters, retention, bundling), `security.md` (importer
  routes, CORS defaults), `overview.md`, `setup.md`, `decisions.md`,
  `aws-messaging.md`, `database-schema.md`, `backend-assessment.md`,
  `github-rulesets.md` (real job names), and a status note in
  `cloudflare-optimization.md`.
- `docs/plans/*.md` status lines for plans that already shipped.

## Invariants this change preserves

- `docs/api/*.yaml` paths and schemas are unchanged, so generated types
  do not move.

## Done when

- `python3 scripts/check_openapi_routes.py`
- `node scripts/check-lambda-docs.mjs`
- `python3 scripts/validate_agent_rules.py`
- `npm run generate:api` in `apps/admin_web` leaves no diff

## Rollback

Revert the commits. Docs only.
