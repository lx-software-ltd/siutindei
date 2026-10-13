import { describe, expect, it } from 'vitest';

import { formatAdminPageName } from '@/lib/admin-page-name';

describe('formatAdminPageName', () => {
  it('uses the nav label when there is no tab', () => {
    expect(formatAdminPageName('Catalog')).toBe('Catalog');
    expect(formatAdminPageName('Locations')).toBe('Locations');
    expect(formatAdminPageName('Audit logs')).toBe('Audit logs');
    expect(formatAdminPageName('Catalog', '')).toBe('Catalog');
    expect(formatAdminPageName('Catalog', '  ')).toBe('Catalog');
  });

  it('uses the nav label when the tab repeats the nav', () => {
    expect(formatAdminPageName('Imports', 'Import')).toBe('Imports');
    expect(formatAdminPageName('Categories', 'Categories')).toBe('Categories');
    expect(formatAdminPageName('Feedback', 'Feedback')).toBe('Feedback');
    expect(formatAdminPageName('Categories', 'Category')).toBe('Categories');
    expect(formatAdminPageName('Activities', 'Activity')).toBe('Activities');
  });

  it('joins nav and tab with an interpunct when the tab distinguishes the view', () => {
    expect(formatAdminPageName('Imports', 'History')).toBe('Imports · History');
    expect(formatAdminPageName('Categories', 'Suggestions')).toBe(
      'Categories · Suggestions'
    );
    expect(formatAdminPageName('Feedback', 'Labels')).toBe('Feedback · Labels');
    expect(formatAdminPageName('Data quality', 'Duplicates')).toBe(
      'Data quality · Duplicates'
    );
    expect(formatAdminPageName('Data quality', 'Names')).toBe(
      'Data quality · Names'
    );
    expect(formatAdminPageName('Data quality', 'Locations')).toBe(
      'Data quality · Locations'
    );
    expect(formatAdminPageName('Data quality', 'Categories')).toBe(
      'Data quality · Categories'
    );
    expect(formatAdminPageName('Data quality', 'Deleted')).toBe(
      'Data quality · Deleted'
    );
  });
});
