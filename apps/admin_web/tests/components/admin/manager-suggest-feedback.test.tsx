import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { NuqsTestingAdapter } from 'nuqs/adapters/testing';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AdminDashboard } from '@/components/admin/admin-dashboard';
import {
  getUserAccessStatus,
  getUserFeedback,
  getUserSuggestions,
  listFeedbackLabels,
  fetchActiveAreas,
} from '@/lib/api-client-user';
import { listManagerOrganizations } from '@/lib/api-client-manager';

vi.mock('next/image', () => ({
  default: ({ alt, src }: { alt: string; src: string }) => (
    <img alt={alt} src={src} />
  ),
}));

vi.mock('@/components/auth-provider', () => ({
  useAuth: () => ({
    status: 'authenticated',
    user: { email: 'manager@example.com', groups: ['manager'] },
    isAdmin: false,
    isManager: true,
    logout: vi.fn(),
    error: '',
    configErrors: [],
  }),
}));

vi.mock('@/components/shared', () => ({
  OrganizationsPanel: () => <div>Organization workspace</div>,
  LocationsPanel: () => <div>Locations workspace</div>,
  ActivitiesPanel: () => <div>Activities workspace</div>,
  PricingPanel: () => <div>Pricing workspace</div>,
  SchedulesPanel: () => <div>Schedules workspace</div>,
}));

vi.mock('@/lib/api-client-user', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api-client-user')>(
    '@/lib/api-client-user'
  );
  return {
    ...actual,
    getUserAccessStatus: vi.fn(),
    getUserSuggestions: vi.fn(),
    getUserFeedback: vi.fn(),
    listFeedbackLabels: vi.fn(),
    fetchActiveAreas: vi.fn(),
  };
});

vi.mock('@/lib/api-client-manager', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api-client-manager')>(
    '@/lib/api-client-manager'
  );
  return {
    ...actual,
    listManagerOrganizations: vi.fn(),
  };
});

const urlUpdates: string[] = [];

function wrapper({ children }: { children: ReactNode }) {
  return (
    <NuqsTestingAdapter
      hasMemory
      searchParams='?section=organizations&org=org-1'
      onUrlUpdate={(event) => {
        urlUpdates.push(event.queryString);
      }}
    >
      {children}
    </NuqsTestingAdapter>
  );
}

describe('manager suggest and feedback pages', () => {
  beforeEach(() => {
    urlUpdates.length = 0;
    vi.mocked(getUserAccessStatus).mockResolvedValue({
      organizations_count: 1,
      has_pending_request: false,
      pending_request: null,
    });
    vi.mocked(getUserSuggestions).mockResolvedValue({
      has_pending_suggestion: false,
      suggestions: [],
    });
    vi.mocked(getUserFeedback).mockResolvedValue({
      has_pending_feedback: false,
      feedbacks: [],
    });
    vi.mocked(listFeedbackLabels).mockResolvedValue({ items: [] });
    vi.mocked(fetchActiveAreas).mockResolvedValue({ items: [] });
    vi.mocked(listManagerOrganizations).mockResolvedValue({
      items: [{ id: 'org-1', name: 'Test Organization 1' }],
      next_cursor: null,
    });
  });

  it('stays on Suggest a Place and Feedback without reloading the account', async () => {
    const user = userEvent.setup();
    render(<AdminDashboard />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText('Organization workspace')).toBeVisible();
    });
    const statusCalls = vi.mocked(getUserAccessStatus).mock.calls.length;

    await user.click(screen.getAllByRole('button', { name: 'Suggest a Place' })[0]);
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Suggest a place' })).toBeVisible();
    });
    expect(screen.queryByText('Loading your account information...')).not.toBeInTheDocument();
    expect(urlUpdates.at(-1)).toContain('section=suggest-place');
    expect(urlUpdates.at(-1)).toContain('org=org-1');
    expect(vi.mocked(getUserAccessStatus).mock.calls.length).toBe(statusCalls);

    await user.click(screen.getAllByRole('button', { name: 'Feedback' })[0]);
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Leave feedback' })).toBeVisible();
    });
    expect(screen.queryByText('Loading your account information...')).not.toBeInTheDocument();
    expect(urlUpdates.at(-1)).toContain('section=feedback');
    expect(urlUpdates.at(-1)).toContain('org=org-1');
    expect(vi.mocked(getUserAccessStatus).mock.calls.length).toBe(statusCalls);
  });
});
