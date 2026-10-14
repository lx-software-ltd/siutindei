import { describe, expect, it } from 'vitest';

import { ADMIN_TABLE_EMPTY } from '@/components/ui/admin-table-value';
import {
  capturedCategoryLabel,
  formatCapturedCategories,
  formatImportResultHeader,
  formatImportResultNotes,
  formatImportStatusCounts,
  groupImportResults,
  importResultPath,
  previewImportRows,
} from '@/lib/import-job-results';
import type { AdminImportResult } from '@/lib/api-client-imports';

function row(
  partial: Partial<AdminImportResult> &
    Pick<AdminImportResult, 'type' | 'key' | 'status'>
): AdminImportResult {
  return {
    warnings: [],
    errors: [],
    ...partial,
  };
}

describe('formatImportStatusCounts', () => {
  it('lists only statuses that occurred, in status order', () => {
    expect(
      formatImportStatusCounts([
        { status: 'failed' },
        { status: 'created' },
        { status: 'created' },
        { status: 'unchanged' },
      ])
    ).toBe('created 2 · unchanged 1 · failed 1');
  });
});

describe('groupImportResults', () => {
  it('groups by type and omits empty types', () => {
    const groups = groupImportResults([
      row({
        type: 'activities',
        key: 'Harbor Arts / Clay club',
        status: 'created',
      }),
      row({ type: 'organizations', key: 'Harbor Arts', status: 'updated' }),
      row({
        type: 'organizations',
        key: 'Missing Org',
        status: 'failed',
        errors: [{ message: 'name is required' }],
      }),
    ]);
    expect(groups.map((group) => group.label)).toEqual([
      'Organization',
      'Activity',
    ]);
    expect(groups[0]?.counts).toBe('updated 1 · failed 1');
    expect(groups[1]?.rows).toHaveLength(1);
  });
});

describe('formatImportResultNotes', () => {
  it('joins errors and warnings without the file path', () => {
    expect(
      formatImportResultNotes({
        errors: [{ message: 'name is required' }],
        warnings: ['neighbourhood missing'],
      })
    ).toBe('name is required · neighbourhood missing');
  });
});

describe('importResultPath', () => {
  it('keeps a path that differs from the name', () => {
    expect(
      importResultPath({ key: 'Harbor Arts', path: 'organizations[0]' })
    ).toBe('organizations[0]');
  });

  it('omits a path that repeats the name', () => {
    expect(importResultPath({ key: 'Harbor Arts', path: 'Harbor Arts' })).toBe(
      ''
    );
  });
});

describe('previewImportRows', () => {
  it('shows failed rows first and hides the rest past the preview', () => {
    const rows = [
      { status: 'created', key: 'a' },
      { status: 'failed', key: 'b' },
      { status: 'updated', key: 'c' },
    ];
    expect(previewImportRows(rows, false, 2)).toEqual({
      rows: [
        { status: 'failed', key: 'b' },
        { status: 'created', key: 'a' },
      ],
      hidden: 1,
    });
    expect(previewImportRows(rows, true, 2).hidden).toBe(0);
  });
});

describe('capturedCategoryLabel', () => {
  it('keeps the imported name while the suggestion is still pending', () => {
    expect(
      capturedCategoryLabel({
        requested_name: 'Pottery',
        suggested_name: 'Ceramics',
        status: 'pending',
      })
    ).toBe('Pottery');
  });

  it('shows the settled name and the name that was captured', () => {
    expect(
      capturedCategoryLabel({
        requested_name: 'Pottery',
        suggested_name: 'Ceramics',
        status: 'approved',
        created_category_id: 'cat-1',
      })
    ).toBe('Ceramics · captured as Pottery');
  });
});

describe('formatCapturedCategories', () => {
  it('uses a dash when none were captured', () => {
    expect(formatCapturedCategories(undefined)).toBe(ADMIN_TABLE_EMPTY);
    expect(formatCapturedCategories(0)).toBe(ADMIN_TABLE_EMPTY);
  });

  it('shows the count when names are missing', () => {
    expect(formatCapturedCategories(2)).toBe('2');
  });

  it('appends unique names when they resolve', () => {
    expect(formatCapturedCategories(2, ['Pottery', 'Pottery', ' Sensory '])).toBe(
      '2 · Pottery, Sensory'
    );
  });

  it('says when some names could not be loaded', () => {
    expect(formatCapturedCategories(2, ['Pottery'], 1)).toBe(
      '2 · Pottery · 1 name unavailable'
    );
    expect(formatCapturedCategories(2, [], 2)).toBe('2 · 2 names unavailable');
  });
});

describe('formatImportResultHeader', () => {
  it('pluralizes rows and appends warning and error totals', () => {
    expect(formatImportResultHeader(1)).toBe('1 row');
    expect(formatImportResultHeader(3, 1, 2)).toBe(
      '3 rows · 1 warning · 2 errors'
    );
  });
});
