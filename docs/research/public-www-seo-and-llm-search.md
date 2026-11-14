# Research: SEO and LLM-search posture of the public website

**Status**: Draft
**Zone**: this memo is green (`docs/**`). The follow-up work is mostly
green (`apps/public_www/**`), with red slices where a new top-level
route, the deploy script, or the CloudFront path function changes. The
plan is `docs/plans/public-www-seo-and-llm-search.md`.

## Summary

The site's static pages (home, about, privacy, terms) are technically
sound: unique canonicals, reciprocal hreflang, Open Graph and Twitter
tags, one H1, and a Lighthouse SEO score of 100. The catalogue is the
problem. Every activity name, description, price, and link is fetched
in the browser from `/v1/activities/search`, and `robots.txt`
disallows `/v1/`. No crawler can see any activity:

1. Crawlers that do not run JavaScript (AI search crawlers and link
   preview fetchers) receive an empty `<main>` on the search and
   activity routes and a home page with no activity links.
2. A crawler that does run JavaScript but obeys `robots.txt` for
   sub-requests, which is how Google documents its renderer, gets
   "Unable to load activities." on home and search, and an error page
   with HTTP 200 on every activity URL.
3. Every activity URL declares the same canonical
   (`/<locale>/activity/`), so even a fully rendered activity cannot be
   indexed as its own page, and its share preview is generic.

So the site can rank for its brand name and nothing else. It has no
page that can answer "children's activities in Stanley" in Google,
Bing, ChatGPT search, Perplexity, or Claude.

Production is in pre-launch maintenance mode today (deny-all
`robots.txt`, `noindex` page), so nothing is lost yet. The findings
describe what ships at promotion if nothing changes.

## Method

Run on 13 Nov 2026 (Hong Kong time) at commit `main` as of that day.

- **Static export audit.** Built `apps/public_www` in production mode
  (`NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED=false`) and parsed all 21
  HTML files in `out/` for title, description, robots, canonical,
  hreflang, Open Graph, headings, JSON-LD, word count in `<main>`, and
  image attributes.
- **Render audit.** Served `out/` behind a local stand-in for
  CloudFront (same path rewrite and 302 behaviour as
  `backend/infrastructure/lib/functions/public-www-path-rewrite.js`)
  with a mock `/v1/activities/search` backed by the staging fixture,
  scoped to Stanley (`NEXT_PUBLIC_SEARCH_AREA_SCOPE=southern-stanley`,
  26 fixture activities). Loaded 11 URLs in system Chrome through
  Playwright in three views: `raw` (JavaScript off), `crawler`
  (JavaScript on, requests matching the site's own `robots.txt`
  `Disallow` prefixes aborted), and `browser` (nothing blocked).
- **Lighthouse.** Mobile emulation against the same local server for
  five URLs.
- **Live probes.** `curl` against `https://siutindei.com` and
  `https://www-staging.siutindei.com` for status codes, headers,
  `robots.txt`, `sitemap.xml`, and 21 crawler user agents.
- **External facts.** Read the vendor documentation listed under
  "External references".

Not measured: real catalogue data (the fixture is synthetic), Search
Console or Bing Webmaster data (the site is not yet indexable),
verified-bot behaviour at Cloudflare (probes used spoofed user agents
from a non-crawler IP), and real-device performance. The `crawler`
view models Google's documented behaviour; it is not Googlebot.

## Entry points

- Metadata: `apps/public_www/src/lib/seo.ts` (`buildLocalizedMetadata`)
  called from each `src/app/[locale]/**/page.tsx`. Strings are in
  `src/content/en.json` and `zh-HK.json` under `seo`.
- Crawl control: `src/app/robots.ts`, `src/app/sitemap.ts`, and
  `INDEXED_ROUTE_PATHS` and `ROBOTS_DISALLOWED_PATHS` in
  `src/lib/routes.ts`.
- Structured data: `scripts/inject-structured-data.mjs` (build time,
  home pages only) and `src/components/pages/activity-detail-page.tsx`
  (client side, `Course`).
- Catalogue rendering: `src/components/pages/discovery-home-page.tsx`,
  `search-results-page.tsx`, `activity-detail-route.tsx`, all fed by
  `src/lib/activities/search-client.ts`.
- Edge: `scripts/cloudflare/public_www_edge_policy.json` and
  `backend/infrastructure/lib/public-www-stack.ts`.

## Owners

`apps/public_www/**` is green outside deploy scripts.
`backend/infrastructure/**` and `scripts/deploy/**` are red
(`docs/architecture/zones.md`). `scripts/cloudflare/**` is not listed
in the zone map; `docs/plans/cloudflare-edge-protection.md` treats the
policy tool as green.

## Findings

### 1. Catalogue content is invisible to crawlers (critical)

Measured on the local production-mode build. "Words" is visible text in
`<main>`; "links" is anchors to an activity.

