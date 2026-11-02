export const ROUTES = {
  home: '/',
  about: '/about',
  search: '/search',
  activity: '/activity',
  privacy: '/privacy',
  terms: '/terms',
} as const;

export type AppRoutePath = (typeof ROUTES)[keyof typeof ROUTES];

export const INDEXED_ROUTE_PATHS: readonly AppRoutePath[] = [
  ROUTES.home,
  ROUTES.about,
  ROUTES.search,
  ROUTES.privacy,
  ROUTES.terms,
];

/**
 * Not pages: the proxied search API and Cloudflare's challenge platform.
 * AI crawlers are blocked at the Cloudflare edge
 * (scripts/cloudflare/public_www_edge_policy.json), not by robots.txt.
 */
export const ROBOTS_DISALLOWED_PATHS = ['/v1/', '/cdn-cgi/'] as const;
