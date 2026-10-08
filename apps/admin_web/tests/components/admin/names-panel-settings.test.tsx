import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { NuqsTestingAdapter } from 'nuqs/adapters/testing';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { NamesPanel } from '@/components/admin/data-quality/names-panel';
import { resetAdminQueryClientForTests } from '@/lib/admin-query-client';
import {
  getNameFixSettings,
  getNameFixSummary,
  listNameFixes,
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
  });

  it('keeps a space so a new exception word can be typed', async () => {
    const user = userEvent.setup();
    render(<NamesPanel />, { wrapper });
    const exceptions = await screen.findByLabelText('Words to leave in capitals');
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
});
