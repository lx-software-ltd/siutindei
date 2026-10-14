import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ImportRunStatus } from '@/components/admin/import-run-status';
import { resetAdminQueryClientForTests } from '@/lib/admin-query-client';
import { request } from '@/lib/api-client-core';
import {
  getDataQualityRun,
  retryDataQualityRun,
} from '@/lib/api-client-data-quality';

vi.mock('@/lib/api-client-core', () => ({
  request: vi.fn(),
  buildApiUrl: (path: string) => path,
}));

const run = {
  id: 'run-1',
  trigger: 'import',
  scope: {},
  checks: [{ name: 'duplicates', status: 'done' }],
  status: 'done',
  attempt: 1,
  attempts: 1,
};

function wrapper({ children }: { children: ReactNode }) {
  const client = resetAdminQueryClientForTests();
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe('data quality run client', () => {
  beforeEach(() => {
    vi.mocked(request).mockReset();
    vi.mocked(request).mockResolvedValue(run);
  });

  it('retries with a refresh', async () => {
    await retryDataQualityRun('run-1');
    expect(request).toHaveBeenCalledWith(
      'v1/admin/data-quality/runs/run-1',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ action: 'retry', refresh: true }),
      })
    );
  });

  it('polls a status view', async () => {
    await getDataQualityRun('run-1', 'status');
    expect(request).toHaveBeenCalledWith(
      'v1/admin/data-quality/runs/run-1?view=status'
    );
  });

  it('shows the import footer from the status view', async () => {
    render(<ImportRunStatus runId='run-1' />, { wrapper });
    expect(await screen.findByText(/duplicates done/)).toBeInTheDocument();
    await waitFor(() => {
      expect(request).toHaveBeenCalledWith(
        'v1/admin/data-quality/runs/run-1?view=status'
      );
    });
  });
});