| URL | View | Words | Links | H1 | JSON-LD |
| --- | --- | --- | --- | --- | --- |
| `/en/` | raw | 267 | 0 | slogan | Organization, WebSite |
| `/en/` | crawler | 257 | 0 | slogan | Organization, WebSite |
| `/en/` | browser | 633 | 12 | slogan | Organization, WebSite |
| `/en/search/` | raw | 0 | 0 | none | none |
| `/en/search/` | crawler | 53 | 0 | sr-only | none |
| `/en/search/` | browser | 833 | 26 | sr-only | none |
| `/en/activity/?id=…` | raw | 0 | 0 | none | none |
| `/en/activity/?id=…` | crawler | 27 | 0 | error text | none |
| `/en/activity/?id=…` | browser | 260 | 3 | activity name | Course |

The `zh-HK` rows show the same pattern. In the crawler view the home
page and search page print "Unable to load activities." and the
activity page prints "This activity won't come out of the steamer"
with HTTP 200, `index, follow`, and the generic title.

Causes:

- `search/page.tsx` and `activity/page.tsx` wrap a client component in
  `<Suspense fallback={null}>`, so the exported HTML has an empty
  `<main>`.
- `ROBOTS_DISALLOWED_PATHS` contains `/v1/`. Google states that it
  does not fetch disallowed resources while rendering and advises
  against blocking resources a page needs.
- The edge policy rate-limits `/v1/activities/search` to 15 requests
  per 10 seconds per IP and blocks tooling user agents. Removing the
  `robots.txt` rule alone would leave rendering dependent on those
  rules and would still do nothing for crawlers that do not run
  JavaScript.

