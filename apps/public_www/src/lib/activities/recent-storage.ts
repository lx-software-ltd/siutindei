import type { SearchFiltersState } from './search-params';

const RECENT_SEARCH_KEY = 'siutindei.recentSearch';
const RECENT_VIEWED_KEY = 'siutindei.recentViewed';
const RECENT_SEARCH_EVENT = 'siutindei-recent-search';
const MAX_RECENT = 8;

let recentSearchRaw: string | null | undefined;
let recentSearchSnapshot: SearchFiltersState | null = null;

export function subscribeRecentSearch(onStoreChange: () => void): () => void {
  window.addEventListener('storage', onStoreChange);
  window.addEventListener(RECENT_SEARCH_EVENT, onStoreChange);
  return () => {
    window.removeEventListener('storage', onStoreChange);
    window.removeEventListener(RECENT_SEARCH_EVENT, onStoreChange);
  };
}

export function getRecentSearchSnapshot(): SearchFiltersState | null {
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(RECENT_SEARCH_KEY);
  } catch {
    raw = null;
  }
  if (raw === recentSearchRaw) {
    return recentSearchSnapshot;
  }
  recentSearchRaw = raw;
  recentSearchSnapshot = parseRecentSearch(raw);
  return recentSearchSnapshot;
}

export function getRecentSearchServerSnapshot(): null {
  return null;
}

function parseRecentSearch(raw: string | null): SearchFiltersState | null {
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as SearchFiltersState;
  } catch {
    return null;
  }
}

export function loadRecentSearch(): SearchFiltersState | null {
  if (typeof window === 'undefined') {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(RECENT_SEARCH_KEY);
    if (!raw) {
      return null;
    }
    return JSON.parse(raw) as SearchFiltersState;
  } catch {
    return null;
  }
}

export function saveRecentSearch(filters: SearchFiltersState): void {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.localStorage.setItem(RECENT_SEARCH_KEY, JSON.stringify(filters));
    window.dispatchEvent(new Event(RECENT_SEARCH_EVENT));
  } catch {
    // Ignore quota errors.
  }
}

export function loadRecentViewedIds(): readonly string[] {
  if (typeof window === 'undefined') {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(RECENT_VIEWED_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((value): value is string => typeof value === 'string');
  } catch {
    return [];
  }
}

export function rememberViewedActivity(activityId: string): void {
  if (typeof window === 'undefined') {
    return;
  }
  const existing = loadRecentViewedIds().filter((id) => id !== activityId);
  const next = [activityId, ...existing].slice(0, MAX_RECENT);
  try {
    window.localStorage.setItem(RECENT_VIEWED_KEY, JSON.stringify(next));
  } catch {
    // Ignore quota errors.
  }
}
