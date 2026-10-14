import { describe, expect, it } from 'vitest';

import { ADMIN_TABLE_EMPTY } from '@/components/ui/admin-table-value';
import {
  capturedCategoryLabel,
  formatCapturedCategories,
  formatImportJobMode,
  formatImportJobSource,
  formatImportResultHeader,
  formatImportResultNotes,
  formatImportStatusCounts,
  groupImportResults,
  importResultWorkspaceHref,
  previewImportRows,
  stripImportResultPathPrefix,
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

describe('formatImportJobSource', () => {
  it('names the admin Imports page and the board catalog API', () => {
    expect(formatImportJobSource('ui')).toBe('UI import');
    expect(formatImportJobSource('board')).toBe('Board API');
  });

  it('uses an em dash when the job predates source', () => {
    expect(formatImportJobSource(null)).toBe(ADMIN_TABLE_EMPTY);
    expect(formatImportJobSource(undefined)).toBe(ADMIN_TABLE_EMPTY);
    expect(formatImportJobSource('')).toBe(ADMIN_TABLE_EMPTY);
  });
});

describe('formatImportJobMode', () => {
  it('keeps dry run and completed live labels', () => {
    expect(formatImportJobMode({ dry_run: true, status: 'completed' })).toBe(
      'Dry run'
    );
    expect(formatImportJobMode({ dry_run: false, status: 'completed' })).toBe(
      'Live execution'
    );
    expect(
      formatImportJobMode({
        dry_run: false,
        status: 'completed',
        allow_updates: false,
      })
    ).toBe('Live execution · skip existing');
  });

  it('capitalizes live statuses that are not completed', () => {
    expect(formatImportJobMode({ dry_run: false, status: 'failed' })).toBe(
      'Failed'
    );
    expect(formatImportJobMode({ dry_run: false, status: 'running' })).toBe(
      'Running'
    );
    expect(
      formatImportJobMode({
        dry_run: false,
        status: 'FAILED',
        allow_updates: false,
      })
    ).toBe('Failed · skip existing');
  });
});

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

describe('stripImportResultPathPrefix', () => {
  it('drops a leading organizations[n]: prefix', () => {
    expect(
      stripImportResultPathPrefix(
        'organizations[0]: ignored flat location fields area_name, address because locations[] is present'
      )
    ).toBe(
      'ignored flat location fields area_name, address because locations[] is present'
    );
  });

  it('drops a nested type path prefix', () => {
    expect(
      stripImportResultPathPrefix(
        'organizations[1]/activities[0]: ignored flat activity fields category_name'
      )
    ).toBe('ignored flat activity fields category_name');
  });

  it('leaves notes that have no path prefix', () => {
    expect(stripImportResultPathPrefix('neighbourhood missing')).toBe(
      'neighbourhood missing'
    );
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

  it('strips JSON index prefixes from each warning and error', () => {
    expect(
      formatImportResultNotes({
        errors: [{ message: 'organizations[0]: name is required' }],
        warnings: [
          'organizations[0]: ignored flat location fields area_name, address because locations[] is present',
          'organizations[0]: ignored flat activity fields category_name because activities[] is present',
        ],
      })
    ).toBe(
      'name is required · ignored flat location fields area_name, address because locations[] is present; ignored flat activity fields category_name because activities[] is present'
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

describe('importResultWorkspaceHref', () => {
  const results = [
    row({
      type: 'organizations',
      key: 'Harbor Arts',
      status: 'created',
      id: 'org-1',
      path: 'organizations[0]',
    }),
    row({
      type: 'locations',
      key: 'Harbor Arts / Main studio',
      status: 'created',
      id: 'loc-1',
      path: 'organizations[0].locations[0]',
    }),
    row({
      type: 'activities',
      key: 'Harbor Arts / Clay club',
      status: 'created',
      id: 'activity-1',
      path: 'organizations[0].activities[0]',
    }),
    row({
      type: 'pricing',
      key: 'Clay club / Main studio / per_class',
      status: 'created',
      id: 'pricing-1',
      path: 'organizations[0].activities[0].pricing[0]',
    }),
    row({
      type: 'schedules',
      key: 'Clay club / Main studio',
      status: 'updated',
      id: 'schedule-1',
      path: 'organizations[0].activities[0].schedules[0]',
    }),
  ];

  it('links each stored id to its workspace section', () => {
    expect(importResultWorkspaceHref(results[0]!, results)).toBe(
      '/admin/dashboard?section=organizations&org=org-1'
    );
    expect(importResultWorkspaceHref(results[1]!, results)).toBe(
      '/admin/dashboard?section=locations&org=org-1&location=loc-1'
    );
    expect(importResultWorkspaceHref(results[2]!, results)).toBe(
      '/admin/dashboard?section=activities&org=org-1&activity=activity-1'
    );
    expect(importResultWorkspaceHref(results[3]!, results)).toBe(
      '/admin/dashboard?section=pricing&org=org-1&pricing=pricing-1'
    );
    expect(importResultWorkspaceHref(results[4]!, results)).toBe(
      '/admin/dashboard?section=schedules&org=org-1&schedule=schedule-1'
    );
  });

  it('resolves the parent organization from a key prefix when path is missing', () => {
    const location = row({
      type: 'locations',
      key: 'Harbor Arts / Main studio',
      status: 'created',
      id: 'loc-1',
    });
    expect(importResultWorkspaceHref(location, results)).toBe(
      '/admin/dashboard?section=locations&org=org-1&location=loc-1'
    );
  });

  it('skips dry-run ids and rows without an id', () => {
    expect(
      importResultWorkspaceHref(results[0]!, results, { dryRun: true })
    ).toBeNull();
    expect(
      importResultWorkspaceHref(
        row({ type: 'organizations', key: 'Missing Org', status: 'failed' }),
        results
      )
    ).toBeNull();
    expect(
      importResultWorkspaceHref(
        row({
          type: 'locations',
          key: 'Other Studio / Hall',
          status: 'created',
          id: 'loc-2',
          path: 'organizations[1].locations[0]',
        }),
        results
      )
    ).toBeNull();
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
