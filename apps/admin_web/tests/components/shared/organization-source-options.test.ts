import { describe, expect, it } from 'vitest';

import { ORG_SOURCE_OPTIONS } from '@/components/shared/organizations/organization-form-utils';

describe('ORG_SOURCE_OPTIONS', () => {
  it('includes Recommendation with the catalog source value', () => {
    expect(ORG_SOURCE_OPTIONS).toContainEqual({
      value: 'recommendation',
      label: 'Recommendation',
    });
  });

  it('keeps the existing catalog sources', () => {
    expect(ORG_SOURCE_OPTIONS.map((option) => option.value)).toEqual([
      'lcsd',
      'edb',
      'swd',
      'places',
      'competitor',
      'recommendation',
    ]);
  });
});
