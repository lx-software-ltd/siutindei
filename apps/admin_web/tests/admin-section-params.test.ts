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

  it('keeps duplicate and name-fix links on data quality', () => {
    expect(
      staleRecordParams('data-quality', {
        duplicate: 'org-a,org-b',
        'name-fix': 'fix-1',
        organization: 'org-1',
      })
    ).toEqual({});
    const patch = patchForSectionChange('data-quality');
    expect(patch.section).toBe('data-quality');
    expect(patch).not.toHaveProperty('duplicate');
    expect(patch).not.toHaveProperty('name-fix');
    expect(patch).not.toHaveProperty('organization');
  });
});
