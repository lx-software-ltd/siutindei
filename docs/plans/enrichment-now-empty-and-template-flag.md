# Plan: Enrichment "Now" and template description flag

**Status**: Draft
**Zone**: yellow

## Goal

On the admin organization page, Website enrichment "Now" is the live
catalog (logo, photos, contact, description), not a frozen crawl
snapshot or a blank `add_media` / location row. Readiness does not
warn "Description is a template" after a real description has replaced
the import boilerplate. Public search shows that description.

Evidence and the International Montessori School example:
`docs/research/enrichment-now-empty-and-template-flag.md`.

## Non-goals

- Schema, seed, or a data migration (red `backend/db/**`).
- Re-crawling or changing extract quotes, confidence, or dismiss
  hashes.
- A new warning for leftover Chinese boilerplate after English is
  replaced. Call that out in the PR; do not build a second detector
  in this change.
- Hiding applied/dismissed enrichment rows.

## Files

- `backend/src/app/services/enrichment/store.py` — GET serializer
  takes the live organization (and venues). `current_value` in the
  response is display-only. Stored `current_value` is unchanged so
  apply `_still` still detects edits since the crawl.
- `backend/src/app/services/enrichment/match.py` — reuse
  `_live_current` for org fields. Add display currents:
  - `add_media` logo: existing `logo_media_url` when set
  - `add_media` photo: `{ "photos": N }` when `media_urls` is
    non-empty, plus `already_saved: true` when `source_url` is
    already on the org
  - `create_location` / `create_activity`: matching row when the
    address or name already exists, otherwise `{ "venues": N }` /
    `{ "activities": N }` when the org already has some
- `backend/src/app/api/admin_enrichment.py` — pass org and venues
  into serialize
- `backend/src/app/services/enrichment/apply_rows.py` — applying
  `description` or `description_translations` sets
  `description_source` to `enrich` (do not overwrite `official` or
  `places`)
- `backend/src/app/services/org_review.py` and
  `backend/src/app/services/org_review_sql.py` — `source_attribution`
  for `template` only when the English description still looks like
  import boilerplate (`is a class or early-years centre in` / the
  Cantonese `幼兒或興趣班，適合小朋友同家庭` closing). A unique
  description with a stale `template` tag is not a warning. Keep the
  `Source:` substring check.
- `backend/src/app/api/search.py` — same boilerplate test before
  blanking descriptions, so a retagged **or** retagged-in-text-only
  org is visible. Leave card view omitting descriptions.
- `apps/admin_web/src/components/admin/organization-enrichment-proposals.tsx`
  — `proposedText`: drop null / blank entries; if none remain, `Empty`.
  Do not print `email: ` for `{ "email": null }`.
- Tests: `tests/test_org_enrichment.py`, `tests/test_org_review.py`,
  search tests that cover template blanking,
  `apps/admin_web/tests/components/admin/organization-enrichment-proposals.test.tsx`
- OpenAPI descriptions for enrichment `current_value` (live catalog on
  GET) in `docs/api/admin.yaml` / `docs/api/partner.yaml` if the
  current text implies a crawl snapshot

## Invariants this change preserves

- Apply still compares against the **stored** crawl snapshot and
  rejects "changed since the crawl".
- `description_source` allowed values stay
  `template | official | places | enrich`.
- A description that is still the EDB/LCSD boilerplate keeps the
  template warning and stays hidden from search.
- `Source:` in the description still warns.
- Media apply still keys off `source_url`. GET may add display-only
  keys (`photos`, `already_saved`, `venues`, `activities`); apply
  ignores them because they are not persisted.
- No new API Gateway paths.

## Done when

- `pytest tests/test_org_enrichment.py tests/test_org_review.py` plus
  the search test that blanks template descriptions: GET enrichment
  for an org with a logo and photos does not return `current_value:
  null` on those media rows; applying a description sets
  `description_source` to `enrich`; a unique description with
  `description_source=template` does not emit `source_attribution`
  and is not blanked in search; boilerplate text still does.
- Admin: `npm test -- tests/components/admin/organization-enrichment-proposals.test.tsx`,
  `npm run lint`, `npm run typecheck` in `apps/admin_web`. `Now: Empty`
  remains only when every current field is null or blank.
- `pre-commit run ruff-format --all-files` before commit.
- No seed change: `description_source` semantics stay, writers and
  the warning catch up.

Workaround until this ships: on Details, set Description origin from
Template to Enrich and save. That clears Readiness and search hiding
for one org; it does not fix "Now: Empty".

## Rollback

Revert the pull request. Stored proposals and `description_source`
rows are unchanged except orgs that had a description apply after
this code shipped (those stay `enrich`, which is correct).

## Open questions

None. Leftover Chinese boilerplate after an English enrich apply is
explicitly out of scope.
