import { afterEach, describe, expect, it, vi } from 'vitest';

import type { GeographicAreaNode } from '@/lib/api-client-user';
import {
  areaIdForCatalogDefault,
  areaNameInTree,
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

const tree = [
  area({
    id: 'hk',
    name: 'Hong Kong',
    level: 'country',
    children: [
      area({
        id: 'hki',
        name: 'Hong Kong Island',
        level: 'region',
        children: [
          area({
            id: 'southern',
            name: 'Southern',
            level: 'district',
            children: [
              area({
                id: 'stanley',
                name: 'Stanley',
                level: 'neighbourhood',
              }),
              area({
                id: 'shek-o',
                name: 'Shek O',
                level: 'neighbourhood',
              }),
            ],
          }),
          area({
            id: 'wan-chai-district',
            name: 'Wan Chai',
            level: 'district',
            children: [
              area({
                id: 'wan-chai',
                name: 'Wan Chai',
                level: 'neighbourhood',
              }),
              area({
                id: 'jardine',
                name: "Jardine's Lookout",
                level: 'neighbourhood',
              }),
            ],
          }),
        ],
      }),
      area({
        id: 'islands-region',
        name: 'Islands',
        level: 'region',
        children: [
          area({
            id: 'islands-district',
            name: 'Islands',
            level: 'district',
            children: [
              area({
                id: 'mui-wo',
                name: 'Mui Wo',
                level: 'neighbourhood',
              }),
            ],
          }),
        ],
      }),
      area({
        id: 'kowloon',
        name: 'Kowloon',
        level: 'region',
        children: [
          area({
            id: 'ytm',
            name: 'Yau Tsim Mong',
            level: 'district',
            children: [
              area({
                id: 'mong-kok',
                name: 'Mong Kok',
                level: 'neighbourhood',
              }),
            ],
          }),
        ],
      }),
    ],
  }),
];

describe('areaIdForCatalogDefault', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });

  it('reads SEARCH_AREA_SCOPE from the inlined public env', () => {
    vi.stubEnv('NEXT_PUBLIC_SEARCH_AREA_SCOPE', 'southern-stanley');
    expect(areaIdForCatalogDefault(tree)).toBe('stanley');
  });

  it('returns empty when the variable is blank', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect(areaIdForCatalogDefault(tree, '')).toBe('');
    expect(areaIdForCatalogDefault(tree, '  ,  ')).toBe('');
    expect(warn).not.toHaveBeenCalled();
  });

  it('resolves a neighbourhood slug and ignores the English name', () => {
    expect(areaIdForCatalogDefault(tree, '  Southern-Stanley  ')).toBe(
      'stanley'
    );
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect(areaIdForCatalogDefault(tree, 'Stanley')).toBe('');
    expect(warn).toHaveBeenCalledTimes(1);
  });

  it('selects a district rather than one neighbourhood inside it', () => {
    expect(areaIdForCatalogDefault(tree, 'southern')).toBe('southern');
    expect(areaIdForCatalogDefault(tree, 'yau-tsim-mong')).toBe('ytm');
  });

  it('selects a region id, and islands matches the region before the district', () => {
    expect(areaIdForCatalogDefault(tree, 'hong_kong_island')).toBe('hki');
    expect(areaIdForCatalogDefault(tree, 'islands')).toBe('islands-region');
    expect(areaIdForCatalogDefault(tree, 'hong-kong-island')).toBe('');
  });

  it('keeps a district and a neighbourhood that share a name apart', () => {
    expect(areaIdForCatalogDefault(tree, 'wan-chai')).toBe('wan-chai-district');
    expect(areaIdForCatalogDefault(tree, 'wan-chai-wan-chai')).toBe('wan-chai');
    expect(areaIdForCatalogDefault(tree, 'wan-chai-jardine-s-lookout')).toBe(
      'jardine'
    );
  });

  it('uses the area that contains every other match', () => {
    expect(areaIdForCatalogDefault(tree, 'southern,southern-stanley')).toBe(
      'southern'
    );
    expect(
      areaIdForCatalogDefault(tree, 'hong_kong_island, southern-stanley')
    ).toBe('hki');
    expect(areaIdForCatalogDefault(tree, 'southern-stanley,southern-stanley')).toBe(
      'stanley'
    );
  });

  it('leaves the filter unset when the scope is two disjoint areas', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect(areaIdForCatalogDefault(tree, 'southern-stanley,southern-shek-o')).toBe(
      ''
    );
    expect(areaIdForCatalogDefault(tree, 'kowloon,islands')).toBe('');
    expect(warn).toHaveBeenCalled();
    expect(String(warn.mock.calls[0]?.[0])).toContain(
      'SEARCH_AREA_SCOPE "southern-stanley,southern-shek-o"'
    );
  });

  it('ignores an unknown slug when another token names one area', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect(areaIdForCatalogDefault(tree, 'southern-stanley,atlantis')).toBe(
      'stanley'
    );
    expect(String(warn.mock.calls[0]?.[0])).toContain('unknown slugs');
  });

  it('returns empty without warning when the tree has not loaded', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect(areaIdForCatalogDefault([], 'southern-stanley')).toBe('');
    expect(warn).not.toHaveBeenCalled();
  });

  it('warns in development when every slug is unknown', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect(areaIdForCatalogDefault(tree, 'atlantis')).toBe('');
    expect(warn).toHaveBeenCalledTimes(1);
  });

  it('stays quiet in production when the scope does not match', () => {
    vi.stubEnv('NODE_ENV', 'production');
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect(areaIdForCatalogDefault(tree, 'atlantis')).toBe('');
    expect(warn).not.toHaveBeenCalled();
  });
});

describe('areaNameInTree', () => {
  it('finds a nested area and returns empty when the id is missing', () => {
    expect(areaNameInTree(tree, 'stanley')).toBe('Stanley');
    expect(areaNameInTree(tree, 'southern')).toBe('Southern');
    expect(areaNameInTree(tree, '')).toBe('');
    expect(areaNameInTree(tree, 'missing')).toBe('');
  });
});
