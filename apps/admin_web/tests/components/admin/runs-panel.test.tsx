import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { NuqsTestingAdapter } from 'nuqs/adapters/testing';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { RunsPanel } from '@/components/admin/data-quality/runs-panel';
import { resetAdminQueryClientForTests } from '@/lib/admin-query-client';
import {
  createDataQualityRun,
  listDataQualityRuns,
} from '@/lib/api-client-data-quality';
import { listImportJobs, type ImportJobListItem } from '@/lib/api-client-org-review';
import { searchUserOrganizations } from '@/lib/api-client-user';
import { formatDateTime } from '@/lib/date-utils';

vi.mock('@/lib/api-client-data-quality', () => ({
  listDataQualityRuns: vi.fn(),
  createDataQualityRun: vi.fn(),
  retryDataQualityRun: vi.fn(),
}));

vi.mock('@/lib/api-client-user', () => ({
  searchUserOrganizations: vi.fn(),
}));

vi.mock('@/lib/api-client-org-review', () => ({
  listImportJobs: vi.fn(),
}));

const organizations = [
  { id: 'org-1', name: 'Harbour Club' },
  { id: 'org-2', name: 'Harbor Arts' },
];

function importJob(index: number): ImportJobListItem {
  return {
    id: `job-${index}`,
    object_key: `admin/imports/${index}.json`,
    dry_run: false,
    status: 'completed',
    summary: {},
    file_warnings: [],
    created_at: new Date(Date.UTC(2026, 0, 21 - index, 15, 4, 0)).toISOString(),
  };
}

const importJobs = Array.from({ length: 21 }, (_, index) => importJob(index));

function wrapper({ children }: { children: ReactNode }) {
  const client = resetAdminQueryClientForTests();
  return (
    <QueryClientProvider client={client}>
      <NuqsTestingAdapter hasMemory searchParams='?section=data-quality&tab=runs'>
        {children}
      </NuqsTestingAdapter>
    </QueryClientProvider>
  );
}

describe('RunsPanel scope', () => {
  beforeEach(() => {
    vi.mocked(listDataQualityRuns).mockResolvedValue({ items: [] });
    vi.mocked(createDataQualityRun).mockResolvedValue({
      id: 'run-new',
      trigger: 'manual',
      scope: {},
      checks: [],
      status: 'queued',
      attempt: 1,
      attempts: 1,
    });
    vi.mocked(searchUserOrganizations).mockImplementation(async (query: string) => ({
      items: organizations.filter((item) =>
        item.name.toLowerCase().includes(query.toLowerCase())
      ),
    }));
    vi.mocked(listImportJobs).mockResolvedValue({ items: importJobs });
  });

  it('starts a run from an organization name', async () => {
    const user = userEvent.setup();
    render(<RunsPanel />, { wrapper });

    await user.selectOptions(await screen.findByLabelText('Scope'), 'organization');
    expect(screen.queryByLabelText('Organization id')).not.toBeInTheDocument();
    const field = screen.getByLabelText('Organization');
    expect(screen.getByRole('button', { name: 'Run checks' })).toBeDisabled();

    await user.type(field, 'H');
    await new Promise((resolve) => {
      setTimeout(resolve, 400);
    });
    expect(searchUserOrganizations).not.toHaveBeenCalled();

    await user.type(field, 'a');
    await user.click(await screen.findByRole('option', { name: 'Harbour Club' }));

    expect(field).toHaveValue('Harbour Club');
    expect(searchUserOrganizations).toHaveBeenCalledWith('Ha', 10);
    await user.click(screen.getByRole('button', { name: 'Run checks' }));

    await waitFor(() => {
      expect(createDataQualityRun).toHaveBeenCalledWith({
        checks: ['names', 'duplicates'],
        scope: {
          kind: 'organization',
          org_id: 'org-1',
          import_job_id: undefined,
        },
      });
    });
  });

  it('lists the last 20 imports by create time', async () => {
    const user = userEvent.setup();
    render(<RunsPanel />, { wrapper });

    expect(listImportJobs).not.toHaveBeenCalled();
    await user.selectOptions(await screen.findByLabelText('Scope'), 'import');
    expect(screen.queryByLabelText('Import id')).not.toBeInTheDocument();

    await waitFor(() => {
      expect(listImportJobs).toHaveBeenCalledWith(undefined, 20);
    });

    const importSelect = await screen.findByLabelText('Import');
    const newest = formatDateTime(importJobs[0].created_at);
    await waitFor(() => {
      expect(importSelect.querySelector('option[value="job-0"]')).toHaveTextContent(
        newest
      );
    });
    expect(importSelect.querySelector('option[value="job-0"]')?.textContent).not.toBe(
      'job-0'
    );
    expect(importSelect.querySelector('option[value="job-20"]')).toBeNull();
    expect(importSelect.querySelectorAll('option')).toHaveLength(21);

    await user.selectOptions(screen.getByLabelText('Import'), 'job-0');
    await user.click(screen.getByRole('button', { name: 'Run checks' }));

    await waitFor(() => {
      expect(createDataQualityRun).toHaveBeenCalledWith({
        checks: ['names', 'duplicates'],
        scope: {
          kind: 'import',
          org_id: undefined,
          import_job_id: 'job-0',
        },
      });
    });
  });
});
