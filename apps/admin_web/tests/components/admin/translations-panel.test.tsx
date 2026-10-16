import { QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { NuqsTestingAdapter } from 'nuqs/adapters/testing';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TranslationsPanel } from '@/components/admin/data-quality/translations-panel';
import { resetAdminQueryClientForTests } from '@/lib/admin-query-client';
import {
  decideTranslationFix,
  decideTranslationFixesBulk,
  getTranslationFixSettings,
  getTranslationFixSummary,
  listTranslationFixes,
  scanTranslationFixes,
} from '@/lib/api-client-data-quality';

vi.mock('@/lib/api-client-data-quality', () => ({
  decideTranslationFix: vi.fn(),
  decideTranslationFixesBulk: vi.fn(),
  getTranslationFix: vi.fn(),
  getTranslationFixSettings: vi.fn(),
  getTranslationFixSummary: vi.fn(),
  listTranslationFixes: vi.fn(),
  scanTranslationFixes: vi.fn(),
  updateTranslationFixSettings: vi.fn(),
}));

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

function wrapper({ children }: { children: ReactNode }) {
  return renderPanel(children, '?section=data-quality&tab=translations');
}

describe('TranslationsPanel', () => {
  beforeEach(() => {
    vi.mocked(getTranslationFixSettings).mockResolvedValue({
      monthly_cost_limit_usd: 50,
    });
    vi.mocked(getTranslationFixSummary).mockResolvedValue({
      by_status: { pending: 0 },
      month_cost_usd: 0,
      monthly_cost_limit_usd: 50,
      active_run: null,
    });
    vi.mocked(listTranslationFixes).mockResolvedValue({ items: [], next_cursor: null });
    vi.mocked(decideTranslationFixesBulk).mockResolvedValue({
      dry_run: false,
      matched: 0,
      decided: 0,
      failed: 0,
      failures: [],
    });
    vi.mocked(scanTranslationFixes).mockResolvedValue({
      scan_run_id: 'run-1',
      created: 0,
      updated: 0,
      skipped: 0,
      cleared: 0,
      queued_for_model: 1,
      total_entities: 1,
      truncated: false,
      status: 'queued',
    });
    vi.mocked(decideTranslationFix).mockResolvedValue({
      id: 'tr-1',
      entity_type: 'organization',
      entity_id: 'org-1',
      org_id: 'org-1',
      field: 'name',
      missing_languages: [],
      source: 'model',
      status: 'applied',
      current_label: 'English: Harbour Club',
      proposed_label: 'Chinese: 海港会',
      missing_label: '',
    });
  });

  it('offers sweep, decide, and the model budget', async () => {
    render(<TranslationsPanel />, { wrapper });
    expect(
      await screen.findByRole('heading', { name: 'Data quality · Translations' })
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sweep pending' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sweep all orgs' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Apply selected' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Dismiss selected' })).toBeInTheDocument();
    expect(
      await screen.findByRole('heading', { name: 'Model budget', level: 3 })
    ).toHaveClass('text-base', 'font-semibold', 'sm:text-lg');
    expect(await screen.findByLabelText('Monthly limit (USD)')).toHaveValue('50');
    expect(screen.getByText(/category-check model/)).toBeInTheDocument();
  });

  it('queues a pending sweep and shows the count', async () => {
    render(<TranslationsPanel />, { wrapper });
    fireEvent.click(await screen.findByRole('button', { name: 'Sweep pending' }));
    await waitFor(() => {
      expect(scanTranslationFixes).toHaveBeenCalledWith(
        expect.objectContaining({ review_scope: 'pending_review' })
      );
    });
    expect(await screen.findByText(/queued 1/)).toBeInTheDocument();
  });

  it('replaces the sweep notice when the run finishes', async () => {
    const idle = {
      by_status: { pending: 0 },
      month_cost_usd: 0,
      monthly_cost_limit_usd: 50,
      active_run: null,
    };
    const finished = {
      ...idle,
      by_status: { pending: 1 },
      latest_run: {
        scan_run_id: 'run-1',
        status: 'done' as const,
        created: 2,
        updated: 1,
        skipped: 0,
        cleared: 3,
        queued_for_model: 1,
        truncated: false,
      },
    };
    let calls = 0;
    vi.mocked(getTranslationFixSummary).mockImplementation(async () => {
      calls += 1;
      return calls === 1 ? idle : finished;
    });
    render(<TranslationsPanel />, { wrapper });
    expect(await screen.findByText(/This month 0 of 50/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Sweep pending' }));
    expect(await screen.findByText(/Created 2, updated 1/)).toBeInTheDocument();
  });

  it('explains that sweep pending skips an approved organization', async () => {
    render(<TranslationsPanel />, {
      wrapper: ({ children }) =>
        renderPanel(
          children,
          '?section=data-quality&tab=translations&organization=org-1'
        ),
    });
    expect(
      await screen.findByText(/Sweep pending only includes organizations still in review/)
    ).toBeInTheDocument();
  });

  it('applies an edited translation from the open row', async () => {
    vi.mocked(listTranslationFixes).mockResolvedValue({
      items: [
        {
          id: 'tr-1',
          entity_type: 'organization',
          entity_id: 'org-1',
          entity_name: 'Harbour Club',
          org_id: 'org-1',
          field: 'name',
          source_text: { en: 'Harbour Club' },
          proposed_text: { zh: '海港会', 'zh-HK': '海港會' },
          missing_languages: ['zh', 'zh-HK'],
          source: 'model',
          status: 'pending',
          current_label: 'English: Harbour Club',
          proposed_label: 'Chinese: 海港会',
          missing_label: 'Chinese, Hong Kong',
          rationale: 'From the English name',
        },
      ],
      next_cursor: null,
    });
    render(<TranslationsPanel />, { wrapper });
    fireEvent.click(await screen.findByRole('cell', { name: /Harbour Club/ }));
    const chinese = await screen.findByLabelText('Chinese');
    fireEvent.change(chinese, { target: { value: '海港會所' } });
    fireEvent.click(screen.getByRole('button', { name: /^Apply$/ }));
    await waitFor(() => {
      expect(decideTranslationFix).toHaveBeenCalledWith('tr-1', {
        action: 'apply',
        translations: { zh: '海港會所', 'zh-HK': '海港會' },
      });
    });
    expect(await screen.findByText('Translation updated.')).toBeInTheDocument();
  });
});
