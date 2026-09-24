/** Record ids mirrored in the dashboard URL. `edit` is the legacy alias. */
export const ADMIN_RECORD_PARAMS = [
  'edit',
  'organization',
  'location',
  'activity',
  'pricing',
  'schedule',
  'category',
  'feedback',
  'feedback-label',
  'api-key',
  'suggestion',
  'ticket',
  'user',
  'audit-log',
  'review',
  'job',
  'import-job',
] as const;

export type AdminRecordParam = (typeof ADMIN_RECORD_PARAMS)[number];

const KEEP_BY_SECTION: Record<string, readonly AdminRecordParam[]> = {
  organizations: ['organization'],
  locations: ['location'],
  activities: ['activity'],
  pricing: ['pricing'],
  schedules: ['schedule'],
  tickets: ['ticket'],
  feedback: ['feedback'],
  'feedback-labels': ['feedback-label'],
  'cognito-users': ['user'],
  'activity-categories': ['category'],
  'category-suggestions': ['suggestion'],
  'api-keys': ['api-key'],
  'audit-logs': ['audit-log'],
  imports: ['review', 'job', 'import-job'],
};

const LEGACY_EDIT_SECTIONS = new Set([
  'organizations',
  'locations',
  'activities',
  'pricing',
  'schedules',
]);

/**
 * Query update for a sidebar click: open `nextSection` and drop record params
 * that belong to other sections, including a stale `edit` link.
 */
export function patchForSectionChange(
  nextSection: string
): Record<string, string | null> {
  const keep = new Set<string>(KEEP_BY_SECTION[nextSection] ?? []);
  const patch: Record<string, string | null> = { section: nextSection };
  for (const key of ADMIN_RECORD_PARAMS) {
    if (!keep.has(key)) {
      patch[key] = null;
    }
  }
  return patch;
}

/**
 * Params currently in the URL that the active section does not read.
 * A legacy `edit` value is kept when that section still honors it and its
 * own record param is empty.
 */
export function staleRecordParams(
  section: string,
  current: Partial<Record<AdminRecordParam, string | null>>
): Partial<Record<AdminRecordParam, null>> {
  const own = KEEP_BY_SECTION[section]?.[0];
  const editHoldsLink =
    LEGACY_EDIT_SECTIONS.has(section) && Boolean(current.edit) && (!own || !current[own]);
  const keep = new Set<string>(KEEP_BY_SECTION[section] ?? []);
  if (editHoldsLink) {
    keep.add('edit');
  }
  const patch: Partial<Record<AdminRecordParam, null>> = {};
  for (const key of ADMIN_RECORD_PARAMS) {
    if (keep.has(key) || !current[key]) {
      continue;
    }
    patch[key] = null;
  }
  return patch;
}
