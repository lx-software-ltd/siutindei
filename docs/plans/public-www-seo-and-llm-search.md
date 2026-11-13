# Plan: SEO and LLM-search visibility for the public website

**Status**: Approved, in progress
**Zone**: mixed. Workstreams A, C, and F are green
(`apps/public_www/**`, `docs/**`). Workstream B is green in the app
and red wherever it touches `scripts/deploy/**`,
`backend/infrastructure/**`, or a deploy workflow, and yellow if the
backend gains a catalogue export. Workstream D edits
`scripts/cloudflare/**`, which `docs/plans/cloudflare-edge-protection.md`
treats as green. Red slices need explicit approval before any write.

The evidence is in `docs/research/public-www-seo-and-llm-search.md`.

## Decisions

The owner answered the open questions on 13 Nov 2026 and approved the
red slices listed under "Files".

1. Snapshot source: option 1. A backend job writes the snapshot to a
   private S3 object.
2. Activity pages make the public catalogue readable in HTML.
3. Search and user-action crawlers are allowed; training crawlers stay
   blocked.
4. Landing pages use a new top-level route, `/<locale>/activities/`.

Still open: rebuild cadence (question 5) and `sameAs` profiles
(question 6). Until question 5 is answered the snapshot is read at
each production promotion; activities newer than the last promotion
use the `?id=` page. `sameAs` uses `NEXT_PUBLIC_INSTAGRAM_URL` when it
is set.

### Snapshot design

- `CatalogueSnapshotFunction` runs every hour from EventBridge. It
  pages through the public search query (`view=full`,
  `include_incomplete=true`, the configured `SEARCH_AREA_SCOPE`) with
  the read-only `siutindei_app` role and writes
  `public-www/catalogue-snapshot.json` to a private, versioned bucket.
  The body is the concatenated `items` of every page plus
  `area_scope`, so it has exactly the fields the public search API
  returns. The object is rewritten only when its content hash changes.
- The function, bucket, and schedule sit in a nested stack, because the
  API stack is at 494 of CloudFormation's 500 resources. The parent
  exports the bucket name as `PublicWwwCatalogueSnapshotBucketName`.
- The promote workflow downloads the object before `next build` and
  sets `PUBLIC_WWW_CATALOGUE_SNAPSHOT_PATH` and
  `PUBLIC_WWW_CATALOGUE_SNAPSHOT_REQUIRED=true`, so a production build
  fails without it. The staging workflow derives the snapshot from the
  staging fixture while the fixture is on, capped to keep the deploy
  short, and downloads the object when the fixture is off.

### What shipped and what changed from this plan

Shipped in the catalogue-pages change: workstreams A, B, D, and the
tests and checklist steps of F.

- Home page: instead of seeding the carousels with initial data, a
  server-rendered "Children's activities in <place>" section links to
  the hub, each type page, and twelve activities. The carousels still
  load on the client. This meets the same goal with no change to the
  search hook.
- Landing pages exist per activity type only. The scope is one place
  (Stanley), so a page per area would repeat the hub.
- Landing-page introductions are templates over catalogue facts, not
  text written by a person. Replace them when someone writes them.
- `AboutPage` JSON-LD, workstream C (about-page answer text and
  questions), the build-output test, the Playwright test, the
  Lighthouse URLs, `llms.txt`, and IndexNow are not done. The about
  page is written in the owner's voice, so new text there needs the
  owner.
- Workstream D keeps `ai_bots_protection: block` next to the new
  `ai_training`, `ai_search`, and `ai_user` fields. Dropping it from
  the policy file would not change the zone, because the tool only
  writes the keys the file names.
- Organization `logo` is the square SVG mark, the only square logo in
  the repository. Check it in the Rich Results Test after launch and
  add a raster logo of at least 112 x 112 pixels if Google rejects it.

## Goal

Search engines and AI search products can read, index, and cite the
catalogue, not only the brand pages.

