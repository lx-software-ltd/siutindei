'use client';

import {
  createContext,
  useContext,
  useEffect,
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
  type EnrichmentOverride,
  type EnrichmentProposal,
} from '../../lib/api-client-enrichment';
import { ApiError } from '../../lib/api-client';
import { refreshCatalogHistory, getAdminQueryClient } from '../../lib/admin-query-client';
import { StatusBanner } from '../status-banner';
import { AdminInputCard } from '../ui/admin-input-card';
import { Button } from '../ui/button';
import { StatusBadge } from '../ui/status-badge';
import { ProposalTable } from './organization-enrichment-proposals';
import { OrganizationEnrichmentSettings } from './organization-enrichment-settings';

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
  savedWebsite: string;
  draftWebsite: string;
  detailsDirty: boolean;
  pending: boolean;
  error: string;
  start: () => void;
  onApplied?: () => Promise<void>;
};

const EnrichmentScopeContext = createContext<Scope | null>(null);

export function OrgEnrichmentScope({
  orgId,
  savedWebsite,
  draftWebsite,
  detailsDirty,
  onApplied,
  children,
}: {
  orgId: string | null;
  savedWebsite: string;
  draftWebsite: string;
  detailsDirty: boolean;
  onApplied?: () => Promise<void>;
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
      value={{
        orgId,
        savedWebsite,
        draftWebsite,
        detailsDirty,
        pending,
        error,
        start,
        onApplied,
      }}
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
  const saved = scope.savedWebsite.trim();
  const draft = scope.draftWebsite.trim();
  const missingWebsite = saved.length === 0 && draft.length === 0;
  const unsavedWebsite = saved !== draft;
  const title = missingWebsite
    ? 'Add a website first'
    : unsavedWebsite
      ? 'Save the website first'
      : 'Enrich from the website';
  return (
    <Button
      type='button'
      variant='secondary'
      size='md'
      loading={scope.pending}
      loadingLabel='Enriching…'
      disabled={missingWebsite || unsavedWebsite}
      title={title}
      data-testid='enrich-from-website'
      onClick={() => scope.start()}
    >
      Enrich from website
    </Button>
  );
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
  const [overrides, setOverrides] = useState<Record<string, EnrichmentOverride>>({});
  const [busy, setBusy] = useState<'apply' | 'dismiss' | null>(null);
  const [notice, setNotice] = useState('');
  const [actionError, setActionError] = useState('');
  const runId = query.data?.run?.id ?? '';

  useEffect(() => {
    setSelected([]);
    setOverrides({});
    setNotice('');
    setActionError('');
  }, [orgId, runId]);

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

  function chosenOverrides() {
    const body: Record<string, EnrichmentOverride> = {};
    for (const id of selected) {
      const draft = overrides[id];
      if (!draft) {
        continue;
      }
      const cleaned: EnrichmentOverride = {};
      if (draft.area_id) {
        cleaned.area_id = draft.area_id;
      }
      if (draft.category_id) {
        cleaned.category_id = draft.category_id;
      }
      if (draft.location_id) {
        cleaned.location_id = draft.location_id;
      }
      if (draft.age_min !== undefined && !Number.isNaN(draft.age_min)) {
        cleaned.age_min = draft.age_min;
      }
      if (draft.age_max !== undefined && !Number.isNaN(draft.age_max)) {
        cleaned.age_max = draft.age_max;
      }
      if (Object.keys(cleaned).length > 0) {
        body[id] = cleaned;
      }
    }
    return body;
  }

  async function decide(action: 'apply' | 'dismiss') {
    if (!scope?.orgId || selected.length === 0) {
      return;
    }
    if (action === 'apply' && scope.detailsDirty) {
      return;
    }
    setBusy(action);
    setActionError('');
    setNotice('');
    try {
      const result = await decideOrgEnrichment(
        scope.orgId,
        action,
        selected,
        action === 'apply' ? chosenOverrides() : undefined
      );
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
      if (action === 'apply' && result.results.some((row) => row.status === 'applied')) {
        await scope.onApplied?.();
      }
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
              disabled={selected.length === 0 || busy !== null || scope.detailsDirty}
              title={
                scope.detailsDirty
                  ? 'Save the Details form before applying'
                  : 'Apply selected'
              }
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
      {scope.detailsDirty && pendingIds.length ? (
        <p className='mb-3 text-sm text-slate-600'>
          Save or discard the Details edits before applying these changes.
        </p>
      ) : null}
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
              venues={query.data?.venues ?? []}
              selected={selected}
              overrides={overrides}
              onToggle={toggle}
              onOverride={(id, patch) =>
                setOverrides((current) => ({ ...current, [id]: patch }))
              }
            />
          </section>
        );
      })}
      <OrganizationEnrichmentSettings />
    </AdminInputCard>
  );
}

export type { EnrichmentProposal };
