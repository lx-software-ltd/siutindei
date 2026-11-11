# Plan: Show activity information clearly on the public website

**Status**: Draft
**Zone**: green (phases 0 to 3, `apps/public_www/**`), yellow (phase 4,
search API and `docs/api/search.yaml`)

Findings and measurements are in
`docs/research/public-www-activity-pages-ux.md`.

## Goal

A parent opening an activity can answer five questions on the first
screen at every viewport: what is it, for what age, when, where, and
how much. The enquiry button is always reachable. Times, names, and
venues are correct. Cards and map rows show the same facts in the same
order, so a parent can compare activities without opening each one.

## Non-goals

- Branding: logo, colours, typeface, mascot, tone of the chrome copy.
- Server rendering or per-activity static pages. The site stays a
  static export with one `/activity/` page.
- Booking, payment, or accounts.
- Publishing organisation contact details or parent feedback. Both
  wait on a product decision (see Open questions).
- Changes to the Flutter app.

## Target design

### Activity detail page

Reading order, top to bottom on a phone:

1. **Way back.** "Back to results" when the visitor came from search,
   otherwise a breadcrumb of category and neighbourhood that links to
   search.
2. **Photos.** Every `media_urls` entry, not only the first. A logo is
   shown contained on a plain tile, never stretched. No photo shows the
   category illustration. A photo that fails to load falls back the
   same way.
3. **Title block.** Category chip, `h1`, organisation name with logo,
   then "Temporarily closed" and "Free trial" as badges.
4. **Key facts.** Labelled tiles with an icon each: Ages, When, Where,
   Price, Language. A missing fact is one quiet line ("Ask for times")
   that links to the enquiry, not a value-shaped placeholder.
5. **Sections with `h2` headings.**
   - About: paragraphs kept, long text folded behind "Read more" on
     phones.
   - Schedule: every weekly session in Hong Kong time with start and
     end, grouped by day, plus teaching languages.
   - Price: amount, what it buys ("8 sessions"), the per-class
     equivalent, and the free trial.
   - Location: neighbourhood and region, address, a map from the
     coordinates, and a directions link that works without a place id.
     Several venues list as selectable rows.
   - Organiser: logo, name, description.
   - Similar activities nearby: a carousel of the same category in the
     same area.
6. **Enquiry.** One activity-aware WhatsApp action that is always on
   screen. The generic floating button is hidden on this page.

Loading shows a skeleton with the final page's proportions. Not-found
and error states are a short message with links to search and home.

### Detail layout by viewport

| Viewport | Layout | Photos | Enquiry |
| --- | --- | --- | --- |
| Mobile portrait | One column | Swipe carousel, full width, at most 45% of screen height, with a counter | Bottom bar: price and "Ask on WhatsApp" |
| Mobile landscape | Two columns: photos left, text right | Carousel fills the left column | In the title block. No bottom bar. Header does not stick |
| iPad portrait | One column, text measure capped | One large photo and two stacked, at most 420 px tall | Bottom bar |
| iPad landscape | Photos across the top, then content left and a summary card right | One large and four small | Summary card, sticky |
| PC landscape | Same as iPad landscape, wider | One large and four small | Summary card, sticky |
| PC portrait | Same as iPad landscape | One large and four small | Summary card, sticky |

The summary card repeats price, key facts, the WhatsApp action,
directions, and share. With the sections and the carousel the page is
long enough that the desktop blank space goes away.

### Listing card

- Facts in a fixed order: photo, category and age chips, title,
  organiser, "neighbourhood · day and time", price with the free-trial
  tag.
- A missing price or schedule is omitted from the meta line. One muted
  "Details on request" replaces repeated placeholders.
- One link per card. The region link stays separate.
- "Parent-Verified" leaves the card unless a per-listing signal backs
  it (see Open questions).
- An activity with several venues or prices is one card: "2 locations"
  and "from HK$...".
- The mini map moves off the photo.

### Search list by viewport

| Viewport | Today | Target |
| --- | --- | --- |
| Mobile portrait | 1 photo card, about 1.5 per screen | Row cards (photo left, facts right), about 5 per screen |
| Mobile landscape | 2 columns, no whole card visible | 3 compact columns. Header scrolls away. Chips share the header row |
| iPad portrait | 2 columns | 3 columns |
| iPad landscape | 3 columns | 3 columns |
| PC landscape | 4 columns | 4 columns |
| PC portrait | 3 columns | 3 columns |

Above the results: the active filters as removable chips (including
the default age). A total count and a sort need API work and sit in
phase 4. Three new
filter chips use parameters the API already accepts: free
(`pricing_type=free`), one day of the week, and teaching language.
Free trial, weekend, and a per-class price band need API work and sit
in phase 4. Chips and "See all" grow to 44 px. Carousels get previous
and next buttons on pointer devices.

