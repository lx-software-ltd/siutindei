/** Minimum listings the public discovery surface must support (acceptance). */
export const MIN_PUBLIC_LISTINGS = 10;

/** Client-side budget for loading discovery listings (acceptance, ms). */
export const DISCOVERY_LOAD_BUDGET_MS = 2000;

// Every search limit the site sends must be in the Cloudflare
// `search-limit-allowlist` rule (scripts/cloudflare/public_www_edge_policy.json);
// the edge blocks any other value before it reaches the API.

/** First discovery-home page. Further carousels render from this page. */
export const DISCOVERY_HOME_SEARCH_LIMIT = 24;

/** Search results page size. Further rows load with the API cursor. */
export const SEARCH_RESULTS_PAGE_LIMIT = 30;

/** Recent-search row on the home page. */
export const DISCOVERY_RECENT_SEARCH_LIMIT = 12;

/** Rows per page when loading every venue, price, and schedule of one activity. */
export const ACTIVITY_DETAIL_PAGE_LIMIT = 30;

/** Rows fetched for each related-activities carousel on the activity page. */
export const RELATED_ACTIVITIES_LIMIT = 24;
