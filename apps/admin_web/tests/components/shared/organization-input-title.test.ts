import { describe, expect, it } from 'vitest';

import { organizationInputTitle } from '@/components/shared/organizations-panel';

describe('organizationInputTitle', () => {
  it('uses the trimmed name when the organization has one', () => {
    expect(organizationInputTitle('  Harbour Club  ', 'edit')).toBe('Harbour Club');
  });

  it('titles a draft New organization', () => {
    expect(organizationInputTitle('', 'create')).toBe('New organization');
    expect(organizationInputTitle(null, 'create')).toBe('New organization');
  });

  it('titles a nameless existing organization Organization', () => {
    expect(organizationInputTitle('   ', 'edit')).toBe('Organization');
    expect(organizationInputTitle(undefined, 'edit')).toBe('Organization');
  });
});
