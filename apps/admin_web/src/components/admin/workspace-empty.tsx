'use client';

import type { ReactNode } from 'react';

import { Button } from '../ui/button';
import { Card } from '../ui/card';
import { useOrganizationScope } from '@/hooks/use-organization-scope';

export function WorkspaceEmpty({
  noun = 'this section',
}: {
  noun?: string;
}) {
  const { openCatalog } = useOrganizationScope();

  return (
    <Card
      title='Choose an organization'
      description={`Open an organization from the catalog to work on ${noun}.`}
    >
      <Button type='button' onClick={openCatalog}>
        Open catalog
      </Button>
    </Card>
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
    <Card
      title='No organization is selected'
      description='This account has no organization open. Refresh the page, or ask an owner to assign one.'
    />
  );
}
