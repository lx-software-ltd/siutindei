import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  catalogLatestVersion,
  catalogVersionOptions,
  VersionHistory,
} from '@/components/admin/version-history';
import { resetAdminQueryClientForTests } from '@/lib/admin-query-client';
import {
  forgetCatalogVersion,
  listCatalogVersions,
  listEntireCatalogHistory,
} from '@/lib/api-client-versions';

vi.mock('@/lib/api-client-versions', () => ({
  forgetCatalogVersion: vi.fn(),
  listCatalogVersions: vi.fn(),
  listEntireCatalogHistory: vi.fn(),
}));

function wrapper({ children }: { children: ReactNode }) {
  const client = resetAdminQueryClientForTests();
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe('catalogVersionOptions', () => {
  it('treats a missing version as 1', () => {
    expect(catalogLatestVersion(null)).toBe(1);
    expect(catalogLatestVersion(undefined)).toBe(1);
    expect(catalogLatestVersion(0)).toBe(1);
    expect(catalogVersionOptions(1, { allVersions: true })).toEqual([1]);
  });

  it('lists every version through the latest', () => {
    expect(catalogLatestVersion(3, [{ version: 2 }])).toBe(3);
    expect(catalogVersionOptions(3, { allVersions: true })).toEqual([1, 2, 3]);
  });

  it('keeps only the latest version when history is hidden', () => {
    expect(catalogVersionOptions(3, { allVersions: false })).toEqual([3]);
  });
});

describe('VersionHistory', () => {
  beforeEach(() => {
    vi.mocked(listEntireCatalogHistory).mockResolvedValue({
      items: [
        {
          id: 'ver-2',
          entity_type: 'organization',
          entity_id: 'org-1',
          version: 2,
          action: 'updated',
          snapshot: { name: 'Current name' },
          created_at: '2024-02-01T00:00:00Z',
        },
        {
          id: 'ver-1',
          entity_type: 'organization',
          entity_id: 'org-1',
          version: 1,
          action: 'created',
          snapshot: { name: 'Original name' },
          created_at: '2024-01-01T00:00:00Z',
        },
      ],
      next_cursor: null,
    });
    vi.mocked(listCatalogVersions).mockResolvedValue({
      items: [
        {
          id: 'ver-removed',
          entity_type: 'activity',
          entity_id: 'activity-removed',
          org_id: 'org-1',
          version: 1,
          action: 'created',
          snapshot: { name: 'Removed Class' },
          created_at: '2024-01-02T00:00:00Z',
        },
      ],
      next_cursor: null,
    });
    vi.mocked(forgetCatalogVersion).mockResolvedValue(undefined);
  });

  it('defaults to the latest version and loads an earlier snapshot read-only', async () => {
    const user = userEvent.setup();
    const onHistoricalChange = vi.fn();
    render(
      <VersionHistory
        mode='admin'
        entityType='organization'
        entityId='org-1'
        version={2}
        onHistoricalChange={onHistoricalChange}
      >
        <label htmlFor='live-name'>
          Name
          <input id='live-name' defaultValue='Current name' />
        </label>
      </VersionHistory>,
      { wrapper }
    );

    const version = await screen.findByLabelText('Version');
    expect(version).toHaveValue('2');
    expect(screen.getByLabelText('Name')).toHaveValue('Current name');
    expect(screen.queryByRole('button', { name: 'History' })).not.toBeInTheDocument();
    expect(await screen.findByText(/Removed Class/)).toBeVisible();

    await user.selectOptions(version, '1');
    expect(version).toHaveValue('1');
    expect(await screen.findByText(/Read-only/)).toBeVisible();
    expect(screen.getByText('Original name')).toBeVisible();
    expect(screen.queryByLabelText('Name')).not.toBeInTheDocument();
    expect(onHistoricalChange).toHaveBeenCalledWith(true);

    await user.selectOptions(version, '2');
    expect(screen.getByLabelText('Name')).toHaveValue('Current name');
    expect(screen.queryByText(/Read-only/)).not.toBeInTheDocument();
    expect(onHistoricalChange).toHaveBeenCalledWith(false);
  });

  it('shows only the current version to managers', async () => {
    render(
      <VersionHistory
        mode='manager'
        entityType='organization'
        entityId='org-1'
        version={2}
      >
        <p>Live form</p>
      </VersionHistory>,
      { wrapper }
    );

    const version = await screen.findByLabelText('Version');
    expect(version).toHaveValue('2');
    expect(screen.getByRole('option', { name: '2' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: '1' })).not.toBeInTheDocument();
    expect(screen.getByText('Live form')).toBeVisible();
    expect(listEntireCatalogHistory).not.toHaveBeenCalled();
  });
});
