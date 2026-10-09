import { QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { NuqsTestingAdapter } from 'nuqs/adapters/testing';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LocationsPanel } from '@/components/admin/data-quality/locations-panel';
import { resetAdminQueryClientForTests } from '@/lib/admin-query-client';
import {
  getLocationFixSettings,
  getLocationFixSummary,
  listLocationFixes,
} from '@/lib/api-client-data-quality';

vi.mock('@/lib/api-client-data-quality', () => ({
  decideLocationFix: vi.fn(),
  decideLocationFixesBulk: vi.fn(),
  getLocationFix: vi.fn(),
  getLocationFixSettings: vi.fn(),
  getLocationFixSummary: vi.fn(),
  listLocationFixes: vi.fn(),
  scanLocationFixes: vi.fn(),
  updateLocationFixSettings: vi.fn(),
}));

vi.mock('@/hooks/use-geographic-areas', () => ({
  useGeographicAreas: () => ({
    tree: [],
    countryCodes: '',
    isLoading: false,
    matchNominatimResult: () => null,
  }),
}));

function wrapper({ children }: { children: ReactNode }) {
  return renderPanel(children, '?section=data-quality&tab=locations');
}

function renderPanel(children: ReactNode, searchParams: string) {
  const client = resetAdminQueryClientForTests();
  return (
    <QueryClientProvider client={client}>
      <NuqsTestingAdapter hasMemory searchParams={searchParams}>
        {children}
      </NuqsTestingAdapter>
    </QueryClientProvider>
  );
}

describe('LocationsPanel', () => {
  beforeEach(() => {
    vi.mocked(getLocationFixSettings).mockResolvedValue({
      monthly_cost_limit_usd: 50,
    });
    vi.mocked(getLocationFixSummary).mockResolvedValue({
      by_status: { pending: 0 },
      pending_by_kind: {},
      month_cost_usd: 0,
      monthly_cost_limit_usd: 50,
      active_run: null,
    });
    vi.mocked(listLocationFixes).mockResolvedValue({ items: [], next_cursor: null });
  });

  it('offers the location sweep and decide actions', async () => {
    render(<LocationsPanel />, { wrapper });
    expect(await screen.findByRole('button', { name: 'Sweep pending' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sweep all orgs' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Apply selected' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Dismiss selected' })).toBeInTheDocument();
    expect(screen.getByLabelText('Kind')).toBeInTheDocument();
    expect(screen.getByLabelText('Source')).toBeInTheDocument();
    expect(await screen.findByLabelText('Monthly limit (USD)')).toHaveValue('50');
  });

  it('explains that sweep pending skips an approved organization', async () => {
    render(<LocationsPanel />, {
      wrapper: ({ children }) =>
        renderPanel(
          children,
          '?section=data-quality&tab=locations&organization=org-1'
        ),
    });
    expect(
      await screen.findByText(/Sweep pending only includes organizations still in review/)
    ).toBeInTheDocument();
  });

  it('offers the locations screen for an unresolved row', async () => {
    vi.mocked(listLocationFixes).mockResolvedValue({
      items: [
        {
          id: 'loc-fix-9',
          entity_type: 'organization',
          entity_id: 'org-9',
          entity_name: 'Harbour Club',
          org_id: 'org-9',
          kind: 'unresolved',
          source: 'model',
          status: 'pending',
          current_label: 'No location',
          proposed_label: 'Needs a location',
          rationale: 'Model could not propose an address',
        },
      ],
      next_cursor: null,
    });
    render(<LocationsPanel />, { wrapper });
    fireEvent.click(await screen.findByText('Harbour Club'));
    expect(
      await screen.findByRole('button', { name: 'Create a location' })
    ).toBeInTheDocument();
  });

  it('offers the location editor for an unresolved venue', async () => {
    vi.mocked(listLocationFixes).mockResolvedValue({
      items: [
        {
          id: 'loc-fix-10',
          entity_type: 'location',
          entity_id: 'venue-1',
          entity_name: '8 Harbour Road',
          org_id: 'org-9',
          kind: 'unresolved',
          source: 'rule:empty_address',
          status: 'pending',
          current_label: 'No address',
          proposed_label: 'Add an address',
          rationale: 'Location has no address',
        },
      ],
      next_cursor: null,
    });
    render(<LocationsPanel />, { wrapper });
    fireEvent.click(await screen.findByText('8 Harbour Road'));
    expect(
      await screen.findByRole('button', { name: 'Edit location' })
    ).toBeInTheDocument();
  });
});
