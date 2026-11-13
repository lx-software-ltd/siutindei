export const ROUTES = {
  home: '/',
  about: '/about',
  search: '/search',
  activity: '/activity',
  activities: '/activities',
  privacy: '/privacy',
  terms: '/terms',
} as const;

export type AppRoutePath = (typeof ROUTES)[keyof typeof ROUTES];

/**
 * Brand pages in the sitemap. Activity and landing pages are added from
 * the catalogue. `/search/` and the `?id=` activity page are `noindex`.
 */
export const INDEXED_ROUTE_PATHS: readonly AppRoutePath[] = [
  ROUTES.home,
  ROUTES.about,
  ROUTES.activities,
  ROUTES.privacy,
  ROUTES.terms,
];

/** Not pages: the proxied search API and Cloudflare's challenge platform. */
export const ROBOTS_DISALLOWED_PATHS = ['/v1/', '/cdn-cgi/'] as const;

/**
 * AI search and user-action fetchers. They may read pages so answers can
 * cite them. Named groups replace `*`, so each repeats the disallows.
 */
export const AI_SEARCH_USER_AGENTS = [
  'OAI-SearchBot',
  'ChatGPT-User',
  'PerplexityBot',
  'Perplexity-User',
  'Claude-SearchBot',
  'Claude-User',
] as const;

/**
 * Model-training crawlers. `Google-Extended` and `Applebot-Extended` are
 * training opt-outs only; they do not affect Google or Apple search.
 */
export const AI_TRAINING_USER_AGENTS = [
  'GPTBot',
  'ClaudeBot',
  'CCBot',
  'Google-Extended',
  'Applebot-Extended',
  'Bytespider',
] as const;
