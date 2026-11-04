import { describe, expect, it } from 'vitest';

import {
  DEFAULT_CATALOG_NEIGHBOURHOOD_NAME,
  areaIdForCatalogDefault,
} from '@/lib/catalog-defaults';

describe('catalog defaults', () => {
  it('defaults Catalog to Stanley', () => {
    expect(DEFAULT_CATALOG_NEIGHBOURHOOD_NAME).toBe('Stanley');
  });

  it('resolves the default neighbourhood id from filter options', () => {
    expect(
      areaIdForCatalogDefault([
        { id: 'area-cb', name: 'Causeway Bay', group: 'Wan Chai' },
        { id: 'area-stanley', name: 'Stanley', group: 'Southern' },
      ])
    ).toBe('area-stanley');
  });

  it('returns empty when the default neighbourhood is missing', () => {
    expect(
      areaIdForCatalogDefault([
        { id: 'area-cb', name: 'Causeway Bay', group: 'Wan Chai' },
      ])
    ).toBe('');
  });
});
