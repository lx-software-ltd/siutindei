import { describe, expect, it } from 'vitest';

import {
  CATALOG_MAPS_KEY_REFERRERS,
  catalogMapSurface,
} from '@/lib/catalog-map-surface';

describe('catalogMapSurface', () => {
  it('uses Google Maps when the key is accepted', () => {
    expect(
      catalogMapSurface({ apiKey: 'maps-key', authRefused: false, loadFailed: false })
    ).toBe('google');
  });

  it('uses OpenStreetMap when Google refuses this host', () => {
    expect(
      catalogMapSurface({ apiKey: 'maps-key', authRefused: true, loadFailed: false })
    ).toBe('osm');
  });

  it('uses OpenStreetMap when the key is missing or the script fails', () => {
    expect(
      catalogMapSurface({ apiKey: '', authRefused: false, loadFailed: false })
    ).toBe('osm');
    expect(
      catalogMapSurface({ apiKey: 'maps-key', authRefused: false, loadFailed: true })
    ).toBe('osm');
  });

  it('lists the admin hosts the public Maps key must allow', () => {
    expect(CATALOG_MAPS_KEY_REFERRERS).toEqual([
      'https://siutindei.lx-software.com/*',
      'http://localhost:3000/*',
    ]);
  });
});
