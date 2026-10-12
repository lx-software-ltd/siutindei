export type CatalogMapSurface = 'google' | 'osm';

export function catalogMapSurface(state: {
  apiKey: string;
  authRefused: boolean;
  loadFailed: boolean;
}): CatalogMapSurface {
  if (!state.apiKey.trim() || state.authRefused || state.loadFailed) {
    return 'osm';
  }
  return 'google';
}

/** Hosts a human adds to the public Maps key so Catalog can use Google tiles. */
export const CATALOG_MAPS_KEY_REFERRERS = [
  'https://siutindei.lx-software.com/*',
  'http://localhost:3000/*',
] as const;
