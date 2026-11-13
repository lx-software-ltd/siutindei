# Research: mission, audience, and the category tree

**Status**: Draft
**Zone**: this memo is green (`docs/**`). The follow-up work is mixed
and has red slices. The plan is
`docs/plans/family-guide-kinds-and-topics.md`.

## Summary

The catalogue promises one thing on every card: the ages, the weekly
times, and the price of a children's class. On staging, two classes
out of 82 Stanley listings deliver all three with believable values.
The rest are places, schools, and camps pressed into a class-shaped
card, or classes with no times and no price.

Three causes, in order of weight:

1. **The category tree answers the wrong question.** It was built
   from the import sources (`lcsd`, `edb`, `swd`, `places`), so it
   names venue types: sports centre, primary school, public library.
   A parent asks two other questions: what kind of thing is this
   (a weekly class, a holiday camp, somewhere to turn up), and what is
   it about (football, music, Mandarin). The tree mixes both on one
   axis and the data model has one shape for all of them.
2. **The model cannot hold what parents need for two of the kinds.**
   A camp has dates. The schedule table only stores weekly entries
   (`schedule_type_weekly_only` in
   `backend/src/app/db/models/activity.py`). A place has opening hours
   and no class price, but search only treats a listing as complete
   when it has a weekly entry and a price row.
3. **The copy claims more than the data holds.** The home page says
   every listing is checked by local parents before it appears. The
   flag that backs the badge, `organizations.parent_verified`, is a
   boolean with no date, set by hand, and most listings are imports.

The competitors are city-wide booking sites and editorial guides. Each
is thin in any one neighbourhood. None claims to list every option in
a neighbourhood or to have checked the facts in person. That is the
open position, and it only holds if the listings are true.

## Method

Run on 13 Nov 2026 (Hong Kong time) at `main` (`eae01fd3`).

- **Staging catalogue.** Read
  `https://www-staging.siutindei.com/en/activities/` and `/llms.txt`.
  Parsed the 82 cards between the "All activities" and "Questions
  parents ask" headings into name, organiser, age chip, schedule
  snippet, and price. Sorted each card into a kind by its name and
  organiser. That sorting is a judgement, so treat the counts as
  within a few listings of the truth.
- **Production.** `https://siutindei.com` serves the maintenance page.
  Nothing public depends on today's URLs or category ids.
- **Code.** Read the files listed under "Entry points" and "Callers".
- **Competitors.** Read each company's own public pages. Figures are
  their own claims on that day and were not checked further.

## Findings: the staging catalogue

Scope is Stanley (`SEARCH_AREA_SCOPE=southern-stanley`). 82 listings
from about 40 organisers.

| Kind, as a parent would name it | Listings |
| --- | --- |
| Classes, clubs, and camps | 49 |
| Public places (beach, park, library, pool, sports ground) | 17 |
| School programmes | 12 |
| Members-only club entries | 4 |

- 14 of the 49 are water sports.
- 36 listings show a price, 50 show times, 25 show both, 21 show
  neither.
- 31 listings carry a catch-all age range (0 to 18, or 0 to 99).
- Two classes show a real class time and a real price: a church Sunday
  school (free) and a church playgroup (HK$65 a class).
- Seven listings from one tutoring centre show HK$1,998 a class
  against Monday to Sunday 10:00 to 19:00. Those are opening hours and
  a term fee.
- A library renders as "Ages 0–18 · Mon 10:00–19:00 +6 more · Free".
- Two pre-school programmes render as "HK$104,760 / 10 classes" and
  "HK$45,000 / 1 classes".
- The hub's "At a glance" block reads "0 to 100 years" and "HK$0 to
  HK$45,000 per class". Both come from `landingFacts()` in
  `apps/public_www/src/lib/activities/landing-page-data.ts`, which
  takes the minimum and maximum over every listing.
- Listings named for birthday parties, summer camps, and a fun camp
  have no dates, because there is nowhere to store them.
- A music class for ages 3 to 5 at the local shopping plaza and a
  weekly football session in Stanley were found by web search and are
  not in the catalogue. Completeness is not there yet either.

## Findings: competitors

| Who | What it is | What it leaves open |
| --- | --- | --- |
| Classbee | Booking marketplace. Trials, drop-ins, camps, party venues. About 143 studios city-wide. | Three listings on its Stanley page. |
| KidsClub | Timetable-level class listings from about 58 organisers. Links out to book. | Thin outside the central districts. |
| Kidemy | Chinese-first booking with discounts and reviews. | Lists who sells through it. |
| Bizibuz | Booking and class management. Claims 1,000+ education centres. | Provider tool first. |
| Cultiv8 Club | Booking plus provider software for playgroups. | One segment. |
| Whizpa | Parent reviews. Claims 5,000+ providers and 400+ categories, schools included. | Breadth without checked facts. |
| Little Steps, Sassy Mama | Editorial guides and round-ups. | Articles age. No times or prices per class. |
| Parent chat groups | The real incumbent for "is it any good". | Not searchable. Closed to newcomers. |
| OpenRice, Google Maps | Restaurants and places. | No reliable family facts (high chairs, changing table, room for a stroller). |

