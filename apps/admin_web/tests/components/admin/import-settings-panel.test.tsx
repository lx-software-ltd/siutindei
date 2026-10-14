import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { NuqsTestingAdapter } from 'nuqs/adapters/testing';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ImportSettingsPanel } from '@/components/admin/import-settings-panel';
import { resetAdminQueryClientForTests } from '@/lib/admin-query-client';
import {
  getImportDataQualitySettings,
  updateImportDataQualitySettings,
} from '@/lib/api-client-imports';

vi.mock('@/lib/api-client-imports', () => ({
  getImportDataQualitySettings: vi.fn(),
  updateImportDataQualitySettings: vi.fn(),
}));

const off = {
  duplicates: false,
  names: false,
  locations: false,
  categories: false,
};

function wrapper({ children }: { children: ReactNode }) {
  const client = resetAdminQueryClientForTests();
  return (
    <QueryClientProvider client={client}>
      <NuqsTestingAdapter hasMemory searchParams='?section=imports&tab=settings'>
        {children}
      </NuqsTestingAdapter>
    </QueryClientProvider>
  );
}

describe('ImportSettingsPanel', () => {
  beforeEach(() => {
    vi.mocked(getImportDataQualitySettings).mockResolvedValue(off);
    vi.mocked(updateImportDataQualitySettings).mockImplementation(
      async (body) => body
    );
  });

  it('lets an admin tick which Data quality checks run on import', async () => {
    const user = userEvent.setup();
    render(<ImportSettingsPanel />, { wrapper });

    expect(
      await screen.findByRole('heading', { name: 'Imports · Settings' })
    ).toBeVisible();
    const names = await screen.findByRole('checkbox', { name: 'Names' });
    expect(names).not.toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Duplicates' })).not.toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Locations' })).not.toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Categories' })).not.toBeChecked();

    await user.click(names);
    await user.click(screen.getByRole('button', { name: 'Save settings' }));

    await waitFor(() => {
      expect(updateImportDataQualitySettings).toHaveBeenCalledWith({
        duplicates: false,
        names: true,
        locations: false,
        categories: false,
      });
    });
    expect(await screen.findByText('Settings saved.')).toBeVisible();
  });

  it('shows a load error instead of a permanent loading line', async () => {
    vi.mocked(getImportDataQualitySettings).mockRejectedValue(
      new Error('Settings failed.')
    );
    render(<ImportSettingsPanel />, { wrapper });

    expect(await screen.findByText('Settings failed.')).toBeVisible();
    expect(screen.queryByText('Loading settings...')).not.toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'Imports · Settings' })
    ).toBeVisible();
  });
});