This contradicts the stated intent in
`docs/plans/cloudflare-edge-protection.md` ("Cards stay public and
crawlable by search engines").

### 2. Activity pages cannot be indexed individually (critical)

- `listing-card.tsx` links to `/<locale>/activity/?id=<uuid>`. The
  route's metadata sets the canonical to `/<locale>/activity/` for
  every id, so all activities consolidate onto one empty shell.
- After the client fetch, `activity-detail-page.tsx` sets
  `document.title` and appends `Course` JSON-LD but leaves canonical,
  meta description, and all Open Graph tags generic. A WhatsApp or
  Facebook share of any activity shows the site-wide title and image.
- A missing or unknown id renders a not-found message with HTTP 200
  and `index, follow` (soft 404). Staging confirms this:
  `/en/activity/` returns 200, while an unknown path returns 404.
- The sitemap has no activity URLs.
- Per-activity static pages existed on staging only and were removed
  in `44d31ef6` (#828) because exporting 7,582 fixture activities took
  1.5 to 2 hours. Production never had them.

### 3. On-page issues on the static pages (medium)

| Issue | Evidence |
| --- | --- |
| Brand doubled in every non-home title, for example "Privacy Policy \| Siu Tin Dei · Siu Tin Dei" and "About Siu Tin Dei · Siu Tin Dei" | `buildPageTitle` appends ` · <site name>`; the content strings already end in the brand |
| Short, generic meta descriptions (home: 69 characters in English, 26 in Chinese; search zh-HK: 20) | `seo.*.description` |
| Chinese brand name 小天地 is absent from every title, description, and JSON-LD field, although the zh-HK body uses it | `zh-HK.json`, `inject-structured-data.mjs` |
| Home H1 is the slogan; the phrase "Discover children's activities in Hong Kong" is an `sr-only` paragraph | `small-world-hero.tsx`, `discovery-home-page.tsx` |
| `og:locale` is `en` and `zh-HK`; Open Graph expects `en_HK` and `zh_HK`; no `og:locale:alternate` | `seo.ts` |
| Sitemap: `lastmod` is the build time for every URL, no hreflang alternates, includes the empty search shell | `sitemap.ts` |
| `robots.txt` emits a `Host:` line, which no major engine uses | `robots.ts` |
| Structured data is on the home pages only. `Organization.logo` is the 1200 x 630 share image. No `alternateName`, `sameAs`, `contactPoint`, `BreadcrumbList`, `AboutPage`, or `ItemList` | `inject-structured-data.mjs` |
| The 404 page carries the home title and description and `lang="en"` | `out/404.html` |
| Listing photos render with `alt=""` | `listing-card.tsx` |
| The indexable `/search/` and `/activity/` shells are thin pages | Finding 1 |

### 4. LLM-search posture

- **Edge access.** The policy file sets the legacy
  `ai_bots_protection: block`. A probe of production with spoofed user
  agents returned 403 for GPTBot, ClaudeBot, Bytespider, CCBot, and
  Amazonbot, and 200 for Googlebot, bingbot, OAI-SearchBot,
  ChatGPT-User, Claude-SearchBot, Claude-User, PerplexityBot,
  Perplexity-User, Applebot, and the link-preview fetchers. Training
  crawlers appear blocked and search and user-agent crawlers appear
  admitted. This is not confirmed: Cloudflare also classifies verified
  bots by IP, and it has since split the setting into separate search,
  training, and user-action controls, which the policy file does not
  set.
- **Content.** Admitted crawlers find nothing to cite. OpenAI,
  Anthropic, and Perplexity describe their search crawlers as page
  fetchers; none documents JavaScript rendering, so this audit treats
  them as reading raw HTML. On that basis they see four static pages
  per locale and no activities.
- **Google AI features.** Google says a page must be indexed and
  eligible for a snippet to appear in AI Overviews or AI Mode, with no
  extra requirements. Activity content cannot meet that today.
- **Entity signals.** The `Organization` node has no alternate name,
  no profile links, and no contact point, and the site has no page
  that states in plain text what Siu Tin Dei is, which areas it
  covers, and how listings are checked, in a form that is easy to
  quote. The about page tells the founder story but does not list
  those facts.
- **`llms.txt`.** Absent. No major AI search provider has said it uses
  the file, so it is a low-priority extra.

### 5. Process gaps

- `docs/deployment/launch-checklist.md` section 8 has no SEO steps: no
  Search Console or Bing Webmaster verification, no sitemap
  submission, no check that `robots.txt` and the `noindex` tag flip at
  promotion.
- Lighthouse CI (`apps/public_www/.lighthouserc.json`) asserts SEO at
  0.9 or above on the two home pages. Lighthouse scored 100 for SEO on
  the search and activity pages too, so the score cannot catch
  finding 1.
- The maintenance page serves the same English page at `/zh-HK/`. It
  is `noindex`, so the effect is limited to visitors.

### 6. What already works

- Canonical, hreflang (`en`, `zh-HK`, `x-default`), Open Graph, and
  Twitter tags are present and correct on all ten localised pages.
- `www` and `http` redirect to the apex over HTTPS with a 301; unknown
  paths return a real 404.
- Staging is kept out of indexes by `X-Robots-Tag: noindex, nofollow,
  noarchive` (`public-www-stack.ts`) and a deny-all `robots.txt`.
- About, privacy, and terms are fully static with one H1 and H2
  sections.
- Lighthouse on the local build: home `/en/` scored 100 for
  performance and SEO; accessibility was 90 to 100 across the five
  URLs.

## Tests

- `apps/public_www/tests/app/robots.test.ts` covers `robots.ts`.
- `tests/lib/locale-routing.test.ts` and `site-config.test.ts` cover
  the path helpers.
- No test covers titles, descriptions, the sitemap, or what the
  exported HTML contains without JavaScript.
- `apps/public_www/e2e` runs against a browser with the API reachable,
  so it sees the visitor view only.

## Production signals

- `https://siutindei.com/robots.txt` is `User-agent: *` /
  `Disallow: /`; `/en/` and `/zh-HK/` serve the "Coming soon" page
  with `noindex, nofollow`; `/sitemap.xml`, `/en/about/`, and
  `/llms.txt` return 404.
- Staging serves the full site and returns 200 for `/en/activity/`
  with or without a valid id.
- Lighthouse on the local server reported a simulated mobile LCP of
  6.1 s on the activity page and 6.2 s on search, against 1.2 s on
  home. The LCP element on both is client-rendered text (the activity
  H1 and the first card title). The absolute values come from a local
  server and simulated throttling; the gap is the signal.

## History

- `44d31ef6` (#828) removed per-activity export, its static catalogue
  loader, and activity sitemap entries. The removed code
  (`generateStaticParams` from a catalogue file, a placeholder id,
  server-rendered `Course` JSON-LD, an `initialListing` prop) is the
  reference design for restoring them.
- `docs/plans/cloudflare-edge-protection.md` introduced the `/v1/`
  rate limit, the custom block rules, and the AI crawler block.
- `docs/plans/2026-11-10-search-area-scope.md` and
  `2026-11-11-catalog-search-area-scope.md` limit public search to
  Stanley, which keeps the production catalogue small.

## External references

- Google Search Central: "AI features and your website", "Introduction
  to robots.txt", "Fix Search-related JavaScript problems".
- OpenAI: "Overview of OpenAI crawlers" (OAI-SearchBot, GPTBot,
  ChatGPT-User).
- Anthropic: crawler help article (ClaudeBot, Claude-User,
  Claude-SearchBot).
- Perplexity: crawler documentation (PerplexityBot, Perplexity-User).
- Cloudflare: "AI Crawler and Agent access policies" and the bot
  reference.

## Open questions

1. Which source can a CI build read the production catalogue from?
   The public search path needs CloudFront's `X-Origin-Verify` header
   and is blocked for tooling user agents at Cloudflare.
2. Does the business accept that pre-rendered activity pages expose
   the same fields in HTML that the search API returns one page at a
   time? The edge plan says cards should be crawlable; this makes it
   explicit.
3. What are the real Cloudflare AI crawler settings on the zone? Read
   them from the dashboard or the bot management API.
4. Should training crawlers stay blocked while search and user-action
   crawlers are allowed? The probe suggests that is the current
   effect.
5. How complete are `zh-HK` translations in the real catalogue? The
   fixture shows English names on Chinese pages, which would weaken
   the Chinese pages if real data looks the same.
