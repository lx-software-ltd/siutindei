import { describe, expect, it } from 'vitest';

import { patchForSectionChange, staleRecordParams } from '@/lib/admin-section-params';

describe('admin section params', () => {
  it('drops record params that belong to other sections', () => {
    const patch = patchForSectionChange('locations');
    expect(patch.section).toBe('locations');
    expect(patch.organization).toBeNull();
    expect(patch.edit).toBeNull();
    expect(patch.ticket).toBeNull();
    expect(patch).not.toHaveProperty('location');
  });

  it('keeps a legacy edit link for the section that still reads it', () => {
    expect(
      staleRecordParams('locations', { edit: 'loc-1', organization: 'org-1' })
    ).toEqual({ organization: null });
  });

  it('clears a legacy edit link once the section has its own param', () => {
    expect(staleRecordParams('locations', { edit: 'old', location: 'loc-1' })).toEqual({
      edit: null,
    });
  });

  it('clears every record param on a section that has none', () => {
    expect(staleRecordParams('media', { organization: 'org-1', edit: 'org-1' })).toEqual({
      organization: null,
      edit: null,
    });
  });

  it('keeps a preserved org on sections outside the workspace', () => {
    const suggest = patchForSectionChange('suggest-place', ['org']);
    expect(suggest.section).toBe('suggest-place');
    expect(suggest).not.toHaveProperty('org');
    expect(suggest.location).toBeNull();

    const feedback = patchForSectionChange('feedback', ['org']);
    expect(feedback).not.toHaveProperty('org');
    expect(feedback).not.toHaveProperty('feedback');
    expect(
      staleRecordParams(
        'suggest-place',
        { org: 'org-1', location: 'loc-1' },
        ['org']
      )
    ).toEqual({ location: null });
    expect(
      staleRecordParams('feedback', { org: 'org-1', ticket: 't-1' }, ['org'])
    ).toEqual({ ticket: null });
  });

  it('drops org on admin feedback when nothing is preserved', () => {
    expect(patchForSectionChange('feedback').org).toBeNull();
    expect(staleRecordParams('feedback', { org: 'org-1' })).toEqual({
      org: null,
    });
  });

  it('keeps feedback entry and label links on the feedback page', () => {
    expect(
      staleRecordParams('feedback', {
        feedback: 'fb-1',
        'feedback-label': 'lbl-1',
        ticket: 't-1',
      })
    ).toEqual({ ticket: null });
    expect(
      staleRecordParams('feedback-labels', {
        feedback: 'fb-1',
        'feedback-label': 'lbl-1',
        ticket: 't-1',
      })
    ).toEqual({ ticket: null });

    const patch = patchForSectionChange('feedback');
    expect(patch.section).toBe('feedback');
    expect(patch).not.toHaveProperty('feedback');
    expect(patch).not.toHaveProperty('feedback-label');
    expect(patch.ticket).toBeNull();
  });

  it('keeps the organization scope across workspace sections', () => {
    const patch = patchForSectionChange('locations');
    expect(patch).not.toHaveProperty('org');
    expect(patch.organization).toBeNull();
    expect(
      staleRecordParams('media', { org: 'org-1', ticket: 't-1' })
    ).toEqual({ ticket: null });
    expect(staleRecordParams('imports', { org: 'org-1', job: 'job-1' })).toEqual({
      org: null,
    });
  });

  it('keeps duplicate and name-fix links on data quality', () => {
    expect(
      staleRecordParams('data-quality', {
        duplicate: 'org-a,org-b',
        'name-fix': 'fix-1',
        'location-fix': 'loc-1',
        'translation-fix': 'tr-1',
        organization: 'org-1',
      })
    ).toEqual({});
    const patch = patchForSectionChange('data-quality');
    expect(patch.section).toBe('data-quality');
    expect(patch).not.toHaveProperty('duplicate');
    expect(patch).not.toHaveProperty('name-fix');
    expect(patch).not.toHaveProperty('location-fix');
    expect(patch).not.toHaveProperty('translation-fix');
    expect(patch).not.toHaveProperty('organization');
    expect(patch).not.toHaveProperty('category-check');
  });

  it('keeps an open category check on data quality', () => {
    expect(
      staleRecordParams('data-quality', {
        'category-check': 'rev-1',
        suggestion: 'sug-1',
      })
    ).toEqual({ suggestion: null });
  });
});
