import { ADMIN_TABLE_EMPTY } from '@/components/ui/admin-table-value';

import type { AdminImportResult, AdminImportStatus } from './api-client-imports';

export const IMPORT_RESULT_TYPES = [
  { type: 'organizations', label: 'Organization' },
  { type: 'locations', label: 'Location' },
  { type: 'activities', label: 'Activity' },
  { type: 'pricing', label: 'Pricing' },
  { type: 'schedules', label: 'Schedule' },
] as const;

export const IMPORT_RESULT_STATUSES = [
  'created',
  'updated',
  'unchanged',
  'failed',
  'skipped',
] as const satisfies readonly AdminImportStatus[];

export type ImportResultGroup = {
  readonly type: (typeof IMPORT_RESULT_TYPES)[number]['type'];
  readonly label: string;
  readonly counts: string;
  readonly rows: readonly AdminImportResult[];
};

const IMPORT_JOB_SOURCE_LABELS: Record<string, string> = {
  ui: 'UI import',
  board: 'Board API',
};

/** History Source column. Missing source is an em dash. */
export function formatImportJobSource(source?: string | null): string {
  const value = source?.trim() ?? '';
  if (!value) {
    return ADMIN_TABLE_EMPTY;
  }
  return IMPORT_JOB_SOURCE_LABELS[value] ?? value;
}

export function countImportStatuses(
  rows: readonly Pick<AdminImportResult, 'status'>[]
): Partial<Record<AdminImportStatus, number>> {
  const counts: Partial<Record<AdminImportStatus, number>> = {};
  for (const row of rows) {
    const status = row.status;
    counts[status] = (counts[status] ?? 0) + 1;
  }
  return counts;
}

export function formatImportStatusCounts(
  rows: readonly Pick<AdminImportResult, 'status'>[]
): string {
  const counts = countImportStatuses(rows);
  return IMPORT_RESULT_STATUSES.filter((status) => (counts[status] ?? 0) > 0)
    .map((status) => `${status} ${counts[status]}`)
    .join(' · ');
}

export function groupImportResults(
  results: readonly AdminImportResult[]
): ImportResultGroup[] {
  return IMPORT_RESULT_TYPES.flatMap((entry) => {
    const rows = results.filter((row) => row.type === entry.type);
    if (rows.length === 0) {
      return [];
    }
    return [
      {
        type: entry.type,
        label: entry.label,
        counts: formatImportStatusCounts(rows),
        rows,
      },
    ];
  });
}

const IMPORT_RESULT_PATH_PREFIX =
  /^(?:organizations|locations|activities|pricing|schedules)\[\d+\](?:\/(?:organizations|locations|activities|pricing|schedules)\[\d+\])*:\s*/i;

export function stripImportResultPathPrefix(text: string): string {
  return text.replace(IMPORT_RESULT_PATH_PREFIX, '');
}

export function formatImportResultNotes(
  row: Pick<AdminImportResult, 'errors' | 'warnings'>
): string {
  const errors = (row.errors ?? [])
    .map((error) => stripImportResultPathPrefix(error.message ?? ''))
    .filter(Boolean)
    .join('; ');
  const warnings = (row.warnings ?? [])
    .map((warning) => stripImportResultPathPrefix(warning))
    .filter(Boolean)
    .join('; ');
  return [errors, warnings].filter(Boolean).join(' · ');
}

const RESULT_STATUS_RANK: Record<string, number> = {
  failed: 0,
  skipped: 1,
  created: 2,
  updated: 3,
  unchanged: 4,
};

export const IMPORT_RESULT_PREVIEW = 20;

export function previewImportRows<T extends { status: string }>(
  rows: readonly T[],
  showAll: boolean,
  limit = IMPORT_RESULT_PREVIEW
): { rows: T[]; hidden: number } {
  const ordered = rows
    .map((row, index) => ({ row, index }))
    .sort((left, right) => {
      const rank =
        (RESULT_STATUS_RANK[left.row.status] ?? 9) -
        (RESULT_STATUS_RANK[right.row.status] ?? 9);
      return rank || left.index - right.index;
    })
    .map((entry) => entry.row);
  if (showAll || ordered.length <= limit) {
    return { rows: ordered, hidden: 0 };
  }
  return {
    rows: ordered.slice(0, limit),
    hidden: ordered.length - limit,
  };
}

export type CapturedCategoryName = {
  readonly requested_name?: string | null;
  readonly suggested_name?: string | null;
  readonly status?: string | null;
  readonly created_category_id?: string | null;
};

export function capturedCategoryLabel(suggestion: CapturedCategoryName): string {
  const requested = suggestion.requested_name?.trim() ?? '';
  const suggested = suggestion.suggested_name?.trim() ?? '';
  const settled =
    Boolean(suggestion.created_category_id) ||
    suggestion.status === 'approved' ||
    suggestion.status === 'merged';
  if (settled && suggested && requested && suggested !== requested) {
    return `${suggested} · captured as ${requested}`;
  }
  if (settled && suggested) {
    return suggested;
  }
  return requested || suggested;
}

export function formatCapturedCategories(
  count: number | undefined,
  names: readonly string[] = [],
  unavailable = 0
): string {
  if (!count) {
    return ADMIN_TABLE_EMPTY;
  }
  const unique = [...new Set(names.map((name) => name.trim()).filter(Boolean))];
  const missing =
    unavailable > 0
      ? `${unavailable} name${unavailable === 1 ? '' : 's'} unavailable`
      : '';
  if (unique.length === 0) {
    return missing ? `${count} · ${missing}` : String(count);
  }
  const listed = `${count} · ${unique.join(', ')}`;
  return missing ? `${listed} · ${missing}` : listed;
}

export function formatImportResultHeader(
  resultCount: number,
  warnings = 0,
  errors = 0
): string {
  const bits = [`${resultCount} row${resultCount === 1 ? '' : 's'}`];
  if (warnings > 0) {
    bits.push(`${warnings} warning${warnings === 1 ? '' : 's'}`);
  }
  if (errors > 0) {
    bits.push(`${errors} error${errors === 1 ? '' : 's'}`);
  }
  return bits.join(' · ');
}
