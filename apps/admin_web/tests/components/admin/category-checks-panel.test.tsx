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
  decideCategoryReviewsBulk,
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
    vi.mocked(decideCategoryReviewsBulk).mockResolvedValue({
      decided: 0,
      skipped: 0,
      failed: 0,
      matched: 0,
      applicable: 0,
      failures: [],
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

  it('offers sweep buttons and not discover', async () => {
    render(<CategoryChecksPanel />, { wrapper });
    const sweepPending = await screen.findByRole('button', { name: 'Sweep pending' });
    const sweepAll = screen.getByRole('button', { name: 'Sweep all orgs' });
    const apply = screen.getByRole('button', { name: 'Apply matching' });
    const dismiss = screen.getByRole('button', { name: 'Dismiss matching' });
    expect(screen.queryByRole('button', { name: 'Discover all categories' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Discover categories' })).not.toBeInTheDocument();
    expect(
      sweepPending.compareDocumentPosition(sweepAll) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
    expect(
      sweepAll.compareDocumentPosition(apply) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
    expect(
      apply.compareDocumentPosition(dismiss) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
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

  it('cycles the header checkbox from visible rows to all matching rows', async () => {
    const user = userEvent.setup();
    vi.mocked(listCategoryReviews).mockResolvedValue({
      items: [
        {
          id: 'rev-1',
          scan_run_id: 'run-1',
          activity_id: 'act-1',
          activity_name: 'Clay club',
          org_id: 'org-1',
          verdict: 'reassign',
          status: 'pending',
        },
      ],
      next_cursor: 'page-2',
    });
    render(<CategoryChecksPanel />, { wrapper });
    const header = await screen.findByRole('checkbox', { name: 'Select visible rows' });
    await user.click(header);
    expect(screen.getByRole('checkbox', { name: 'Select all matching rows' })).toBeChecked();
    await user.click(screen.getByRole('checkbox', { name: 'Select all matching rows' }));
    expect(screen.getByRole('checkbox', { name: 'Clear selection' })).toBeChecked();
    expect(
      screen.getByText(/All matching records are selected/)
    ).toBeInTheDocument();
  });
});
