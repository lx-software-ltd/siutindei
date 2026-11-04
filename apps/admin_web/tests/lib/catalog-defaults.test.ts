import { afterEach, describe, expect, it, vi } from 'vitest';

import type { GeographicAreaNode } from '@/lib/api-client-user';
import {
  DEFAULT_CATALOG_NEIGHBOURHOOD_NAME,
  areaIdForCatalogDefault,
} from '@/lib/catalog-defaults';

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

const stanleyTree = [
  area({
    id: 'hk',
    name: 'Hong Kong',
    level: 'country',
    children: [
      area({
        id: 'southern',
        name: 'Southern',
        level: 'district',
        children: [
          area({
            id: 'area-stanley',
            name: DEFAULT_CATALOG_NEIGHBOURHOOD_NAME,
            level: 'neighbourhood',
          }),
        ],
      }),
    ],
  }),
];

describe('areaIdForCatalogDefault', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('resolves a neighbourhood id from the area tree', () => {
    expect(areaIdForCatalogDefault(stanleyTree)).toBe('area-stanley');
  });

  it('ignores a district that shares the default name', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect(
      areaIdForCatalogDefault([
        area({
          id: 'sg',
          name: 'Singapore',
          level: 'country',
          children: [
            area({
              id: 'district-stanley',
              name: DEFAULT_CATALOG_NEIGHBOURHOOD_NAME,
              level: 'district',
            }),
          ],
        }),
      ])
    ).toBe('');
    expect(warn).toHaveBeenCalled();
  });

  it('returns empty without warning when the tree has not loaded', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect(areaIdForCatalogDefault([])).toBe('');
    expect(warn).not.toHaveBeenCalled();
  });

  it('returns empty and warns in development when the neighbourhood is missing', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect(
      areaIdForCatalogDefault([
        area({
          id: 'hk',
          name: 'Hong Kong',
          level: 'country',
          children: [
            area({
              id: 'causeway',
              name: 'Unrelated Neighbourhood',
              level: 'neighbourhood',
            }),
          ],
        }),
      ])
    ).toBe('');
    expect(warn).toHaveBeenCalledTimes(1);
    expect(String(warn.mock.calls[0]?.[0])).toContain(
      `Catalog default neighbourhood "${DEFAULT_CATALOG_NEIGHBOURHOOD_NAME}"`
    );
  });
});
