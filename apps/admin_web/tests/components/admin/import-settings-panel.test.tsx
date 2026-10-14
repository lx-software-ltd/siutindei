import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { NuqsTestingAdapter } from 'nuqs/adapters/testing';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ImportSettingsPanel } from '@/components/admin/import-settings-panel';
import { resetAdminQueryClientForTests } from '@/lib/admin-query-client';
import { ApiError } from '@/lib/api-client';
import {
  getImportSettings,
  updateImportSettings,
  type ImportSettings,
} from '@/lib/api-client-imports';

vi.mock('@/lib/api-client-imports', () => ({
  getImportSettings: vi.fn(),
  updateImportSettings: vi.fn(),
}));

const stored: ImportSettings = {
  skip_deleted_organizations: true,
  name_cleanup: 'apply',
  unknown_categories: 'capture',
  duplicates: 'off',
  locations: 'off',
  categories: 'off',
  updated_at: '2026-10-14T00:00:00+00:00',
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
    vi.mocked(getImportSettings).mockResolvedValue(stored);
    vi.mocked(updateImportSettings).mockImplementation(async (body) => ({
      ...body,
      updated_at: '2026-10-14T00:01:00+00:00',
    }));
  });

  it('saves import behaviour and shows the page name', async () => {
    const user = userEvent.setup();
    render(<ImportSettingsPanel />, { wrapper });

    expect(
      await screen.findByRole('heading', { name: /^Settings$/ })
    ).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Imports · Settings' })).toBeInTheDocument();
    expect(screen.getByLabelText('Names')).toHaveValue('apply');
    expect(screen.getByRole('checkbox', { name: 'Skip deleted organizations' })).toBeChecked();

    await user.selectOptions(screen.getByLabelText('Duplicates'), 'report');
    await user.click(screen.getByRole('button', { name: 'Save settings' }));

    await waitFor(() => {
      expect(updateImportSettings).toHaveBeenCalledWith({
        ...stored,
        duplicates: 'report',
      });
    });
    expect(await screen.findByText('Settings saved.')).toBeVisible();
  });

  it('warns when deleted organizations can be imported again', async () => {
    const user = userEvent.setup();
    render(<ImportSettingsPanel />, { wrapper });
    await user.click(
      await screen.findByRole('checkbox', { name: 'Skip deleted organizations' })
    );
    expect(
      screen.getByText('Deleted organizations can be created again by a later import.')
    ).toBeVisible();
  });

  it('reloads when another save wins', async () => {
    const user = userEvent.setup();
    vi.mocked(updateImportSettings).mockRejectedValue(
      new ApiError('Import settings were updated', 409)
    );
    render(<ImportSettingsPanel />, { wrapper });
    await user.click(await screen.findByRole('button', { name: 'Save settings' }));
    expect(
      await screen.findByText(
        'Settings were updated. Review the current values and save again.'
      )
    ).toBeVisible();
    expect(getImportSettings).toHaveBeenCalledTimes(2);
  });

  it('shows a load error instead of a permanent loading line', async () => {
    vi.mocked(getImportSettings).mockRejectedValue(new Error('Settings failed.'));
    render(<ImportSettingsPanel />, { wrapper });

    expect(await screen.findByText('Settings failed.')).toBeVisible();
    expect(screen.queryByText('Loading settings...')).not.toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /^Settings$/ })
    ).toBeVisible();
  });
});
