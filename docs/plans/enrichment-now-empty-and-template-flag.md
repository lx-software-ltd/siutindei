# Plan: Enrichment "Now" and template description flag

**Status**: Done
**Zone**: yellow

## Goal

On the admin organization page, Website enrichment "Now" is the live
catalog (logo, photos, contact, description, venue/activity/price
counts), not a frozen crawl snapshot or a blank row. Readiness does
not warn "Description is a template" after a real description has
replaced import filler. Public search shows that description. Import
filler from EDB, LCSD, and Places stays hidden and still warns.

Evidence and the International Montessori School example:
`docs/research/enrichment-now-empty-and-template-flag.md`.

## Non-goals

- Schema, seed, or a data migration (red `backend/db/**`).
- Re-crawling or changing extract quotes, confidence, or dismiss
  hashes.
- Hiding applied/dismissed enrichment rows.
- A shared phrases file under red `shared/**`. Python and the public
  website keep matching constants; a test locks them together.

## Files

- `backend/src/app/services/description_boilerplate.py` — shared
  filler: English closing `for children and families` with `is a ` /
  `is an `, and Cantonese closing `適合小朋友同家庭`. That covers
  the EDB class sentence and the LCSD/Places venue sentence. Search
  hides a `template` description when it is blank or still filler.
  Readiness warns on that English filler, and on leftover Chinese
  filler in `description_translations`.
- `backend/src/app/services/enrichment/store.py` — GET serializer
  takes the live organization, venues, activity names, and
  pricing/schedule counts. `current_value` in the response is
  display-only. Stored `current_value` is unchanged so apply `_still`
  still detects edits since the crawl.
- `backend/src/app/services/enrichment/match.py` — reuse
  `_live_current` for org fields (only the proposed translation
  languages). Add display currents:
  - `add_media` logo: `logo: saved` when a logo URL exists (no URL
    in the payload), plus `already_saved: true` when `source_url` is
    already on the org
  - `add_media` photo: `{ "photos": N }` when `media_urls` is
    non-empty, plus `already_saved: true` when `source_url` is
    already on the org
  - `create_location` / `create_activity`: matching row when the
    address or name already exists, otherwise `{ "venues": N }` /
    `{ "activities": N }` when the org already has some
  - `create_pricing` / `create_schedule`: `{ "prices": N }` /
    `{ "schedules": N }` when the org already has some
  - `update_organization`: `changed_since_crawl: true` when live
    fields differ from the stored snapshot (apply will refuse)
- `backend/src/app/api/admin_enrichment.py` — pass org, venues,
  activity names, and counts into serialize
- `backend/src/app/services/enrichment/apply_rows.py` — applying a
  non-filler `description` sets `description_source` to `enrich`
  (do not overwrite `official` or `places`). Applying only
  `description_translations` does not retag.
- `backend/src/app/services/org_review.py` and
  `backend/src/app/services/org_review_sql.py` — `source_attribution`
  for `template` only when the English description still looks like
  import filler. Leftover Chinese filler in translations warns
  separately. A unique description with a stale `template` tag is
  not an English template warning. Keep the `Source:` substring
  check.
- `backend/src/app/api/search.py` — same boilerplate test before
  blanking descriptions. A translation that is still filler is
  omitted. Leave card view omitting descriptions.
- `backend/src/app/services/category_suggestions/prompt.py` —
  recheck treats a missing `description_source` as untrusted, and a
  `template` tag as untrusted only when the text is blank or filler.
- `apps/admin_web/src/components/admin/organization-enrichment-proposals.tsx`
  — `proposedText` drops null / blank entries but keeps `false`.
  `currentText` uses labels (`2 photos`, `Already saved`, `Logo saved`,
  `Changed since crawl`) and does not print media URLs. If no
  current fields remain, `Empty`.
- `apps/public_www/src/lib/activities/description-boilerplate.ts` and
  the listing, staging, and static catalog callers — the activity
  page uses the same blank-or-filler rule.
- Tests: `tests/test_org_enrichment.py`, `tests/test_org_review.py`,
  `tests/test_description_boilerplate.py`, search tests,
  category recheck tests,
  `apps/admin_web/tests/components/admin/organization-enrichment-proposals.test.tsx`
- OpenAPI descriptions for enrichment `current_value` and search
  `description_source`. Regenerated admin types.

## Invariants this change preserves

- Apply still compares against the **stored** crawl snapshot and
  rejects "changed since the crawl".
- `description_source` allowed values stay
  `template | official | places | enrich`.
- EDB/LCSD/Places filler keeps the template warning and stays hidden
  from search.
- `Source:` in the description still warns.
- Media apply still keys off `source_url`. GET may add display-only
  keys (`photos`, `already_saved`, `venues`, `activities`, `prices`,
  `schedules`, `logo`, `changed_since_crawl`); apply ignores them
  because they are not persisted.
- No new API Gateway paths.

## Done when

- `pytest tests/test_org_enrichment.py tests/test_org_review.py tests/test_description_boilerplate.py tests/test_search_text_and_view.py tests/test_category_recheck_followups.py tests/test_category_scan_guards.py`: GET enrichment for an org with a logo and photos does not return `current_value: null` on those media rows; applying a description sets `description_source` to `enrich`; applying only a translation does not; a unique description with `description_source=template` does not emit the English template warning and is not blanked in search; LCSD/Places filler still does; leftover Chinese filler warns; category recheck includes unique template copy.
- Admin: `npm test -- tests/components/admin/organization-enrichment-proposals.test.tsx`,
  `npm run lint`, `npm run typecheck`, `npm run generate:api` in `apps/admin_web`.
  `Now: Empty` remains only when every current field is null or blank.
- Public website: `npm test` for listing-utils and description-boilerplate.
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

None.
