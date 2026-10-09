import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
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
  const client = resetAdminQueryClientForTests();
  return (
    <QueryClientProvider client={client}>
      <NuqsTestingAdapter
        hasMemory
        searchParams='?section=data-quality&tab=locations'
      >
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
});
