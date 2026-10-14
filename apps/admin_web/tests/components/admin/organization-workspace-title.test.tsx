import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { OrganizationStatusBadges } from '@/components/admin/organization-workspace-title';
import type { Organization } from '@/types/admin';

const organization = {
  id: 'org-1',
  name: 'Harbour Club',
  status: 'operational',
  review_status: 'pending_review',
  version: 2,
} as Organization;

describe('OrganizationStatusBadges', () => {
  it('labels the workspace roll-up as Organization Version N', () => {
    render(<OrganizationStatusBadges organization={organization} />);

    expect(screen.getByText('Organization Version 2')).toBeVisible();
    expect(screen.queryByText('Org v2')).not.toBeInTheDocument();
  });

  it('hides the version tag when a switcher owns the version', () => {
    render(
      <OrganizationStatusBadges organization={organization} version='hidden' />
    );

    expect(screen.queryByText('Organization Version 2')).not.toBeInTheDocument();
  });
});
