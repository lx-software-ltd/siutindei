import { describe, expect, it } from 'vitest';

import type { GeographicAreaNode } from '@/lib/api-client';
import { matchNominatimAddress } from '@/hooks/use-geographic-areas';

function area(
  id: string,
  name: string,
  level: GeographicAreaNode['level'],
  children: GeographicAreaNode[] = [],
  code: string | null = null,
  lat: number | null = null,
  lng: number | null = null
): GeographicAreaNode {
  return {
    id,
    parent_id: null,
    name,
    name_translations: {},
    level,
    code,
    active: true,
    display_order: 1,
    lat,
    lng,
    children,
  };
}

const causewayBay = area('hood-cb', 'Causeway Bay', 'neighbourhood', [], null, 22.2803, 114.1846);
const wanChai = area('district-wc', 'Wan Chai', 'district', [causewayBay]);
const island = area('region-hki', 'Hong Kong Island', 'region', [wanChai]);
const hongKong = area('country-hk', 'Hong Kong', 'country', [island], 'HK');
const orchard = area('district-or', 'Orchard', 'district');
const singapore = area('country-sg', 'Singapore', 'country', [orchard], 'SG');

describe('matchNominatimAddress', () => {
  it('returns a Hong Kong neighbourhood and skips the parent district', () => {
    const match = matchNominatimAddress([hongKong], {
      country_code: 'hk',
      state: 'Hong Kong Island',
      city_district: 'Wan Chai',
      suburb: 'Causeway Bay',
    });

    expect(match?.areaId).toBe('hood-cb');
    expect(match?.chain.map((node) => node.name)).toEqual([
      'Hong Kong',
      'Hong Kong Island',
      'Wan Chai',
      'Causeway Bay',
    ]);
  });

  it('snaps a district match to the nearest neighbourhood when a pin is set', () => {
    const match = matchNominatimAddress(
      [hongKong],
      {
        country_code: 'hk',
        state: 'Hong Kong Island',
        city_district: 'Wan Chai',
      },
      { lat: 22.2803, lng: 114.1846 }
    );

    expect(match?.areaId).toBe('hood-cb');
  });

  it('drops a district match when that district still has neighbourhoods', () => {
    const match = matchNominatimAddress([hongKong], {
      country_code: 'hk',
      state: 'Hong Kong Island',
      city_district: 'Wan Chai',
    });

    expect(match).toBeNull();
  });

  it('keeps a childless district', () => {
    const match = matchNominatimAddress([singapore], {
      country_code: 'sg',
      city: 'Orchard',
    });

    expect(match?.areaId).toBe('district-or');
  });
});
