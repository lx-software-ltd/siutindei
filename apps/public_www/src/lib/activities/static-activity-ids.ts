/**
 * Ids of activities the build pre-rendered, read once per page load from
 * `/activity-pages.json`. Until it arrives, or if it fails, cards keep the
 * `?id=` link, which works for every activity.
 */

export const STATIC_ACTIVITY_IDS_PATH = '/activity-pages.json';

const EMPTY: ReadonlySet<string> = new Set();

let ids: ReadonlySet<string> = EMPTY;
let request: Promise<ReadonlySet<string>> | null = null;
const listeners = new Set<() => void>();

function load(): Promise<ReadonlySet<string>> {
  if (request) {
    return request;
  }
  request = fetch(STATIC_ACTIVITY_IDS_PATH, { headers: { Accept: 'application/json' } })
    .then(async (response) => {
      if (!response.ok) {
        return EMPTY;
      }
      const payload = (await response.json()) as { ids?: unknown };
      return Array.isArray(payload.ids)
        ? new Set(payload.ids.filter((id): id is string => typeof id === 'string'))
        : EMPTY;
    })
    .catch(() => EMPTY)
    .then((loaded) => {
      ids = loaded;
      for (const listener of listeners) {
        listener();
      }
      return loaded;
    });
  return request;
}

export function subscribeStaticActivityIds(listener: () => void): () => void {
  listeners.add(listener);
  if (typeof window !== 'undefined' && typeof fetch === 'function') {
    void load();
  }
  return () => {
    listeners.delete(listener);
  };
}

export function getStaticActivityIds(): ReadonlySet<string> {
  return ids;
}

export function getServerStaticActivityIds(): ReadonlySet<string> {
  return EMPTY;
}

export function loadStaticActivityIds(): Promise<ReadonlySet<string>> {
  return load();
}

export function resetStaticActivityIdsForTests(): void {
  ids = EMPTY;
  request = null;
  listeners.clear();
}
