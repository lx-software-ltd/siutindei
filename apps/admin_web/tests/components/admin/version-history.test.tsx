import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  ageBoundsFromSnapshot,
  organizationFormFromSnapshot,
} from '@/components/admin/catalog-version-snapshot';
import {
  catalogLatestVersion,
  useCatalogVersion,
  VersionField,
  VersionFields,
  VersionSwitcher,
  VersionViewBanner,
} from '@/components/admin/version-history';
import { resetAdminQueryClientForTests } from '@/lib/admin-query-client';
import { listEntireCatalogHistory } from '@/lib/api-client-versions';
import type { ApiMode } from '@/lib/resource-api';
import { emptyForm } from '@/components/shared/organizations/organization-form-utils';

vi.mock('@/lib/api-client-versions', () => ({
  forgetCatalogVersion: vi.fn(),
  listCatalogVersions: vi.fn(),
  listEntireCatalogHistory: vi.fn(),
}));

function wrapper({ children }: { children: ReactNode }) {
  const client = resetAdminQueryClientForTests();
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function Harness({ mode = 'admin' }: { mode?: ApiMode }) {
  const view = useCatalogVersion({
    mode,
    entityType: 'organization',
    entityId: 'org-1',
    version: 2,
  });
  return (
    <VersionFields view={view}>
      <VersionSwitcher view={view} />
      <VersionViewBanner view={view} />
      <VersionField label='Name' versionKey='name'>
        <input aria-label='Name' readOnly={view.locked} />
      </VersionField>
    </VersionFields>
  );
}

describe('catalogLatestVersion', () => {
  it('treats a missing version as 1', () => {
    expect(catalogLatestVersion(null)).toBe(1);
    expect(catalogLatestVersion(undefined)).toBe(1);
    expect(catalogLatestVersion(0)).toBe(1);
  });

  it('uses the higher of the live version and history', () => {
    expect(catalogLatestVersion(3, [{ version: 2 }])).toBe(3);
    expect(catalogLatestVersion(1, [{ version: 4 }])).toBe(4);
  });
});

describe('snapshot forms', () => {
  it('reads an exclusive age range as inclusive bounds', () => {
    expect(ageBoundsFromSnapshot('[5,13)')).toEqual({ min: '5', max: '12' });
  });

  it('keeps live values for keys the snapshot omits', () => {
    const fallback = { ...emptyForm, name: 'Live', email: 'live@example.com' };
    const next = organizationFormFromSnapshot({ name: 'Original' }, fallback);
    expect(next.name).toBe('Original');
    expect(next.email).toBe('live@example.com');
  });
});

describe('version switcher', () => {
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
  });

  it('opens a menu and marks the earlier version read-only', async () => {
    const user = userEvent.setup();
    render(<Harness />, { wrapper });

    const version = await screen.findByRole('button', { name: 'Version 2 · Latest' });
    expect(screen.getByLabelText('Name')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'History' })).not.toBeInTheDocument();

    await user.click(version);
    await user.click(await screen.findByRole('menuitem', { name: /Version 1/ }));

    expect(await screen.findByText('Viewing version 1 of 2 · read-only')).toBeVisible();
    expect(screen.getByText('Latest: Current name')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Version 1' })).toBeVisible();
    expect(screen.getByLabelText('Name')).toHaveAttribute('readonly');
  });

  it('shows managers a static version pill', async () => {
    render(<Harness mode='manager' />, { wrapper });

    expect(await screen.findByText('Version 2')).toBeVisible();
    expect(screen.queryByRole('button', { name: /Version/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'History' })).not.toBeInTheDocument();
    expect(listEntireCatalogHistory).not.toHaveBeenCalled();
  });
});
