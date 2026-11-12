import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { NuqsTestingAdapter } from 'nuqs/adapters/testing';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useQuery } from '@tanstack/react-query';

import { AuditLogsPanel, loadApiKeyNames } from '@/components/admin/audit-logs-panel';
import {
  getAdminQueryClient,
  refreshApiKeyActorNames,
  resetAdminQueryClientForTests,
} from '@/lib/admin-query-client';
import { adminQueryKeys } from '@/lib/admin-query-keys';
import { listApiKeys } from '@/lib/api-client-api-keys';
import { listAuditLogs, type AuditLogsResponse } from '@/lib/api-client-audit';
import { listCognitoUsers } from '@/lib/api-client-cognito';
import type { CognitoUser } from '@/types/admin';

vi.mock('@/lib/api-client-api-keys', () => ({
  listApiKeys: vi.fn(),
}));

vi.mock('@/lib/api-client-audit', () => ({
  listAuditLogs: vi.fn(),
}));

vi.mock('@/lib/api-client-cognito', () => ({
  listCognitoUsers: vi.fn(),
}));

const logs: AuditLogsResponse = {
  items: [
    {
      id: 'audit-user',
      table_name: 'organizations',
      record_id: 'org-1',
      action: 'UPDATE',
      source: 'admin',
      user_id: 'user-1',
      request_id: 'req-1',
      changed_fields: ['name'],
      old_values: { name: 'Old' },
      new_values: { name: 'New' },
      timestamp: '2024-01-07T10:00:00Z',
      ip_address: null,
      user_agent: null,
    },
    {
      id: 'audit-system',
      table_name: 'activities',
      record_id: 'activity-1',
      action: 'INSERT',
      source: '',
      user_id: null,
      request_id: null,
      changed_fields: null,
      old_values: null,
      new_values: { name: 'New' },
      timestamp: '2024-01-07T11:00:00Z',
      ip_address: null,
      user_agent: null,
    },
    {
      id: 'audit-key',
      table_name: 'locations',
      record_id: 'loc-1',
      action: 'DELETE',
      source: 'partner',
      user_id: 'api-key:key-1',
      request_id: 'req-key',
      changed_fields: ['name'],
      old_values: { name: 'Old' },
      new_values: null,
      timestamp: '2024-01-07T12:00:00Z',
      ip_address: null,
      user_agent: null,
    },
    {
      id: 'audit-job',
      table_name: 'tickets',
      record_id: 'ticket-1',
      action: 'DELETE',
      source: 'category-scan',
      user_id: 'category-scan:run-1',
      request_id: 'req-scan',
      changed_fields: ['category_id'],
      old_values: { category_id: 'old' },
      new_values: { category_id: 'new' },
      timestamp: '2024-01-07T13:00:00Z',
      ip_address: null,
      user_agent: null,
    },
  ],
  next_cursor: null,
};

function renderPanel() {
  const client = resetAdminQueryClientForTests();
  function wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <NuqsTestingAdapter>{children}</NuqsTestingAdapter>
      </QueryClientProvider>
    );
  }
  render(<AuditLogsPanel />, { wrapper });
}

describe('audit log key names', () => {
  beforeEach(() => {
    vi.mocked(listAuditLogs).mockResolvedValue(logs);
    const user: CognitoUser = {
      sub: 'user-1',
      username: 'google_user-1',
      email: 'a@example.com',
      email_verified: true,
      enabled: true,
      status: 'CONFIRMED',
      groups: [],
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      attributes: { email: 'a@example.com' },
    };
    vi.mocked(listCognitoUsers).mockResolvedValue({
      items: [user],
      pagination_token: null,
    });
  });

  it('shows an error when key names cannot be loaded', async () => {
    vi.mocked(listApiKeys).mockRejectedValue(new Error('offline'));
    renderPanel();

    expect(await screen.findByText('Could not load API key names.')).toBeVisible();
    expect(screen.getAllByText('system').length).toBeGreaterThan(0);
    expect(screen.getAllByText('category check').length).toBeGreaterThan(0);
    expect(screen.queryByText('category-scan:run-1')).toBeNull();
    expect(screen.queryByText('migration')).toBeNull();
    expect(screen.getAllByRole('img', { name: 'Google' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('img', { name: 'API key' }).length).toBeGreaterThan(0);
    expect(screen.queryByText('Partner read key')).toBeNull();
  });

  it('shows the key name when the lookup succeeds', async () => {
    vi.mocked(listApiKeys).mockResolvedValue({
      items: [
        {
          id: 'key-1',
          name: 'Partner read key',
          key_prefix: 'stk_read',
          scope: 'read',
          org_id: null,
          status: 'active',
          created_by: 'user-1',
          created_at: '2024-01-01T00:00:00Z',
          expires_at: null,
          revoked_at: null,
          last_used_at: null,
        },
      ],
      next_cursor: null,
    });
    renderPanel();

    expect((await screen.findAllByText('Partner read key')).length).toBeGreaterThan(0);
    expect(screen.queryByText('Could not load API key names.')).toBeNull();
  });

  it('does not turn a failed lookup into an empty success', async () => {
    vi.mocked(listApiKeys).mockRejectedValue(new Error('offline'));
    await expect(loadApiKeyNames()).rejects.toThrow('offline');
  });
});

describe('refreshApiKeyActorNames', () => {
  it('refetches the actor-name cache', async () => {
    const client = resetAdminQueryClientForTests();
    const queryFn = vi.fn().mockResolvedValue({ 'key-1': 'Partner read key' });

    function Probe() {
      const query = useQuery(
        { queryKey: adminQueryKeys.apiKeyActorNames(), queryFn },
        getAdminQueryClient()
      );
      return <div>{query.isSuccess ? 'ready' : 'loading'}</div>;
    }

    render(
      <QueryClientProvider client={client}>
        <Probe />
      </QueryClientProvider>
    );
    expect(await screen.findByText('ready')).toBeVisible();
    refreshApiKeyActorNames();
    await waitFor(() => expect(queryFn).toHaveBeenCalledTimes(2));
  });
});