### Search map by viewport

| Viewport | Target |
| --- | --- |
| Mobile portrait | Map with a bottom sheet: a swipeable row of result cards in step with the pins, pulled up into a list. "List / Map" becomes a segmented control in the chip row. Floating WhatsApp button hidden |
| Mobile landscape | Side by side: map left, result rows right |
| iPad portrait | Map on top, two-column result rows below |
| iPad landscape, PC | Split stays. Rows gain age, time, and neighbourhood. A row click selects the pin and shows a "View" button. Hover highlights the pin. Results load inside the list |
| Enlarged map | Summary card capped in width and anchored bottom-left, clear of the zoom controls |

Pins get a white backing and a distinct selected state. Pins at the
same venue or very close together group into a count.

## Phases

Each phase is one pull request and ships on its own.

### Phase 0: correctness (green)

- `src/lib/activities/listing-utils.ts`
  - `pickTranslation`: `zh-HK` reads `zh-HK`, then `zh`, then the base
    value. `en` reads `en`, then the base value. Never `zh` on `en`.
  - Schedule times convert from UTC to Hong Kong time (fixed +480
    minutes, day carried forward) in one helper used by every caller.
- `src/lib/activities/group-listings.ts` (new): group search rows by
  activity id, keeping venue, schedule, and price variants.
  `use-activity-search.ts` and the home carousels use it.
- `search-client.ts`: `fetchActivityListingById` requests all rows of
  the activity and returns the grouped listing.
- `map-listing.ts`: keep `organization.description_translations`.
- `activity-detail-page.tsx`: description keeps line breaks. Image
  `onError` falls back.
- `listing-grid.tsx`: skeletons take the grid cell width.
- Tests first: `tests/lib/listing-utils.test.ts` (translation order,
  UTC to Hong Kong time including the day carry, price suffixes),
  `tests/lib/group-listings.test.ts`, and a two-venue case in
  `tests/components/search-results-page.test.tsx`.

### Phase 1: activity detail page (green)

- New formatting helpers in `src/lib/activities/`: `schedule-format.ts`
  (sessions grouped by day, ranges), `price-format.ts` (sessions and
  per-class equivalent), `age-format.ts`, `area-labels.ts`
  (neighbourhood and region from `home_wizard_choices.json`),
  `category-labels.ts`, `directions-url.ts`.
- New sections in `src/components/sections/activity-detail/`:
  `activity-breadcrumb.tsx`, `activity-gallery.tsx`,
  `activity-title-block.tsx`, `activity-key-facts.tsx`,
  `activity-about.tsx`, `activity-schedule.tsx`, `activity-price.tsx`,
  `activity-location.tsx`, `activity-organiser.tsx`,
  `activity-similar.tsx`, `activity-summary-card.tsx`,
  `activity-action-bar.tsx`, `activity-detail-skeleton.tsx`,
  `activity-detail-empty.tsx`.
- `src/components/shared/ui/`: `share-button.tsx` (Web Share with a
  copy-link fallback). The gallery lightbox reuses `modal.tsx`.
- `src/components/pages/activity-detail-page.tsx` becomes composition
  and data loading only.
- `src/components/shared/whatsapp-fab.tsx` hides on the activity route.
- `src/app/globals.css`: a `short` variant for viewports up to 500 px
  tall, used by the landscape-phone layout.
- Icons as files under `public/images/icons/`.
- Copy keys in `src/content/en.json`, `src/content/zh-HK.json`, and
  `src/content/types.ts`.
- JSON-LD gains age range, location, and image.
- Tests: `tests/components/activity-detail-page.test.tsx` asserts the
  full record, each sparse record, loading, not found, and the
  two-venue record. `e2e/activity-detail-layout.spec.ts` asserts, at
  the six viewports, that the `h1`, price, and enquiry action are
  inside the first screen and that nothing overflows sideways.

### Phase 2: cards and search list (green)

- `listing-card.tsx` (new fact order, single link, chips),
  `listing-row-card.tsx` (new, phone list), `listing-grid.tsx`
  (columns per viewport), `listing-card-mini-map.tsx`.
- `search-results-page.tsx` and a new
  `sections/search/search-results-summary.tsx` (active filters).
- `filter-chip-row.tsx`, `src/lib/activities/search-params.ts`, and
  `search-client.ts`: free, day, and language filters. The day chip
  converts the Hong Kong day to the stored UTC day. The age default
  becomes visible and removable.