- Every activity has its own URL with its own title, description,
  canonical, share image, and structured data in the HTML the server
  sends.
- The home page and one landing page per area and category list
  activities as plain links in that HTML.
- No indexable URL depends on a request that `robots.txt` disallows.
- Launch includes the steps that get the site into Google and Bing
  and lets us measure the result.

## Non-goals

- Moving off static export to server rendering.
- Serving different HTML to crawlers than to visitors.
- Opening `/v1/` to crawlers or weakening the edge rules that limit
  bulk extraction from the search API.
- Paid search, link buying, or content written only for crawlers.
- Changing which fields the search API returns.

## Order of work

| Step | Workstream | Why this position |
| --- | --- | --- |
| 1 | A. On-page fixes | Small, green, and safe to ship before launch |
| 2 | F. Launch checklist and tests | Must be in place at the first promotion |
| 3 | D. Crawler policy | Config only; makes current behaviour explicit |
| 4 | B. Crawlable catalogue | Largest effect; needs a decision on the data source and red-zone approval |
| 5 | C. Entity and answer content | Builds on B's pages |
| 6 | E. Off-site and measurement | Starts at launch and continues |

## Workstream A: on-page fixes

All in `apps/public_www`. Tests first.

1. **Titles.** Remove the brand from the `seo.*.title` strings and let
   `buildPageTitle` add it once. Target shape: "Privacy Policy · Siu
   Tin Dei". Keep the home title as is.
2. **Chinese brand name.** Use "小天地 Siu Tin Dei" as the brand in
   `zh-HK` titles, descriptions, and the share-image alt text.
3. **Meta descriptions.** Rewrite to 120 to 155 characters in English
   and 60 to 80 characters in Chinese, each naming the area served
   (Stanley and the Southern District today), the audience, and what
   the page offers. Do not promise coverage the area scope does not
   deliver.
4. **Home heading.** Put the descriptive phrase in visible text: keep
   the slogan as the H1 and make the sub-heading carry "children's
   activities in Stanley, Hong Kong", or swap them. Remove the
   `sr-only` paragraph in `discovery-home-page.tsx` so no text is
   hidden from visitors but shown to crawlers.
5. **Thin shells.** Set `/<locale>/search/` and `/<locale>/activity/`
   to `noindex, follow` and remove `/search/` from the sitemap until
   workstream B gives them server-sent content. In
   `activity-detail-page.tsx`, add a `noindex` robots meta tag when the
   state is not-found or error.
6. **Open Graph locale.** Emit `en_HK` and `zh_HK`, plus
   `og:locale:alternate` for the other locale.
7. **Sitemap.** Add hreflang alternates to every entry, drop
   `changeFrequency` and `priority`, and set `lastModified` from a
   per-route date that changes only when the content does (the legal
   pages already carry a "last updated" date).
8. **`robots.txt`.** Drop the `Host:` line.
9. **Structured data.** Extend `inject-structured-data.mjs`:
   - `Organization`: `alternateName` ("小天地"), a square logo of at
     least 112 x 112 pixels, `sameAs` for each official profile,
     `contactPoint` using the public contact address from the build
     environment, and `areaServed`.
   - `WebSite`: `alternateName`. Do not add `SearchAction`; Google
     retired the sitelinks search box.
   - About pages: `AboutPage` with `BreadcrumbList`.
   - Regenerate the CSP hashes in the same build step, as today.
10. **404 page.** Give it its own title and description.
11. **Image alt text.** Give listing photos an alt of the activity
    name and the organisation name. Decorative icons keep `alt=""`.
12. **Accessibility findings from Lighthouse** that also affect
    crawlers' reading of structure: heading order on the search page
    and `<dl>` structure on the activity page.

## Workstream B: crawlable catalogue

### B1. Build-time catalogue snapshot

The build needs a JSON snapshot of the published activities in the
public area scope, in both locales. Options, in order of preference:

