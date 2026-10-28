import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
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
  type CategorySuggestionSummary,
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

function wrapperFor(searchParams: string) {
  return function wrapper({ children }: { children: ReactNode }) {
    const client = resetAdminQueryClientForTests();
    return (
      <QueryClientProvider client={client}>
        <NuqsTestingAdapter hasMemory searchParams={searchParams}>
          {children}
        </NuqsTestingAdapter>
      </QueryClientProvider>
    );
  };
}

const wrapper = wrapperFor('?section=data-quality&tab=checks');
const scopedWrapper = wrapperFor(
  '?section=data-quality&tab=checks&organization=org-1'
);

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

  it('defaults the status filter to pending', async () => {
    render(<CategoryChecksPanel />, { wrapper });
    expect(await screen.findByLabelText('Status')).toHaveValue('pending');
    await waitFor(() =>
      expect(listCategoryReviews).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'pending' })
      )
    );
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
    expect(apply).toHaveClass('bg-brand-100');
    expect(dismiss).toHaveClass('bg-brand-100');
    expect(apply).not.toHaveClass('bg-accent-500');
  });

  it('puts a scoped organization above the card, not in the filter bar', async () => {
    render(<CategoryChecksPanel />, { wrapper: scopedWrapper });
    const note = await screen.findByText(
      /Filtered to the organization from the review queue/
    );
    const card = screen.getByTestId('admin-record-table');
    expect(card).not.toContainElement(note);
    expect(screen.getByRole('button', { name: 'Show all' })).toBeVisible();
    expect(screen.queryByLabelText('Organization')).not.toBeInTheDocument();
    const heading = screen.getByRole('heading', { name: 'Data quality · Categories' });
    expect(heading.compareDocumentPosition(note) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    await waitFor(() => expect(listCategoryReviews).toHaveBeenCalled());
    const calls = vi.mocked(listCategoryReviews).mock.calls;
    expect(calls[0]?.[0]).toMatchObject({ org_id: 'org-1' });
    expect(calls.every((call) => call[0]?.org_id === 'org-1')).toBe(true);
  });

  it('shows waiting and auto-assigned in KPI cards', async () => {
    let resolveSummary: (value: CategorySuggestionSummary) => void = () => undefined;
    vi.mocked(getCategorySuggestionSummary).mockImplementation(
      () =>
        new Promise<CategorySuggestionSummary>((resolve) => {
          resolveSummary = resolve;
        })
    );
    render(<CategoryChecksPanel />, { wrapper });
    const cards = await screen.findAllByTestId('admin-kpi-card');
    expect(cards).toHaveLength(2);
    expect(cards[0]).toHaveTextContent('Waiting');
    expect(cards[0]).toHaveTextContent('0');
    expect(cards[1]).toHaveTextContent('Auto-assigned');
    resolveSummary({
      by_status: {},
      by_enrichment_status: {},
      pending_activity_total: 0,
      stranded_activity_total: 0,
      month_cost_usd: 0,
      review_pending_total: 4,
      auto_applied_total: 2,
      scan_candidate_total: 2,
      scan_candidate_total_all: 5,
      scan_limit: 500,
      scan_batch_size: 10,
      discover_activity_total: 1,
      discover_label_total: 1,
    });
    await waitFor(() => {
      const updated = screen.getAllByTestId('admin-kpi-card');
      expect(updated[0]).toHaveTextContent('4');
      expect(updated[1]).toHaveTextContent('2');
    });
    expect(screen.queryByText('4 waiting. 2 auto-assigned.')).not.toBeInTheDocument();
    expect(screen.queryByText('Loading…')).not.toBeInTheDocument();
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
  it('hides organization and current columns', async () => {
    vi.mocked(listCategoryReviews).mockResolvedValue({
      items: [
        {
          id: 'rev-1',
          scan_run_id: 'run-1',
          activity_id: 'act-1',
          activity_name: 'Clay club',
          org_id: 'org-1',
          org_name: 'Harbor Arts',
          current_category_name: 'Sport',
          proposed_category_name: 'Ceramics',
          verdict: 'reassign',
          status: 'pending',
        },
      ],
      next_cursor: null,
    });
    render(<CategoryChecksPanel />, { wrapper });
    const table = await screen.findByRole('table', {
      name: 'Data quality · Categories',
    });
    expect(
      within(table).queryByRole('columnheader', { name: 'Organization' })
    ).not.toBeInTheDocument();
    expect(
      within(table).queryByRole('columnheader', { name: 'Current' })
    ).not.toBeInTheDocument();
    expect(
      within(table).getByRole('columnheader', { name: 'Proposed' })
    ).toBeInTheDocument();
    expect(
      within(table).queryByRole('cell', { name: 'Harbor Arts' })
    ).not.toBeInTheDocument();
    expect(
      within(table).queryByRole('cell', { name: 'Sport' })
    ).not.toBeInTheDocument();
    expect(
      within(table).getByRole('cell', { name: 'Ceramics' })
    ).toBeInTheDocument();
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
