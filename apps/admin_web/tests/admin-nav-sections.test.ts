import { describe, expect, it } from 'vitest';

import { buildAdminNavSections } from '@/lib/admin-nav-sections';

describe('buildAdminNavSections', () => {
  it('keeps an unsorted group in declaration order', () => {
    const sections = buildAdminNavSections([
      {
        sections: [
          { key: 'organizations', label: 'Organization' },
          { key: 'media', label: 'Media' },
        ],
      },
    ]);

    expect(sections.map((section) => section.label)).toEqual([
      'Organization',
      'Media',
    ]);
    expect(sections[0]?.dividerBefore).toBe(false);
  });

  it('sorts a group A-Z when asked', () => {
    const sections = buildAdminNavSections([
      {
        sort: true,
        sections: [
          { key: 'users', label: 'Users' },
          { key: 'api-keys', label: 'API Keys' },
        ],
      },
    ]);

    expect(sections.map((section) => section.label)).toEqual([
      'API Keys',
      'Users',
    ]);
  });

  it('draws a rule only before the first item of a marked group', () => {
    const sections = buildAdminNavSections([
      { sections: [{ key: 'catalog', label: 'Catalog' }] },
      {
        dividerBefore: true,
        sections: [
          { key: 'organizations', label: 'Organization' },
          { key: 'schedules', label: 'Schedules' },
        ],
      },
      {
        dividerBefore: true,
        sort: true,
        sections: [
          { key: 'tickets', label: 'Tickets' },
          { key: 'imports', label: 'Imports' },
        ],
      },
    ]);

    expect(sections.map((section) => section.key)).toEqual([
      'catalog',
      'organizations',
      'schedules',
      'imports',
      'tickets',
    ]);
    expect(sections.map((section) => section.dividerBefore)).toEqual([
      false,
      true,
      false,
      true,
      false,
    ]);
  });
});
