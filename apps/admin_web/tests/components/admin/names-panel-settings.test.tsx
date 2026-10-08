import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { NuqsTestingAdapter } from 'nuqs/adapters/testing';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { NamesPanel } from '@/components/admin/data-quality/names-panel';
import { resetAdminQueryClientForTests } from '@/lib/admin-query-client';
import {
  decideNameFixesBulk,
  getNameFixSettings,
  getNameFixSummary,
  listNameFixes,
  scanNameFixes,
  updateNameFixSettings,
} from '@/lib/api-client-data-quality';

vi.mock('@/lib/api-client-data-quality', () => ({
  decideNameFix: vi.fn(),
  decideNameFixesBulk: vi.fn(),
  getNameFix: vi.fn(),
  getNameFixSettings: vi.fn(),
  getNameFixSummary: vi.fn(),
  listNameFixes: vi.fn(),
  scanNameFixes: vi.fn(),
  updateNameFixSettings: vi.fn(),
}));

const settings = {
  enabled_rules: ['title_case'],
  available_rules: ['title_case'],
  exception_words: ['YMCA'],
  bracket_suffixes: ['lcsd'],
};

function wrapper({ children }: { children: ReactNode }) {
  const client = resetAdminQueryClientForTests();
  return (
    <QueryClientProvider client={client}>
      <NuqsTestingAdapter hasMemory searchParams='?section=data-quality&tab=names'>
        {children}
      </NuqsTestingAdapter>
    </QueryClientProvider>
  );
}

describe('NamesPanel settings lists', () => {
  beforeEach(() => {
    vi.mocked(getNameFixSettings).mockResolvedValue(settings);
    vi.mocked(getNameFixSummary).mockResolvedValue({
      by_status: { pending: 0 },
      pending_by_entity: {},
    });
    vi.mocked(listNameFixes).mockResolvedValue({ items: [], next_cursor: null });
    vi.mocked(updateNameFixSettings).mockImplementation(async (body) => body);
    vi.mocked(scanNameFixes).mockResolvedValue({
      scan_run_id: 'scan-1',
      created: 0,
      updated: 0,
      skipped: 0,
      cleared: 0,
      truncated: false,
    });
    vi.mocked(decideNameFixesBulk).mockResolvedValue({
      dry_run: false,
      matched: 1,
      decided: 1,
      failed: 0,
      failures: [],
    });
  });

  it('offers pending and all-orgs sweep buttons and not a regular scan', async () => {
    render(<NamesPanel />, { wrapper });
    expect(await screen.findByRole('button', { name: 'Sweep pending' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sweep all orgs' })).toBeInTheDocument();
    expect(screen.queryByLabelText('Sweep')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Scan names' })).not.toBeInTheDocument();
  });

  it('sweeps pending review or all organizations from the matching button', async () => {
    const user = userEvent.setup();
    render(<NamesPanel />, { wrapper });
    await user.click(await screen.findByRole('button', { name: 'Sweep pending' }));
    await waitFor(() =>
      expect(scanNameFixes).toHaveBeenCalledWith(
        expect.objectContaining({ review_scope: 'pending_review' })
      )
    );
    await user.click(screen.getByRole('button', { name: 'Sweep all orgs' }));
    await waitFor(() =>
      expect(scanNameFixes).toHaveBeenCalledWith(
        expect.objectContaining({ review_scope: 'all' })
      )
    );
  });

  it('keeps a space so a new exception word can be typed', async () => {
    const user = userEvent.setup();
    render(<NamesPanel />, { wrapper });
    const heading = await screen.findByRole('heading', { name: 'Rules' });
    expect(heading.parentElement).toHaveClass('bg-white');
    const exceptions = screen.getByLabelText('Words to leave in capitals');
    expect(exceptions.tagName).toBe('TEXTAREA');
    expect(exceptions).toHaveAttribute('rows', '3');
    await user.click(exceptions);
    await user.type(exceptions, ' YWCA');
    expect(exceptions).toHaveValue('YMCA YWCA');
    await user.click(screen.getByRole('button', { name: 'Save rules' }));
    await waitFor(() =>
      expect(updateNameFixSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          exception_words: ['YMCA', 'YWCA'],
          bracket_suffixes: ['lcsd'],
        })
      )
    );
  });

  it('cycles the header checkbox from visible rows to all matching rows', async () => {
    const user = userEvent.setup();
    vi.mocked(listNameFixes).mockResolvedValue({
      items: [
        {
          id: 'fix-1',
          entity_type: 'organization',
          entity_id: 'org-1',
          current_value: 'HARBOUR CLUB',
          proposed_value: 'Harbour Club',
          rules: ['title_case'],
          status: 'pending',
        },
      ],
      next_cursor: 'page-2',
    });
    render(<NamesPanel />, { wrapper });
    const header = await screen.findByRole('checkbox', { name: 'Select visible rows' });
    await user.click(header);
    expect(screen.getByRole('checkbox', { name: 'Select all matching rows' })).toBeChecked();
    await user.click(screen.getByRole('checkbox', { name: 'Select all matching rows' }));
    expect(screen.getByRole('checkbox', { name: 'Clear selection' })).toBeChecked();
    expect(
      screen.getByText(/All matching records are selected/)
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Apply selected' }));
    await waitFor(() =>
      expect(decideNameFixesBulk).toHaveBeenCalledWith(
        expect.objectContaining({
          action: 'apply',
        })
      )
    );
    expect(vi.mocked(decideNameFixesBulk).mock.calls[0][0]).not.toHaveProperty('ids');
  });
});
