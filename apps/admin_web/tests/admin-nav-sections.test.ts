import { describe, expect, it } from 'vitest';

import { buildAdminNavSections } from '@/lib/admin-nav-sections';

const primary = [
  { key: 'organizations', label: 'Organizations' },
  { key: 'media', label: 'Media' },
];

describe('buildAdminNavSections', () => {
  it('keeps the primary group in declaration order', () => {
    const sections = buildAdminNavSections(primary, [
      { key: 'tickets', label: 'Tickets' },
    ]);

    expect(sections.slice(0, 2).map((section) => section.label)).toEqual([
      'Organizations',
      'Media',
    ]);
  });

  it('sorts the second group A-Z even when declared out of order', () => {
    const sections = buildAdminNavSections(primary, [
      { key: 'tickets', label: 'Tickets' },
      { key: 'api-keys', label: 'API Keys' },
      { key: 'feedback', label: 'Feedback' },
    ]);

    expect(sections.map((section) => section.label)).toEqual([
      'Organizations',
      'Media',
      'API Keys',
      'Feedback',
      'Tickets',
    ]);
  });

  it('places a future second-group page on the A-Z path', () => {
    const sections = buildAdminNavSections(primary, [
      { key: 'tickets', label: 'Tickets' },
      { key: 'feedback', label: 'Feedback' },
      { key: 'reports', label: 'Reports' },
      { key: 'imports', label: 'Imports' },
    ]);

    expect(sections.map((section) => section.label)).toEqual([
      'Organizations',
      'Media',
      'Feedback',
      'Imports',
      'Reports',
      'Tickets',
    ]);
  });

  it('puts the divider on the first sorted tool page', () => {
    const sections = buildAdminNavSections(primary, [
      { key: 'users', label: 'Users', dividerBefore: true },
      { key: 'api-keys', label: 'API Keys' },
    ]);

    expect(sections.find((section) => section.dividerBefore)?.key).toBe(
      'api-keys'
    );
    expect(
      sections.filter((section) => section.dividerBefore)
    ).toHaveLength(1);
  });
});