What nobody offers: every option in one neighbourhood, including the
free and the tiny, with times and prices a parent has confirmed, and a
ranking that money cannot move.

## Entry points

- Category tree: `activity_categories` (`id`, `parent_id`, `name`,
  `name_translations`, `display_order`, `show_in_wizard`), model in
  `backend/src/app/db/models/activity_category.py`. Current rows come
  from `backend/db/alembic/versions/0040_recheck_taxonomy.py`: seven
  wizard groups (`c1111111-1111-1111-1111-111111111201` to `…1207`)
  and 26 leaves (`…1211` to `…1272`).
- System and legacy ids: `PENDING_CATEGORY_ID`, `LEGACY_CATEGORY_IDS`,
  and `WIZARD_GROUP_IDS` in
  `backend/src/app/db/models/category_suggestion.py`. The seven group
  ids are hardcoded there.
- Public search: `backend/src/app/api/search.py` (`parse_filters`,
  `fetch_search_response`), `backend/src/app/db/queries.py`
  (`build_search_query`, `_category_descendant_ids_subquery`,
  `category_match_mode`), `backend/src/app/db/incomplete_search.py`,
  `backend/src/app/api/search_page.py`, response shapes in
  `backend/src/app/api/schemas.py`, contract in `docs/api/search.yaml`.
- Wizard choices: `scripts/codegen/generate_home_wizard_choices.py`
  writes `shared/home_wizard/home_wizard_choices.json`;
  `scripts/codegen/sync-home-wizard-choices.sh` copies it to
  `apps/public_www/src/data/` and
  `apps/siutindei_app/assets/home_wizard/`.
- Verified flag: `organizations.parent_verified`
  (`backend/db/alembic/versions/0064_org_parent_verified.py`), written
  in `backend/src/app/api/admin_resource_organization.py`.

## Owners

The owner of the repository decides the taxonomy, the copy, and the
area scope. `backend/db/**` and `shared/**` are red in
`docs/architecture/zones.md`.

## Callers

What reads a category id, a schedule, or the wizard file today.

- **Search filter.** `build_search_query` joins activity, schedule,
  entry, location, and price, so a "complete" row needs a weekly entry
  and a price at the same location. It excludes
  `PENDING_CATEGORY_ID`. The age filter is
  `Activity.age_range.contains(age)` with one age per wizard group
  (2, 4, or 9), so a class for ages 6 to 8 does not match the 6 to 12
  group.
- **Legacy fallback.** A search on a wizard group with no assigned
  activities in scope also returns the five legacy roots and reports
  `category_match: legacy_fallback`. Read by
  `apps/public_www/src/lib/activities/search-client.ts`,
  `apps/public_www/src/components/pages/search-results-page.tsx`, and
  `apps/siutindei_app/lib/models/activity_models.dart`.
- **Catalogue snapshot.** `backend/src/app/services/catalogue_snapshot.py`
  pages through the same search with `view=full` and
  `include_incomplete=true`. The public build reads it in
  `apps/public_www/src/lib/activities/catalogue-snapshot.ts`.
- **Staging fixture.** `backend/src/app/services/staging_search_store.py`
  and `scripts/codegen/generate_activity_search_staging.py` emit the
  same row shape.
- **Public cards and pages.** `listing-card.tsx`,
  `activity-key-facts.tsx`, `listing-facts.ts`, `price-format.ts`,
  `schedule-format.ts`, `landing-page-data.ts`, `llms-txt.ts`, and
  `search-params.ts` under `apps/public_www/src`.
- **Group id equality on the public site.** `catalogueCategories()`
  and `landingTypeIdForListing()` in `catalogue-snapshot.ts`, and
  `categoryLabelForListing()` in `listing-facts.ts`, compare
  `activity.categoryId` with the wizard group id. An activity on a
  leaf matches none of them, so it gets no category chip and counts
  toward no landing page. Staging fits that reading: with 82
  activities in scope, `llms.txt` links the hub and no type page, and
  `/en/activities/sports/` returns 404. Not reproduced locally,
  because the local fixture is synthetic and puts every activity on a
  group id.
- **Category model calls.**
  `backend/src/app/services/category_suggestions/prompt.py` sends the
  taxonomy to the model. A recheck (`ignore_current_category`) sends
  leaves only and skips Pending and the legacy roots.
