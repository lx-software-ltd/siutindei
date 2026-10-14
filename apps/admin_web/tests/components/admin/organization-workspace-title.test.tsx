import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { OrganizationStatusBadges } from '@/components/admin/organization-workspace-title';
import type { Organization } from '@/types/admin';

function organizationFixture(
  overrides: Partial<Organization> = {}
): Organization {
  return {
    id: 'org-1',
    name: 'Harbour Club',
    status: 'operational',
    review_status: 'pending_review',
    version: 2,
    ...overrides,
  } as Organization;
}

describe('OrganizationStatusBadges', () => {
  it('labels the workspace roll-up as Organization Version N', () => {
    render(<OrganizationStatusBadges organization={organizationFixture()} />);

    expect(screen.getByText('Organization Version 2')).toBeVisible();
    expect(screen.queryByText('Org v2')).not.toBeInTheDocument();
  });

  it('hides the version tag when a switcher owns the version', () => {
    render(
      <OrganizationStatusBadges
        organization={organizationFixture()}
        version='hidden'
      />
    );

    expect(screen.queryByText('Organization Version 2')).not.toBeInTheDocument();
  });

  it('hides listing status while the organization is pending review', () => {
    render(<OrganizationStatusBadges organization={organizationFixture()} />);

    expect(screen.queryByText('operational')).not.toBeInTheDocument();
    expect(screen.getByText('pending review')).toBeVisible();
  });

  it('hides listing status when review status is omitted', () => {
    render(
      <OrganizationStatusBadges
        organization={organizationFixture({ review_status: undefined })}
      />
    );

    expect(screen.queryByText('operational')).not.toBeInTheDocument();
    expect(screen.getByText('pending review')).toBeVisible();
  });

  it('shows listing status after review is approved', () => {
    render(
      <OrganizationStatusBadges
        organization={organizationFixture({
          status: 'closed_temporarily',
          review_status: 'approved',
        })}
      />
    );

    expect(screen.getByText('closed temporarily')).toBeVisible();
    expect(screen.getByText('approved')).toBeVisible();
  });

  it('shows listing status after review is rejected', () => {
    render(
      <OrganizationStatusBadges
        organization={organizationFixture({ review_status: 'rejected' })}
      />
    );

    expect(screen.getByText('operational')).toBeVisible();
    expect(screen.getByText('rejected')).toBeVisible();
  });
});
