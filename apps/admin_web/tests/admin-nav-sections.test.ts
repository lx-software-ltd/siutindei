import { describe, expect, it } from 'vitest';

import { buildAdminNavSections } from '@/lib/admin-nav-sections';

describe('buildAdminNavSections', () => {
  it('keeps an unsorted group in declaration order', () => {
    const sections = buildAdminNavSections([
      {
        label: 'Workspace',
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
    expect(sections[0]?.group).toBe('Workspace');
  });

  it('sorts a group A-Z when asked', () => {
    const sections = buildAdminNavSections([
      {
        label: 'Access',
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

  it('keeps group order and leaves an unlabeled item without a heading', () => {
    const sections = buildAdminNavSections([
      { sections: [{ key: 'catalog', label: 'Catalog' }] },
      {
        label: 'Intake',
        sort: true,
        sections: [
          { key: 'tickets', label: 'Tickets' },
          { key: 'imports', label: 'Imports' },
        ],
      },
    ]);

    expect(sections.map((section) => section.key)).toEqual([
      'catalog',
      'imports',
      'tickets',
    ]);
    expect(sections[0]?.group).toBeUndefined();
    expect(sections[1]?.group).toBe('Intake');
  });
});
