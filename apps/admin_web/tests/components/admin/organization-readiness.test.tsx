import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { NuqsTestingAdapter } from 'nuqs/adapters/testing';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { OrganizationReadiness } from '@/components/admin/organization-readiness';
import {
  decideOrgReview,
  getOrgReviewDetail,
} from '@/lib/api-client-org-review';

vi.mock('@/lib/api-client-org-review', () => ({
  decideOrgReview: vi.fn(),
  getOrgReviewDetail: vi.fn(),
}));

vi.mock('@/lib/admin-query-client', () => ({
  refreshCatalogHistory: vi.fn(),
}));

const detail = {
  id: 'org-1',
  name: 'Harbour Club',
  status: 'operational',
  review_status: 'pending_review' as const,
  location_count: 0,
  activity_count: 0,
  pricing_count: 0,
  schedule_count: 0,
  completeness: 0,
  blocker_count: 1,
  warning_count: 0,
  issues: [
    {
      code: 'no_locations',
      severity: 'blocker' as const,
      entity_type: 'organization' as const,
      entity_id: 'org-1',
      message: 'No locations',
    },
  ],
  organization: {},
  locations: [],
  activities: [],
};

function wrapper({ children }: { children: ReactNode }) {
  return (
    <NuqsTestingAdapter
      hasMemory
      searchParams='?section=organizations&org=org-1'
    >
      {children}
    </NuqsTestingAdapter>
  );
}

describe('OrganizationReadiness', () => {
  beforeEach(() => {
    vi.mocked(getOrgReviewDetail).mockResolvedValue(detail);
    vi.mocked(decideOrgReview).mockResolvedValue({});
  });

  it('renders Readiness as an input card with editor actions', async () => {
    render(<OrganizationReadiness orgId='org-1' />, { wrapper });

    expect(
      await screen.findByRole('heading', { name: 'Readiness' })
    ).toBeVisible();
    expect(screen.getByTestId('admin-editor-panel')).toBeInTheDocument();
    expect(screen.getByText('No locations')).toBeVisible();
    expect(
      within(screen.getByRole('listitem')).getByRole('button', { name: 'Fix' })
    ).toBeVisible();
    expect(screen.getByRole('button', { name: 'Approve' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Reject' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Reopen' })).toBeVisible();
    expect(screen.getByLabelText(/Approve anyway/)).toBeVisible();
  });

  it('approves from the editor action row', async () => {
    const user = userEvent.setup();
    render(<OrganizationReadiness orgId='org-1' />, { wrapper });
    await screen.findByRole('button', { name: 'Approve' });

    await user.click(screen.getByLabelText(/Approve anyway/));
    await user.click(screen.getByRole('button', { name: 'Approve' }));

    await waitFor(() => {
      expect(decideOrgReview).toHaveBeenCalledWith('org-1', {
        action: 'approve',
        force: true,
      });
    });
    expect(
      await screen.findByText(
        'Organization approved. Public search can stay cached for up to 5 minutes.'
      )
    ).toBeVisible();
  });
});
