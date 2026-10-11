import { describe, expect, it } from 'vitest';

import {
  organizationsWithoutMapPins,
  pinsForOrganizations,
} from '@/lib/catalog-map-pins';
import { neighbourhoodFilterOptions } from '@/lib/neighbourhood-options';
import type { GeographicAreaNode } from '@/lib/api-client-user';

function area(
  partial: Pick<GeographicAreaNode, 'id' | 'name' | 'level'> & {
    children?: GeographicAreaNode[];
  }
): GeographicAreaNode {
  return {
    parent_id: null,
    name_translations: {},
    code: null,
    active: true,
    display_order: 0,
    children: [],
    ...partial,
  };
}

describe('neighbourhoodFilterOptions', () => {
  it('lists neighbourhoods under their district and keeps a leaf district', () => {
    const options = neighbourhoodFilterOptions([
      area({
        id: 'hk',
        name: 'Hong Kong',
        level: 'country',
        children: [
          area({
            id: 'island',
            name: 'Hong Kong Island',
            level: 'region',
            children: [
              area({
                id: 'wanchai',
                name: 'Wan Chai',
                level: 'district',
                children: [
                  area({
                    id: 'causeway',
                    name: 'Causeway Bay',
                    level: 'neighbourhood',
                  }),
                ],
              }),
            ],
          }),
        ],
      }),
      area({
        id: 'sg',
        name: 'Singapore',
        level: 'country',
        children: [
          area({
            id: 'central',
            name: 'Central',
            level: 'district',
          }),
        ],
      }),
    ]);

    expect(options).toEqual([
      { id: 'causeway', name: 'Causeway Bay', group: 'Wan Chai' },
      { id: 'central', name: 'Central', group: 'Singapore' },
    ]);
  });
});

describe('pinsForOrganizations', () => {
  it('keeps locations that have coordinates', () => {
    const pins = pinsForOrganizations([
      {
        id: 'org-1',
        name: 'Studio',
        map_locations: [
          {
            id: 'loc-1',
            address: '1 Lane',
            area_name: 'Central',
            lat: 22.28,
            lng: 114.15,
          },
          { id: 'loc-2', address: 'No pin', area_name: 'Central', lat: null, lng: null },
        ],
      },
      { id: 'org-2', name: 'Unplaced', map_locations: [] },
    ]);

    expect(pins).toEqual([
      {
        id: 'loc-1',
        orgName: 'Studio',
        address: '1 Lane',
        areaName: 'Central',
        lat: 22.28,
        lng: 114.15,
        mapsUrl: 'https://www.google.com/maps/search/?api=1&query=22.28,114.15',
      },
    ]);
    expect(
      organizationsWithoutMapPins([
        {
          id: 'org-1',
          name: 'Studio',
          map_locations: [{ id: 'loc-1', lat: 1, lng: 2 }],
        },
        { id: 'org-2', name: 'Unplaced', map_locations: [] },
      ])
    ).toBe(1);
  });
});
