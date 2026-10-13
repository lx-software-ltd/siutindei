'use client';

import type { ReactNode } from 'react';

import { useOrganizationScope } from '@/hooks/use-organization-scope';

import { AdminInputCard } from '../ui/admin-input-card';
import { Button } from '../ui/button';

export function WorkspaceEmpty({
  noun = 'this section',
}: {
  noun?: string;
}) {
  const { openCatalog } = useOrganizationScope();

  return (
    <AdminInputCard
      title='Choose an organization'
      description={`Open an organization from the catalog to work on ${noun}.`}
      actions={
        <Button type='button' onClick={openCatalog}>
          Open catalog
        </Button>
      }
    />
  );
}

/** Admin without `?org=` sees the catalog prompt. Managers see an empty state. */
export function WorkspaceScopeGate({
  orgId,
  isAdmin,
  noun,
  children,
}: {
  orgId: string | null;
  isAdmin: boolean;
  noun: string;
  children: ReactNode;
}) {
  if (orgId) {
    return children;
  }
  if (isAdmin) {
    return <WorkspaceEmpty noun={noun} />;
  }
  return (
    <AdminInputCard
      title='No organization is selected'
      description='This account has no organization open. Refresh the page, or ask an owner to assign one.'
    />
  );
}
