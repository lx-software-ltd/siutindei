import { describe, expect, it } from 'vitest';

import {
  catalogSourcePayload,
  emptyForm,
  itemToForm,
  ORG_SOURCE_OPTIONS,
  orgSourceLabel,
} from '@/components/shared/organizations/organization-form-utils';
import type { Organization } from '@/types/admin';

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

  it('uses the editor labels for other catalog sources', () => {
    expect(orgSourceLabel('lcsd')).toBe('LCSD');
    expect(orgSourceLabel('recommendation')).toBe('Recommendation');
  });
});

describe('catalog source form values', () => {
  it('defaults a new organization to Manual', () => {
    expect(emptyForm.source).toBe('manual');
    expect(catalogSourcePayload(emptyForm.source)).toBe('manual');
  });

  it('keeps an unset stored source unset until the editor chooses one', () => {
    const form = itemToForm({ name: 'Unset Hall' } as Organization);
    expect(form.source).toBe('');
    expect(catalogSourcePayload(form.source)).toBeNull();
  });

  it('sends Manual when the editor chooses it', () => {
    expect(catalogSourcePayload('manual')).toBe('manual');
  });
});
