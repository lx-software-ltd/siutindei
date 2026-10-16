'use client';

import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { useQuery } from '@tanstack/react-query';

import { adminQueryKeys } from '../../lib/admin-query-keys';
import {
  decideOrgEnrichment,
  getOrgEnrichment,
  startOrgEnrichment,
  type EnrichmentProposal,
} from '../../lib/api-client-enrichment';
import { ApiError } from '../../lib/api-client';
import { refreshCatalogHistory, getAdminQueryClient } from '../../lib/admin-query-client';
import { StatusBanner } from '../status-banner';
import { AdminInputCard } from '../ui/admin-input-card';
import {
  AdminDataTable,
  AdminDataTableBody,
  AdminDataTableCell,
  AdminDataTableCellMeta,
  AdminDataTableHead,
  AdminDataTableHeadCell,
} from '../ui/admin-data-table';
import {
  AdminTableName,
  AdminTableNumber,
  formatAdminTablePercent,
} from '../ui/admin-table-value';
import { Button } from '../ui/button';
import { StatusBadge } from '../ui/status-badge';

const COPYRIGHT_NOTICE =
  'Copied from the provider website for this catalog. Copyright remains with the provider.';

const SECTIONS = [
  'Organization',
  'Media',
  'Locations',
  'Activities',
  'Pricing',
  'Schedules',
] as const;

const ACTIVE = new Set(['queued', 'running', 'extracting']);

type Scope = {
  orgId: string | null;
  website: string;
  pending: boolean;
  error: string;
  start: () => void;
};

const EnrichmentScopeContext = createContext<Scope | null>(null);

export function OrgEnrichmentScope({
  orgId,
  website,
  children,
}: {
  orgId: string | null;
  website: string;
  children: ReactNode;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');

  async function start() {
    if (!orgId || pending) {
      return;
    }
    setPending(true);
    setError('');
    try {
      await startOrgEnrichment(orgId);
      await getAdminQueryClient().invalidateQueries({
        queryKey: adminQueryKeys.orgEnrichment(orgId),
      });
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : 'Enrichment could not start.');
    } finally {
      setPending(false);
    }
  }

  return (
    <EnrichmentScopeContext.Provider
      value={{ orgId, website, pending, error, start }}
    >
      {children}
    </EnrichmentScopeContext.Provider>
  );
}

export function OrganizationEnrichButton() {
  const scope = useContext(EnrichmentScopeContext);
  if (!scope?.orgId) {
    return null;
  }
  const missingWebsite = scope.website.trim().length === 0;
  return (
    <Button
      type='button'
      variant='secondary'
      size='md'
      loading={scope.pending}
      loadingLabel='Enriching…'
      disabled={missingWebsite}
      title={missingWebsite ? 'Add a website first' : 'Enrich from the website'}
      data-testid='enrich-from-website'
      onClick={() => scope.start()}
    >
      Enrich from website
    </Button>
  );
}

function proposedText(value: Record<string, unknown>): string {
  return Object.entries(value)
    .filter(([key]) => key !== 'copyright_notice')
    .map(([key, item]) => {
      if (item && typeof item === 'object') {
        return `${key}: ${JSON.stringify(item)}`;
      }
      return `${key}: ${String(item ?? '')}`;
    })
    .join(' · ');
}

function statusTone(status: string) {
  if (status === 'ready' || status === 'applied') {
    return 'green' as const;
  }
  if (status === 'failed') {
    return 'red' as const;
  }
  if (status === 'running' || status === 'extracting') {
    return 'blue' as const;
  }
  return 'yellow' as const;
}

