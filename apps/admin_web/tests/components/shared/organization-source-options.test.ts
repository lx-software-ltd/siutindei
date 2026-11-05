import { describe, expect, it } from 'vitest';

import {
  ORG_SOURCE_OPTIONS,
  orgSourceLabel,
} from '@/components/shared/organizations/organization-form-utils';

describe('ORG_SOURCE_OPTIONS', () => {
  it('includes Manual with the catalog source value', () => {
    expect(ORG_SOURCE_OPTIONS).toContainEqual({
      value: 'manual',
      label: 'Manual',
    });
  });

  it('includes Recommendation with the catalog source value', () => {
    expect(ORG_SOURCE_OPTIONS).toContainEqual({
      value: 'recommendation',
      label: 'Recommendation',
    });
  });

  it('keeps the existing catalog sources after Manual', () => {
    expect(ORG_SOURCE_OPTIONS.map((option) => option.value)).toEqual([
      'manual',
      'lcsd',
      'edb',
      'swd',
      'places',
      'competitor',
      'recommendation',
    ]);
  });
});

describe('orgSourceLabel', () => {
  it('labels unset and manual sources as Manual', () => {
    expect(orgSourceLabel(null)).toBe('Manual');
    expect(orgSourceLabel('')).toBe('Manual');
    expect(orgSourceLabel('manual')).toBe('Manual');
  });

  it('leaves other catalog tokens unchanged', () => {
    expect(orgSourceLabel('lcsd')).toBe('lcsd');
    expect(orgSourceLabel('recommendation')).toBe('recommendation');
  });
});
