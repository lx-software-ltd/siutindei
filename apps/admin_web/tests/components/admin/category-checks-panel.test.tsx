import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { NuqsTestingAdapter } from 'nuqs/adapters/testing';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { CategoryChecksPanel } from '@/components/admin/category-suggestions/category-checks-panel';
import { resetAdminQueryClientForTests } from '@/lib/admin-query-client';
import { request } from '@/lib/api-client-core';
import {
  getCategorySuggestionSettings,
  getCategorySuggestionSummary,
  listCategoryReviews,
  startCategoryScan,
} from '@/lib/api-client-category-suggestions';

vi.mock('@/lib/api-client-core', () => ({
  buildApiUrl: (path: string) => `https://example.test/${path}`,
  request: vi.fn(),
}));

vi.mock('@/lib/api-client-category-suggestions', () => ({
  decideCategoryReviewsBulk: vi.fn(),
  getCategorySuggestionSettings: vi.fn(),
  getCategorySuggestionSummary: vi.fn(),
  listCategoryReviews: vi.fn(),
  startCategoryScan: vi.fn(),
}));

function wrapper({ children }: { children: ReactNode }) {
  const client = resetAdminQueryClientForTests();
  return (
    <QueryClientProvider client={client}>
      <NuqsTestingAdapter hasMemory searchParams='?section=data-quality&tab=checks'>
        {children}
      </NuqsTestingAdapter>
    </QueryClientProvider>
  );
}

describe('CategoryChecksPanel sweep buttons', () => {
  beforeEach(() => {
    vi.mocked(request).mockResolvedValue({ items: [] });
    vi.mocked(listCategoryReviews).mockResolvedValue({
      items: [],
      next_cursor: null,
    });
    vi.mocked(getCategorySuggestionSettings).mockResolvedValue({
      on_import_enabled: true,
      auto_enrich_enabled: true,
      fallback_models: [],
      max_evidence_items: 25,
      deny_data_collection: true,
      auto_assign_threshold: 0.9,
    });
    vi.mocked(getCategorySuggestionSummary).mockResolvedValue({
      by_status: {},
      by_enrichment_status: {},
      pending_activity_total: 0,
      stranded_activity_total: 0,
      month_cost_usd: 0,
      review_pending_total: 0,
      auto_applied_total: 0,
      scan_candidate_total: 2,
      scan_candidate_total_all: 5,
      scan_limit: 500,
      scan_batch_size: 10,
      discover_activity_total: 1,
      discover_label_total: 1,
    });
    vi.mocked(startCategoryScan).mockResolvedValue({
      id: 'run-1',
      status: 'queued',
      batch_size: 10,
      total_activities: 2,
      batches_total: 1,
      batches_done: 0,
      confirmed: 0,
      auto_applied: 0,
      reassign_pending: 0,
      proposed: 0,
      skipped: 0,
      failed: 0,
      cost_usd: 0,
    });
  });

  it('offers pending and all-orgs sweep buttons and not verify', async () => {
    render(<CategoryChecksPanel />, { wrapper });
    expect(await screen.findByRole('button', { name: 'Sweep pending' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sweep all orgs' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Discover categories' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Verify categories' })).not.toBeInTheDocument();
  });

  it('sweeps pending review or all organizations from the matching button', async () => {
    const user = userEvent.setup();
    render(<CategoryChecksPanel />, { wrapper });
    await user.click(await screen.findByRole('button', { name: 'Sweep pending' }));
    await user.click(screen.getByRole('button', { name: 'Start scan' }));
    await waitFor(() =>
      expect(startCategoryScan).toHaveBeenCalledWith(
        expect.objectContaining({
          mode: 'verify',
          review_scope: 'pending_review',
        })
      )
    );
    await user.click(screen.getByRole('button', { name: 'Sweep all orgs' }));
    await user.click(screen.getByRole('button', { name: 'Start scan' }));
    await waitFor(() =>
      expect(startCategoryScan).toHaveBeenCalledWith(
        expect.objectContaining({
          mode: 'verify',
          review_scope: 'all',
        })
      )
    );
  });
});