- `shared/ui/carousel.tsx`: arrow buttons, 44 px targets.
- `navbar.tsx`: the header stops sticking on short viewports.
- `staging-search.ts`: the same new filters, so fixture mode matches.
- Tests: `listing-card`, `search-results-page`, `filter-chip-row`,
  `carousel`, `activities-search-params`, `staging-search`.

### Phase 3: search map (green)

- `search-map-split-layout.tsx` (layout per viewport, bottom sheet,
  in-list loading), `search-map-list-item.tsx` (facts and "View"),
  `search-view-toggle.tsx` (segmented control in the chip row),
  `shared/maps/activity-google-map.tsx` (pin backing, selected state,
  grouping, hover), `whatsapp-fab.tsx` (hidden on the map view).
- Marker artwork as files under `public/images/markers/`.
- Tests: `search-map-split-layout`, `activity-google-map`,
  `search-view-toggle`, `whatsapp-surfaces`.

### Phase 4: additive API fields (yellow)

Only what phases 1 to 3 cannot do with today's response.

- `location.name` (venue label) and `organization.updated_at` in
  `backend/src/app/api/schemas.py` and `search_page.py`.
- `organization_id` query parameter for "More from this organiser".
  `ActivitySearchFilters.org_ids` already exists in
  `backend/src/app/db/queries.py`. The work is
  `search_validation.py`, `search.py`, and
  `backend/src/app/services/staging_search_store.py`.
- Filters the website cannot build from today's parameters: free
  trial, several days in one request (weekend), and a price band that
  compares like with like (per class). Each is one filter in
  `queries.py` with its validation.
- A total count on the first page and a `sort` parameter (price, or
  distance from a point). Search is ordered by session time today
  (`docs/api/search.yaml`), and the cursor encodes that order, so sort
  is the largest item here and can be split into its own plan.
- `docs/api/search.yaml`, then `python3 scripts/check_openapi_routes.py`.
- Tests first: `tests/test_search_handler.py`,
  `tests/test_search_validation.py`, `tests/test_staging_search_store.py`.
- Website: `types.ts`, `map-listing.ts`, `activity-location.tsx`,
  `activity-organiser.tsx`, and the staging fixture generator
  `scripts/codegen/generate_activity_search_staging.py`.

## Invariants this change preserves

- `output: 'export'` stays. No route handlers, server actions, or
  per-request rendering.
- No inline `<svg>`, no `style=` in JSX, no `dangerouslySetInnerHTML`.
  Sizes come from classes. Artwork lives in `public/images/`.
- Copy lives in `src/content/*.json` in both locales. Tests live in
  `apps/public_www/tests/`.
- `NEXT_PUBLIC_*` is read only through `src/lib/site-config.ts`.
- Analytics events keep their names and fields: `view_item`,
  `generate_lead` with lead type `whatsapp_activity`, and `search`.
- Search URLs and `?id=` activity links that exist today keep working.
- API changes are additive. A caller that ignores the new fields and
  parameter gets today's response.
- Card view stays small: new card facts come from fields already in
  the card response.
- No real names, phone numbers, or addresses in fixtures or tests.

## Done when

- Phase 0: `npm run lint`, `npm run typecheck`, and `npm test` pass in
  `apps/public_www`. On `/en/`, a record with a `zh` name shows its
  English name. A session stored as Monday 120 to 180 UTC shows
  "Mon 10:00–11:00". A two-venue activity shows one card and both
  venues on its page.
- Phase 1: the same three commands pass, plus
  `npx playwright test e2e/activity-detail-layout.spec.ts`. Browser
  check at the six viewports in both locales for the full, sparse,
  loading, and not-found states.
- Phases 2 and 3: the same commands, the smoke run, and a browser
  check of list and map at the six viewports with a real Maps key.
- Phase 4: `pytest tests/test_search_handler.py
  tests/test_search_validation.py tests/test_staging_search_store.py`
  with `TEST_DATABASE_URL` set, `python3 scripts/check_openapi_routes.py`,
  and `pre-commit run ruff-format --all-files`.
- After release: the share of `view_item` sessions that reach
  `generate_lead` is compared with the four weeks before.

## Rollback

Each phase is a separate pull request and reverts on its own. Phase 4
is additive, so the website can be reverted without a backend revert.

## Open questions

1. Are organisation website, social links, and contact details meant
   to be public? If yes, they join phase 4 and the Organiser section.
2. Is approved parent feedback meant to be public? If yes, it needs
   its own plan: a rating summary on the card and a reviews section.
3. What backs "Parent-Verified"? This plan removes it from cards
   unless there is a per-listing signal.
4. Should search default to all ages instead of "3-6 years"? This plan
   keeps the default and makes it visible.
5. Do production records carry `zh`, `zh-HK`, or both? Phase 0 reads
   both in that order for `zh-HK`.
