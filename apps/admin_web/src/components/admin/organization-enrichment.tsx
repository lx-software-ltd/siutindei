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
  createLeafletUpload,
  leafletUploadBody,
  decideOrgEnrichment,
  getOrgEnrichment,
  startOrgEnrichment,
  type EnrichmentOverride,
  type EnrichmentProposal,
  type LeafletStartItem,
} from '../../lib/api-client-enrichment';
import { ApiError } from '../../lib/api-client';
import { refreshCatalogHistory, getAdminQueryClient } from '../../lib/admin-query-client';
import { StatusBanner } from '../status-banner';
import { ImportRunStatus } from './import-run-status';
import { AdminInputCard } from '../ui/admin-input-card';
import { AdminDialog } from '../ui/admin-dialog';
import { Button } from '../ui/button';
import { Label } from '../ui/label';
import { StatusBadge } from '../ui/status-badge';
import { Textarea } from '../ui/textarea';
import { chosenEnrichmentOverrides, firstBlockerMessage } from '../../lib/enrichment-overrides';
import {
  ProposalTable,
  selectionAfterToggle,
} from './organization-enrichment-proposals';
import { OrganizationEnrichmentSettings } from './organization-enrichment-settings';

const COPYRIGHT_NOTICE =
  'Copied from the provider website for this catalog. Copyright remains with the provider.';

const LEAFLET_COPYRIGHT_NOTICE =
  'Copied from a leaflet supplied for this catalog. Copyright remains with the provider.';

const LEAFLET_TYPES: Record<string, string> = {
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  webp: 'image/webp',
  pdf: 'application/pdf',
};

const SECTIONS = [
  'Organization',
  'Media',
  'Locations',
  'Activities',
  'Pricing',
  'Schedules',
] as const;

const ACTIVE = new Set(['queued', 'running', 'extracting']);

export function enrichmentActivityCopy(
  status: string,
  source?: string
): string | null {
  if (status === 'extracting') {
    return 'Reading pages with the model…';
  }
  if (status === 'queued' || status === 'running') {
    return source === 'leaflet' ? 'Reading the leaflet…' : 'Reading the website…';
  }
  return null;
}

export function leafletPresetIds(
  proposals: Array<{
    id: string;
    status: string;
    proposed_value: Record<string, unknown>;
  }>,
  seenIds: readonly string[]
): string[] {
  const seen = new Set(seenIds);
  return proposals
    .filter(
      (row) => row.status === 'pending' && row.proposed_value.leaflet === true
    )
    .map((row) => row.id)
    .filter((id) => !seen.has(id));
}

function leafletContentType(file: File): string {
  if (Object.values(LEAFLET_TYPES).includes(file.type)) {
    return file.type;
  }
  const extension = file.name.split('.').pop()?.toLowerCase() ?? '';
  return LEAFLET_TYPES[extension] ?? '';
}

type Scope = {
  orgId: string | null;
  draftWebsite: string;
  detailsDirty: boolean;
  pending: boolean;
  error: string;
  start: () => void;
  startLeaflet: (items: LeafletStartItem[]) => Promise<void>;
  onApplied?: () => Promise<void>;
};

const EnrichmentScopeContext = createContext<Scope | null>(null);