| Option | How | Cost |
| --- | --- | --- |
| 1. Snapshot object | A backend job writes the public search response for the scope to a private S3 object when the catalogue changes; the deploy workflow downloads it before `next build` | Yellow backend work plus a red workflow edit; no new public surface |
| 2. Partner search | The build calls `/v1/partner/activities/search` with a read-only key held as a GitHub secret | The partner path skips the public area scope, so the build must apply it; a long-lived key in CI |
| 3. Public search with a skip rule | The build calls the public path with a secret header that a Cloudflare rule exempts | Adds a bypass to the edge rules the anti-scraping plan depends on |

Whichever is chosen, the snapshot contains only the fields the public
search response already returns, and the build fails if the snapshot
is missing or empty in production mode.

### B2. Per-activity pages

- Restore `src/app/[locale]/activity/[id]/page.tsx` along the lines of
  the code removed in `44d31ef6`: `generateStaticParams` from the
  snapshot, server-rendered detail through an `initialListing` prop,
  and `generateMetadata` per activity.
- Per-activity metadata: title "<activity> · <organisation> · Siu Tin
  Dei", a description built from category, age range, area, and the
  first sentence of the description, a self-referencing canonical,
  hreflang to the other locale, and `og:image` set to the first photo
  with the site image as the fallback.
- Structured data in the exported HTML (hashed for the CSP like the
  home page): `Course` with `provider`, `description`, `image`,
  `inLanguage`, `audience` with suggested ages, `offers` with price
  and currency, a `hasCourseInstance` per schedule with the venue as
  a `Place` with address and coordinates, and a `BreadcrumbList`. Add
  `aggregateRating` only for ratings collected by Siu Tin Dei, and
  check Google's review snippet rules first.
- URL: `/<locale>/activity/<id>/`. A readable slug can be added later
  as `/<slug>-<short id>/` once names are stable; do not block on it.
- `listing-card.tsx` links to the static URL when the id is in the
  build's snapshot and to `?id=` otherwise. The `?id=` shell stays as
  the fallback for activities newer than the last build, stays
  `noindex`, and redirects on the client to the static URL when one
  exists.
- An activity that leaves the catalogue drops out of the next build
  and then returns a real 404.
- Deploy time: export only the activities in the production scope.
  Staging uses the same route with a capped sample of the fixture so
  staging and production have the same shape, which was the aim of
  #828.

### B3. Home and landing pages

- Home: pass the first rows of each carousel from the snapshot as
  initial data so the exported HTML contains the activity names and
  links. The client refresh stays.
- Landing pages: one static page per area in scope and one per area
  and top-level category, for example "Art classes for children in
  Stanley". Each has a unique H1, a two or three sentence introduction
  written by a person, the list of activities as server-rendered
  cards, `ItemList` and `BreadcrumbList` structured data, and links to
  sibling pages. Generate a page only when it has at least three
  activities, to avoid thin pages.
- Route choice: nesting under the existing `/activity/` prefix avoids
  touching the CloudFront path function. A new top-level route such as
  `/activities/` reads better but needs `UNPREFIXED` in
  `public-www-path-rewrite.js`, `REDIRECT_HTML_FILES` in
  `inject-static-redirects.mjs`, and `invalidate_distribution()` in
  `deploy-public-www.sh`, which are red.
- Link to the landing pages from the home page, the footer, and each
  activity's breadcrumb, so every activity is at most two clicks from
  home.
- `/search/` stays `noindex, follow`. Filter combinations are not
  indexable pages.

### B4. Sitemap and freshness

- Add activity and landing-page URLs to the sitemap with hreflang
  alternates and `lastModified` from the activity's `updated_at`.
- Rebuild and promote when the catalogue changes: either on a
  schedule or triggered by a catalogue publish. Both are deploy
  workflow changes (red).

## Workstream C: entity and answer content

