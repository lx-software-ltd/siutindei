import { describe, expect, it } from 'vitest';

import { AUDITABLE_TABLES } from '@/lib/audit-tables';

const EXPECTED = [
  'activities',
  'activity_categories',
  'activity_locations',
  'activity_pricing',
  'activity_schedule',
  'api_keys',
  'category_suggestion_settings',
  'category_suggestions',
  'feedback_labels',
  'import_settings',
  'locations',
  'organization_duplicate_dismissals',
  'organization_feedback',
  'organization_merges',
  'organizations',
  'tickets',
] as const;

describe('AUDITABLE_TABLES', () => {
  it('lists every audited table in A–Z order', () => {
    expect(AUDITABLE_TABLES).toEqual(EXPECTED);
    expect([...AUDITABLE_TABLES]).toEqual(
      [...AUDITABLE_TABLES].sort((left, right) => left.localeCompare(right))
    );
  });
});