- **Import resolution.**
  `backend/src/app/services/category_suggestions/resolve.py` resolves
  an imported `category_name` by exact name, then by an alias
  (`category_suggestions.created_category_id` or
  `merged_into_category_id` under the name's fingerprint), then by a
  unique normalised match. Anything else lands on Pending.
- **Website enrichment.**
  `backend/src/app/services/enrichment/prompt.py` asks the model for
  activities, prices, and weekly schedule rows. It has no field for
  dates.
- **Organization review.** `backend/src/app/services/org_review.py`
  raises `missing_pricing`, `missing_schedule`, and `pending_category`
  as blockers for every activity, whatever it is.
  `backend/src/app/services/org_review_sql.py` mirrors the same rules
  in SQL for the summary and the queue filter.
- **Admin console.** `activity-categories-panel.tsx`,
  `activities-panel.tsx`, `schedules-panel.tsx`, `pricing-panel.tsx`,
  and `organizations-panel.tsx` under
  `apps/admin_web/src/components/shared`.
- **Flutter.** `lib/features/home_wizard/**`,
  `lib/models/activity_models.dart`,
  `lib/features/search/widgets/activity_card.dart`.

## Existing abstractions

Use these instead of building new ones.

- **Recheck.** A verify run with `ignore_current_category` re-assigns
  every activity against the current leaves and auto-applies at the
  0.90 threshold. See `docs/architecture/category-suggestions.md`.
- **Aliases.** A `category_suggestions` row with a target makes an old
  imported label resolve to a new category.
- **System category.** Pending is protected from rename, re-parent,
  delete, and the wizard in
  `backend/src/app/api/admin_resource_activity_category.py` and
  `backend/src/app/db/repositories/activity_category.py`. The same
  guard can protect other fixed roots.
- **Reject as not relevant.** `organizations.review_status =
  'rejected'` with `review_reason = 'not_relevant'` hides an
  organisation while `ORG_REVIEW_GATE_ENABLED` is on, and import
  settings `skip_deleted_organizations` keeps deleted ones out.
- **Review issues.** `org_review.py` and `org_review_sql.py` already
  count issues per organisation and expose them at
  `/v1/admin/org-review/summary`.
- **Enum type swap.** `0060_pricing_month_year.py` shows how this
  repository changes a PostgreSQL enum.
- **Wizard file.** It already carries `minAge` and `maxAge` for each
  age group. Only `searchAge` is used.

## Tests

- Search: `tests/test_search_category_filter.py`,
  `tests/test_search_queries.py`, `tests/test_search_incomplete.py`,
  `tests/test_search_validation.py`, `tests/test_search_handler.py`,
  `tests/test_search_public_details.py`,
  `tests/test_search_area_scope.py`.
- Categories: `tests/test_category_recheck_followups.py`,
  `tests/test_category_scan.py`, `tests/test_category_suggestions.py`,
  `tests/test_partner_activity_categories.py`,
  `tests/test_activity_category_names.py`.
- Wizard file: `tests/test_home_wizard_choices.py`,
  `apps/siutindei_app/test/home_wizard_choices_test.dart`.
- Snapshot and fixture: `tests/test_catalogue_snapshot.py`,
  `tests/test_staging_search_store.py`.
- Schedules and prices: `tests/test_admin_schedule_validation.py`,
  `tests/test_pricing_month_year.py`.
- Migrations: `tests/test_alembic_revision_contract.py`.
- Public site: `apps/public_www/tests/**`, including
  `tests/components/search-results-page.test.tsx`.

## Production signals

- Production is in maintenance mode, so there is no traffic to read.
- Staging shows the figures under "Findings: the staging catalogue".
- The API stack is at 494 of CloudFormation's 500 resources
  (`docs/plans/public-www-seo-and-llm-search.md`). A new API route
  costs resources there and is a red-zone change.
- The database is Aurora PostgreSQL 16.4
  (`backend/infrastructure/lib/constructs/database.ts`).

## History

- `0001_initial_schema.py` created the `schedule_type` enum with
  `weekly`, `monthly`, and `date_specific`. The model now allows only
  `weekly`.
- `0040_recheck_taxonomy.py` replaced the five flat roots with the
  seven groups and 26 leaves, and added the recheck.
- `0060_pricing_month_year.py` added `per_month` and `per_year`.
- `0064_org_parent_verified.py` added the verified flag. It is the
  latest revision.
- `docs/plans/2026-11-10-search-area-scope.md` limited public search
  to Stanley.

## Open questions

- How many production activities still sit on a legacy root? The
  fallback in `queries.py` can only be removed when the answer is
  none.
- Does any partner integration depend on the seven group ids? The
  partner category routes are in
  `backend/src/app/api/partner_activity_categories.py`.
- Answered on 13 Nov 2026: the owner is not planning the Flutter app
  in the short term, so the plan leaves the app's code alone.
