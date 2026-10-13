import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { NuqsTestingAdapter } from 'nuqs/adapters/testing';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { MediaPanel } from '@/components/admin/media-panel';
import { resetAdminQueryClientForTests } from '@/lib/admin-query-client';
import { ApiError } from '@/lib/api-client-core';
import { getResourceApi } from '@/lib/resource-api';

vi.mock('@/lib/resource-api', () => ({
  getResourceApi: vi.fn(),
}));

function wrapper({ children }: { children: ReactNode }) {
  const client = resetAdminQueryClientForTests();
  return (
    <QueryClientProvider client={client}>
      <NuqsTestingAdapter hasMemory searchParams='?section=media&org=org-1'>
        {children}
      </NuqsTestingAdapter>
    </QueryClientProvider>
  );
}

describe('MediaPanel load error', () => {
  beforeEach(() => {
    vi.mocked(getResourceApi).mockReturnValue({
      get: vi.fn().mockRejectedValue(new ApiError('Organization missing.', 404)),
    } as never);
  });

  it('shows the error when the organization fails to load', async () => {
    render(<MediaPanel />, { wrapper });

    expect(await screen.findByText('Organization missing.')).toBeVisible();
    expect(screen.queryByText('Loading media…')).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Media' })).not.toBeInTheDocument();
  });
});