1. Add a short "What is Siu Tin Dei" block to the about page in plain
   sentences: what it is, who runs it (the legal entity already named
   on the legal pages), which areas it covers today, how a listing
   gets checked, and that it is free for families. AI search products
   quote text like this.
2. Add a questions-and-answers section to the about page and to each
   landing page, answering what parents ask ("What can a three year
   old do in Stanley on a weekday?") from catalogue facts. Mark it up
   only as visible text; do not rely on `FAQPage` rich results, which
   Google limits to a few site types.
3. Use one name everywhere: "Siu Tin Dei" in English and "小天地 Siu
   Tin Dei" in Chinese, matching the `Organization` node.
4. Keep `zh-HK` pages in Chinese. Where an activity has no Chinese
   name or description, the data-quality translation work
   (`docs/plans/data-quality-translations.md`) is the fix; track the
   share of untranslated activities as a launch metric.
5. Optional and low priority: generate `/llms.txt` from the same
   snapshot, listing the about page and landing pages. No major AI
   search provider has confirmed that it reads the file.

## Workstream D: crawler policy

1. Read the zone's current AI crawler settings and record them in
   `docs/plans/cloudflare-edge-protection.md`.
2. Replace the legacy `ai_bots_protection` field in
   `scripts/cloudflare/public_www_edge_policy.json` with the explicit
   per-purpose settings: allow AI search crawlers, allow user-action
   fetchers, block training crawlers. Extend
   `tests/lib/cloudflare-edge-policy.test.ts`.
3. Make sure Cloudflare's managed `robots.txt` is off, so the file the
   build emits is the one crawlers get.
4. Mirror the decision in `robots.ts` with named groups: allow
   `OAI-SearchBot`, `ChatGPT-User`, `PerplexityBot`,
   `Claude-SearchBot`, and `Claude-User`; disallow `GPTBot`,
   `ClaudeBot`, `CCBot`, `Google-Extended`, `Applebot-Extended`, and
   `Bytespider`. `Google-Extended` does not affect Google Search or
   AI Overviews. Named groups replace the `*` group for those bots, so
   repeat the `/v1/` and `/cdn-cgi/` rules in each allowed group.
5. Keep `/v1/` disallowed. After workstream B no indexable page needs
   it.

The allow or block choice for training crawlers is a business
decision (open question 4).

## Workstream E: off-site and measurement

1. At launch: verify the domain in Google Search Console and Bing
   Webmaster Tools, submit the sitemap, and inspect one home, one
   landing, and one activity URL in each tool's live test.
2. Bing matters for AI search: Copilot uses the Bing index and OpenAI
   names Bing as one of its search providers. Add IndexNow (a key file under
   `public/` and a ping from the deploy workflow, which is red) once
   activity pages exist.
3. Create or claim the official profiles that `sameAs` points to, and
   ask listed organisations to link to their Siu Tin Dei page.
4. Measure monthly: indexed pages against sitemap URLs, impressions
   and clicks for non-brand queries, referrals from `chatgpt.com`,
   `perplexity.ai`, `copilot.microsoft.com`, and `gemini.google.com`
   in analytics, AI crawler requests in Cloudflare's AI crawl report,
   and a fixed list of ten parent questions asked in each AI search
   product, recording whether the site is cited.

## Workstream F: launch checklist and regression tests

1. Add SEO steps to section 8 of
   `docs/deployment/launch-checklist.md`: after promotion, confirm
   `robots.txt` is the built file and not the maintenance deny-all,
   the home page is `index, follow`, `sitemap.xml` returns 200, both
   webmaster tools are verified, and the sitemap is submitted.
2. Unit tests for `seo.ts`, `sitemap.ts`, and the content strings: no
   doubled brand, title and description length bounds, unique titles
   per locale, hreflang pairs reciprocal.
3. A build-output test that reads `out/**/*.html` without a browser
   and asserts: every indexable page has an H1 and a self-referencing
   canonical; after workstream B, the home page has activity links and
   each activity page has its name in the H1 and `Course` JSON-LD.
4. One Playwright test that loads the home page and an activity page
   with `/v1/**` aborted and asserts no error state is shown. This is
   the check Lighthouse cannot do.
5. Add an activity page and a landing page to `.lighthouserc.json`.

## Files

Green:

- `apps/public_www/src/lib/seo.ts`, `src/lib/routes.ts`,
  `src/app/robots.ts`, `src/app/sitemap.ts`
- `apps/public_www/src/content/en.json`, `zh-HK.json`
- `apps/public_www/src/app/[locale]/**/page.tsx`, new
  `activity/[id]/page.tsx` and landing-page routes
- `apps/public_www/src/components/pages/*`,
  `sections/listings/listing-card.tsx`,
  `sections/hero/small-world-hero.tsx`
- `apps/public_www/scripts/inject-structured-data.mjs`,
  `inject-static-redirects.mjs`
- `apps/public_www/tests/**`, `e2e/**`, `.lighthouserc.json`
- `scripts/cloudflare/public_www_edge_policy.json`
- `docs/architecture/public-www.md`,
  `docs/deployment/launch-checklist.md`

Yellow, only for snapshot option 1: a backend export job and its
tests.

Red, approval needed first:

- `scripts/deploy/deploy-public-www.sh` and the deploy and promote
  workflows (snapshot download, rebuild trigger, IndexNow ping,
  invalidation paths)
- `backend/infrastructure/lib/functions/public-www-path-rewrite.js`,
  only if a new top-level route is chosen

## Invariants this change preserves

- Static export with `trailingSlash: true`; no server runtime.
- The CSP meta tag: no inline script without a build-time hash, no
  `dangerouslySetInnerHTML`, no inline `<svg>`, no `style=`.
- Crawlers and visitors receive the same HTML.
- `/v1/` stays disallowed in `robots.txt`, and the edge rules on
  `/v1/activities/search` stay as they are.
- Staging stays out of indexes (`X-Robots-Tag` and deny-all
  `robots.txt`).
- Pages expose only fields the public search API already returns, and
  only for activities in the public area scope.
- No real personal data in source, fixtures, or docs.

## Done when

- `npm run lint`, `npm run typecheck`, and `npm test` pass in
  `apps/public_www`.
- With JavaScript off, `/en/` and `/zh-HK/` contain at least 12
  activity links, and an activity URL returns the activity name in the
  H1, a self-referencing canonical, a per-activity `og:title` and
  `og:image`, and `Course` JSON-LD.
- With `/v1/**` aborted, no indexable page shows an error state.
- No title contains the brand twice; every indexable page has a
  unique title and description.
- `sitemap.xml` lists every activity and landing page with hreflang
  alternates and no `noindex` URL.
- An unknown activity path returns 404; the `?id=` shell is `noindex`.
- Google's Rich Results Test accepts the home and activity structured
  data, and URL Inspection shows the activity text in the rendered
  HTML.
- The launch checklist has the SEO steps and they are ticked at
  promotion.

## Rollback

Each workstream is separate commits. Workstream A and F revert
cleanly. For workstream B, reverting the route and the card link
restores the `?id=` behaviour; removed pages then return 404 and drop
out of indexes on recrawl, so keep the sitemap in step with the
revert. Workstream D reverts by restoring the previous policy file and
applying it.

## Open questions

1. Which catalogue snapshot source (B1)?
2. Is it acceptable that activity pages make the public catalogue
   readable page by page in HTML?
3. Nest landing pages under `/activity/` (green) or add a top-level
   route (red)?
4. Block or allow AI training crawlers? The plan assumes search and
   user-action crawlers are allowed and training crawlers are blocked.
5. Rebuild on a schedule or on catalogue publish, and how often?
6. Which official profiles exist for `sameAs`?