export function OrganizationEnrichmentCard({ hidden }: { hidden: boolean }) {
  const scope = useContext(EnrichmentScopeContext);
  const orgId = scope?.orgId ?? '';
  const query = useQuery(
    {
      queryKey: adminQueryKeys.orgEnrichment(orgId),
      queryFn: () => getOrgEnrichment(orgId),
      enabled: Boolean(orgId) && !hidden,
      refetchInterval: (current) =>
        ACTIVE.has(current.state.data?.run?.status ?? '') ? 3000 : false,
    },
    getAdminQueryClient()
  );
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState<'apply' | 'dismiss' | null>(null);
  const [notice, setNotice] = useState('');
  const [actionError, setActionError] = useState('');

  const proposals = useMemo(
    () => query.data?.proposals ?? [],
    [query.data?.proposals]
  );
  const pendingIds = useMemo(
    () => proposals.filter((row) => row.status === 'pending').map((row) => row.id),
    [proposals]
  );

  if (hidden || !scope?.orgId) {
    return null;
  }
  const run = query.data?.run ?? null;
  if (!run && !scope.error && !query.isError) {
    return null;
  }

  function toggle(id: string) {
    setSelected((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id]
    );
  }

  async function decide(action: 'apply' | 'dismiss') {
    if (!scope?.orgId || selected.length === 0) {
      return;
    }
    setBusy(action);
    setActionError('');
    setNotice('');
    try {
      const result = await decideOrgEnrichment(scope.orgId, action, selected);
      const failed = result.results.filter((row) => row.status === 'error');
      setNotice(
        failed.length
          ? `${result.results.length - failed.length} updated. ${failed.length} need another look.`
          : action === 'apply'
            ? 'Selected changes were applied.'
            : 'Selected changes were dismissed.'
      );
      setSelected([]);
      await getAdminQueryClient().invalidateQueries({
        queryKey: adminQueryKeys.orgEnrichment(scope.orgId),
      });
      await getAdminQueryClient().invalidateQueries({
        queryKey: adminQueryKeys.resourceList('organizations', 'admin'),
      });
      refreshCatalogHistory();
    } catch (err: unknown) {
      setActionError(
        err instanceof ApiError ? err.message : 'The selection could not be saved.'
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <AdminInputCard
      title='Website enrichment'
      titleLevel='h3'
      description={COPYRIGHT_NOTICE}
      data-testid='website-enrichment'
      status={
        scope.error || actionError || query.isError ? (
          <StatusBanner kind='error'>
            {scope.error ||
              actionError ||
              (query.error instanceof ApiError
                ? query.error.message
                : 'Enrichment could not be loaded.')}
          </StatusBanner>
        ) : notice ? (
          <StatusBanner kind='saved'>{notice}</StatusBanner>
        ) : null
      }
      actions={
        pendingIds.length ? (
          <>
            <Button
              type='button'
              variant='secondary'
              loading={busy === 'apply'}
              loadingLabel='Applying…'
              disabled={selected.length === 0 || busy !== null}
              onClick={() => void decide('apply')}
            >
              Apply selected
            </Button>
            <Button
              type='button'
              variant='secondary'
              loading={busy === 'dismiss'}
              loadingLabel='Dismissing…'
              disabled={selected.length === 0 || busy !== null}
              onClick={() => void decide('dismiss')}
            >
              Dismiss selected
            </Button>
          </>
        ) : null
      }
    >
      {run ? (
        <div className='mb-4 flex flex-wrap items-center gap-2'>
          <StatusBadge status={run.status} tone={statusTone(run.status)} />
          <span className='text-sm text-slate-600'>
            {run.pages_fetched} pages
            {run.error ? ` · ${run.error}` : ''}
          </span>
        </div>
      ) : null}
      {run && ACTIVE.has(run.status) ? (
        <p className='text-sm text-slate-600'>Reading the website…</p>
      ) : null}
      {run && run.status === 'ready' && proposals.length === 0 ? (
        <p className='text-sm text-slate-600'>No new fields were found.</p>
      ) : null}
      {SECTIONS.map((section) => {
        const rows = proposals.filter((row) => row.section === section);
        if (rows.length === 0) {
          return null;
        }
        return (
          <section key={section} className='mb-4 space-y-2'>
            <h4 className='text-sm font-semibold text-slate-900'>{section}</h4>
            <ProposalTable
              rows={rows}
              selected={selected}
              onToggle={toggle}
            />
          </section>
        );
      })}
    </AdminInputCard>
  );
}

function ProposalTable({
  rows,
  selected,
  onToggle,
}: {
  rows: EnrichmentProposal[];
  selected: string[];
  onToggle: (id: string) => void;
}) {
  return (
    <AdminDataTable>
      <AdminDataTableHead>
        <tr>
          <AdminDataTableHeadCell className='w-10'>Select</AdminDataTableHeadCell>
          <AdminDataTableHeadCell>Proposal</AdminDataTableHeadCell>
          <AdminDataTableHeadCell priority='secondary'>Value</AdminDataTableHeadCell>
          <AdminDataTableHeadCell priority='tertiary'>Confidence</AdminDataTableHeadCell>
          <AdminDataTableHeadCell priority='secondary'>Status</AdminDataTableHeadCell>
        </tr>
      </AdminDataTableHead>
      <AdminDataTableBody>
        {rows.map((row) => {
          const value = proposedText(row.proposed_value);
          const pending = row.status === 'pending';
          return (
            <tr key={row.id}>
              <AdminDataTableCell>
                <input
                  type='checkbox'
                  aria-label={`Select ${row.label}`}
                  checked={selected.includes(row.id)}
                  disabled={!pending}
                  onChange={() => onToggle(row.id)}
                />
              </AdminDataTableCell>
              <AdminDataTableCell>
                <AdminTableName>{row.label}</AdminTableName>
                <AdminDataTableCellMeta label='Value' until='secondary'>
                  {value}
                </AdminDataTableCellMeta>
                <AdminDataTableCellMeta label='Confidence' until='tertiary'>
                  {formatAdminTablePercent(row.confidence)}
                  {row.unverified ? ' · unverified' : ''}
                </AdminDataTableCellMeta>
              </AdminDataTableCell>
              <AdminDataTableCell priority='secondary'>{value}</AdminDataTableCell>
              <AdminDataTableCell priority='tertiary'>
                <AdminTableNumber>
                  {formatAdminTablePercent(row.confidence)}
                  {row.unverified ? ' unverified' : ''}
                </AdminTableNumber>
              </AdminDataTableCell>
              <AdminDataTableCell priority='secondary'>
                <StatusBadge status={row.status} tone={statusTone(row.status)} />
              </AdminDataTableCell>
            </tr>
          );
        })}
      </AdminDataTableBody>
    </AdminDataTable>
  );
}
