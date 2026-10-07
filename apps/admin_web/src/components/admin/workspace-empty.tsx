'use client';

import type { ReactNode } from 'react';

import { Button } from '../ui/button';
import { useOrganizationScope } from '@/hooks/use-organization-scope';

export function WorkspaceEmpty({
  noun = 'this section',
}: {
  noun?: string;
}) {
  const { openCatalog } = useOrganizationScope();

  return (
    <div className='rounded-lg border border-slate-200 bg-white p-6'>
      <p className='text-base font-semibold text-slate-900'>
        Choose an organization
      </p>
      <p className='mt-1 text-sm text-slate-600'>
        Open an organization from the catalog to work on {noun}.
      </p>
      <Button type='button' className='mt-4' onClick={openCatalog}>
        Open catalog
      </Button>
    </div>
  );
}

/** Admin without `?org=` sees the catalog prompt. Managers wait for their org. */
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
    <p className='text-sm text-slate-600'>Loading the organization…</p>
  );
}