export function OrgEnrichmentScope({
  orgId,
  draftWebsite,
  detailsDirty,
  onApplied,
  children,
}: {
  orgId: string | null;
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
    const website = draftWebsite.trim();
    setPending(true);
    setError('');
    try {
      await startOrgEnrichment(orgId, website);
      await getAdminQueryClient().invalidateQueries({
        queryKey: adminQueryKeys.orgEnrichment(orgId),
      });
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : 'Enrichment could not start.');
    } finally {
      setPending(false);
    }
  }

  async function startLeaflet(items: LeafletStartItem[]) {
    if (!orgId || pending) {
      return;
    }
    setPending(true);
    setError('');
    try {
      await startOrgEnrichment(orgId, { leaflet: { items } });
      await getAdminQueryClient().invalidateQueries({
        queryKey: adminQueryKeys.orgEnrichment(orgId),
      });
    } catch (err: unknown) {
      const message =
        err instanceof ApiError ? err.message : 'The leaflet could not be read.';
      setError(message);
      throw err instanceof Error ? err : new Error(message);
    } finally {
      setPending(false);
    }
  }

  return (
    <EnrichmentScopeContext.Provider
      value={{
        orgId,
        draftWebsite,
        detailsDirty,
        pending,
        error,
        start,
        startLeaflet,
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
  const draft = scope.draftWebsite.trim();
  const missingWebsite = draft.length === 0;
  const title = missingWebsite ? 'Add a website first' : 'Enrich from the website';
  return (
    <Button
      type='button'
      variant='secondary'
      size='md'
      loading={scope.pending}
      loadingLabel='Enriching…'
      disabled={missingWebsite}
      title={title}
      data-testid='enrich-from-website'
      onClick={() => scope.start()}
    >
      Enrich from website
    </Button>
  );
}

export function OrganizationLeafletButton() {
  const scope = useContext(EnrichmentScopeContext);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [urls, setUrls] = useState('');
  if (!scope?.orgId) {
    return null;
  }

  async function submit() {
    if (!scope?.orgId || busy || scope.pending) {
      return;
    }
    const lines = urls
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean);
    if (files.length + lines.length === 0) {
      setError('Add a picture, a PDF, or a public URL.');
      return;
    }
    if (files.length + lines.length > 4) {
      setError('Send at most four leaflets.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const items: LeafletStartItem[] = [];
      for (const file of files) {
        const contentType = leafletContentType(file);
        if (!contentType) {
          setError('Use a JPEG, PNG, WebP, or PDF.');
          return;
        }
        const limit =
          contentType === 'application/pdf' ? 8_000_000 : 5_000_000;
        if (file.size <= 0 || file.size > limit) {
          setError(
            file.size <= 0
              ? 'The leaflet is empty.'
              : 'The leaflet is too large.'
          );
          return;
        }
        const signed = await createLeafletUpload(
          scope.orgId,
          file.name,
          contentType
        );
        const uploaded = await fetch(signed.upload_url, {
          method: 'POST',
          body: leafletUploadBody(signed.upload_fields, file),
        });
        if (!uploaded.ok) {
          throw new Error('The leaflet could not be uploaded.');
        }
        items.push({ object_key: signed.object_key });
      }
      for (const url of lines) {
        items.push({ url });
      }
      await scope.startLeaflet(items);
      setOpen(false);
      setFiles([]);
      setUrls('');
    } catch (err: unknown) {
      setError(
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'The leaflet could not be read.'
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button
        type='button'
        variant='secondary'
        size='md'
        disabled={scope.pending}
        title='Enrich from a picture or PDF'
        data-testid='enrich-from-leaflet'
        onClick={() => {
          setError('');
          setOpen(true);
        }}
      >
        Enrich from leaflet
      </Button>
      <AdminDialog
        open={open}
        title='Enrich from leaflet'
        description='A picture or a PDF. Up to four files or public URLs. A picture is proposed as media and is not attached until you apply it.'
        onClose={() => {
          if (!busy) {
            setOpen(false);
          }
        }}
        contentClassName='w-full max-w-lg'
        footer={
          <Button
            type='submit'
            form='leaflet-enrich'
            variant='secondary'
            loading={busy}
            loadingLabel='Reading…'
          >
            Read leaflet
          </Button>
        }
      >
        <form
          id='leaflet-enrich'
          className='grid gap-3'
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          {error ? (
            <div id='leaflet-form-error'>
              <StatusBanner kind='error'>{error}</StatusBanner>
            </div>
          ) : null}
          <div>
            <Label htmlFor='leaflet-files'>Leaflet files</Label>
            <input
              id='leaflet-files'
              name='leaflet-files'
              aria-describedby={error ? 'leaflet-form-error' : undefined}
              className='block w-full text-sm text-ink-900 file:mr-3 file:rounded-md file:border-0 file:bg-brand-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-ink-900'
              type='file'
              accept='image/jpeg,image/png,image/webp,application/pdf'
              multiple
              onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
            />
          </div>
          <div>
            <Label htmlFor='leaflet-urls'>Leaflet URLs</Label>
            <Textarea
              id='leaflet-urls'
              name='leaflet-urls'
              rows={4}
              spellCheck={false}
              autoCorrect='off'
              autoCapitalize='off'
              placeholder='One public URL per line'
              value={urls}
              onChange={(event) => setUrls(event.target.value)}
            />
          </div>
        </form>
      </AdminDialog>
    </>
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
  const [qualityRunId, setQualityRunId] = useState('');
  const [actionError, setActionError] = useState('');
  const [applyErrors, setApplyErrors] = useState<Record<string, string>>({});
  const runId = query.data?.run?.id ?? '';
  const enrichmentKey = `${orgId}\0${runId}`;
  const [seenEnrichmentKey, setSeenEnrichmentKey] = useState(enrichmentKey);
  const [seenLeafletIds, setSeenLeafletIds] = useState('');

  const proposals = useMemo(
    () => query.data?.proposals ?? [],
    [query.data?.proposals]
  );
  const pendingIds = useMemo(
    () => proposals.filter((row) => row.status === 'pending').map((row) => row.id),
    [proposals]
  );
  const leafletKey = proposals
    .filter((row) => row.status === 'pending' && row.proposed_value.leaflet === true)
    .map((row) => row.id)
    .join(',');
  if (enrichmentKey !== seenEnrichmentKey) {
    setSeenEnrichmentKey(enrichmentKey);
    setSeenLeafletIds(leafletKey);
    setSelected(leafletPresetIds(proposals, []));
    setOverrides({});
    setNotice('');
    setQualityRunId('');
    setActionError('');
    setApplyErrors({});
  } else if (leafletKey !== seenLeafletIds) {
    const incoming = leafletPresetIds(
      proposals,
      seenLeafletIds.split(',').filter(Boolean)
    );
    setSeenLeafletIds(leafletKey);
    if (incoming.length > 0) {
      setSelected((current) => [
        ...current,
        ...incoming.filter((id) => !current.includes(id)),
      ]);
    }
  }

  if (hidden || !scope?.orgId) {
    return null;
  }
  const run = query.data?.run ?? null;
  if (!run && !scope.error && !query.isError) {
    return null;
  }

  function toggle(id: string) {
    setSelected((current) => selectionAfterToggle(current, id, proposals));
  }

  function chosenOverrides() {
    return chosenEnrichmentOverrides(selected, overrides, proposals);
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
      const nextErrors: Record<string, string> = {};
      for (const row of failed) {
        if (row.error) {
          nextErrors[row.id] = row.error;
        }
      }
      setApplyErrors(nextErrors);
      setNotice(
        failed.length
          ? `${result.results.length - failed.length} updated. ${failed.length} need another look.`
          : action === 'apply'
            ? 'Selected changes were applied.'
            : 'Selected changes were dismissed.'
      );
      setQualityRunId(
        action === 'apply' && result.data_quality_run_id
          ? result.data_quality_run_id
          : ''
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

  const leafletRun = run?.source === 'leaflet';
  return (
    <AdminInputCard
      title={leafletRun ? 'Leaflet enrichment' : 'Website enrichment'}
      titleLevel='h3'
      description={leafletRun ? LEAFLET_COPYRIGHT_NOTICE : COPYRIGHT_NOTICE}
      data-testid={leafletRun ? 'leaflet-enrichment' : 'website-enrichment'}
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
          <div className='space-y-2'>
            <StatusBanner kind='saved'>{notice}</StatusBanner>
            {qualityRunId ? <ImportRunStatus runId={qualityRunId} /> : null}
          </div>
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
                  : firstBlockerMessage(selected, proposals, overrides) ||
                    'Apply selected'
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
        <p className='mb-3 text-sm text-ink-700'>
          Save or discard the Details edits before applying these changes.
        </p>
      ) : null}
      {run ? (
        <div className='mb-4 flex flex-wrap items-center gap-2'>
          <StatusBadge status={run.status} tone={statusTone(run.status)} />
          <span className='text-sm text-ink-700'>
            {leafletRun
              ? run.pages_fetched === 1
                ? '1 leaflet'
                : `${run.pages_fetched} leaflets`
              : `${run.pages_fetched} pages`}
            {run.error ? ` · ${run.error}` : ''}
          </span>
        </div>
      ) : null}
      {run && enrichmentActivityCopy(run.status, run.source) ? (
        <p className='text-sm text-ink-700' data-testid='enrichment-activity'>
          {enrichmentActivityCopy(run.status, run.source)}
        </p>
      ) : null}
      {run && run.status === 'ready' && proposals.length === 0 ? (
        <p className='text-sm text-ink-700'>No new fields were found.</p>
      ) : null}
      {SECTIONS.map((section) => {
        const rows = proposals.filter((row) => row.section === section);
        if (rows.length === 0) {
          return null;
        }
        return (
          <section key={section} className='mb-4 space-y-2'>
            <h4 className='text-sm font-semibold text-ink-900'>{section}</h4>
            <ProposalTable
              rows={rows}
              venues={query.data?.venues ?? []}
              selected={selected}
              overrides={overrides}
              applyErrors={applyErrors}
              onToggle={toggle}
              onOverride={(id, patch) => {
                setOverrides((current) => ({ ...current, [id]: patch }));
                setApplyErrors((current) => {
                  if (!current[id]) {
                    return current;
                  }
                  const next = { ...current };
                  delete next[id];
                  return next;
                });
              }}
            />
          </section>
        );
      })}
      <OrganizationEnrichmentSettings />
    </AdminInputCard>
  );
}

export type { EnrichmentProposal };
