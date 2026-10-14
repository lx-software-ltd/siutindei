'use client';

import { useQuery } from '@tanstack/react-query';

import { getAdminQueryClient } from '../../lib/admin-query-client';
import { getResourceApi, type ApiMode } from '../../lib/resource-api';
import type { Organization } from '../../types/admin';
import { StatusBadge } from '../ui/status-badge';

export function OrganizationStatusBadges({
  organization,
  version = 'org',
}: {
  organization: Organization;
  /** `org` labels the workspace roll-up. `hidden` leaves version to a switcher. */
  version?: 'org' | 'hidden';
}) {
  return (
    <span className='inline-flex flex-wrap items-center gap-1'>
      <StatusBadge
        status={(organization.status ?? 'operational').replaceAll('_', ' ')}
      />
      <StatusBadge
        status={(organization.review_status ?? 'pending_review').replaceAll(
          '_',
          ' '
        )}
      />
      {version === 'org' && organization.version ? (
        <span className='rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700'>
          {`Organization Version ${organization.version}`}
        </span>
      ) : null}
    </span>
  );
}

/**
 * Organization name and review badges shown above a workspace table card.
 * Pass `organization` when the page already loaded it. Otherwise the
 * title loads the organization for `orgId`.
 */
export function OrganizationWorkspaceTitle({
  mode,
  orgId,
  organization,
}: {
  mode: ApiMode;
  orgId: string | null;
  organization?: Organization | null;
}) {
  const provided = organization !== undefined;
  const query = useQuery(
    {
      queryKey: ['admin', 'organization', 'workspace-title', mode, orgId],
      enabled: !provided && Boolean(orgId),
      queryFn: () => {
        if (!orgId) {
          throw new Error('Organization id is required');
        }
        return getResourceApi<Organization>('organizations', mode).get(orgId);
      },
    },
    getAdminQueryClient()
  );
  const shown = provided ? organization : (query.data ?? null);
  const name = shown?.name?.trim() || 'Organization';

  return (
    <div className='flex flex-wrap items-center gap-2'>
      <h2 className='text-lg font-semibold text-slate-900'>{name}</h2>
      {shown ? <OrganizationStatusBadges organization={shown} /> : null}
    </div>
  );
}
