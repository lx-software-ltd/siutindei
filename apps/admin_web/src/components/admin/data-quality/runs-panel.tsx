'use client';

import { useQuery } from '@tanstack/react-query';
import { useQueryState } from 'nuqs';
import { useState } from 'react';

import { adminTabLabel, formatAdminPageName } from '../../../lib/admin-page-name';
import { getAdminQueryClient } from '../../../lib/admin-query-client';
import { adminQueryKeys } from '../../../lib/admin-query-keys';
import { ApiError } from '../../../lib/api-client';
import {
  createDataQualityRun,
  listDataQualityRuns,
  retryDataQualityRun,
  type DataQualityRun,
  type DataQualityRunRequest,
} from '../../../lib/api-client-data-quality';
import { listImportJobs } from '../../../lib/api-client-org-review';
import type { OrganizationLookup } from '../../../lib/api-client-user';
import { formatDateTime } from '../../../lib/date-utils';
import { StatusBanner } from '../../status-banner';
import {
  AdminDataTableCell,
  AdminDataTableHeadCell,
} from '../../ui/admin-data-table';
import { AdminField, AdminFieldGrid } from '../../ui/admin-field-grid';
import { AdminInputCard } from '../../ui/admin-input-card';
import { AdminTableTime } from '../../ui/admin-table-value';
import { Button } from '../../ui/button';
import { OrganizationAutocomplete } from '../../ui/organization-autocomplete';
import { ResourceTableShell } from '../../ui/resource-table-shell';
import { Select } from '../../ui/select';

const PAGE_NAME = formatAdminPageName('Data quality', adminTabLabel.runs);
const TRIGGER_LABELS: Record<string, string> = {
  import: 'Import',
  manual: 'Manual',
  enrichment: 'Enrichment',
};

function triggerLabel(trigger: string): string {
  return TRIGGER_LABELS[trigger] ?? trigger;
}
const CHECKS = [
  ['names', adminTabLabel.names],
  ['duplicates', adminTabLabel.duplicates],
  ['locations', adminTabLabel.locations],
  ['categories', adminTabLabel.categories],
] as const;

type ScopeKind = DataQualityRunRequest['scope']['kind'];

const RECENT_IMPORT_COUNT = 20;

export function RunsPanel() {
  const [runParam, setRunParam] = useQueryState('run');
  const [, setSection] = useQueryState('section');
  const [, setTab] = useQueryState('tab');
  const runsQuery = useQuery({
    queryKey: adminQueryKeys.dataQualityRuns(),
    queryFn: listDataQualityRuns,
  });
  const [checks, setChecks] = useState<string[]>(['names', 'duplicates']);
  const [scopeKind, setScopeKind] = useState<ScopeKind>('pending_review');
  const [organization, setOrganization] = useState<OrganizationLookup | null>(null);
  const [importJobId, setImportJobId] = useState('');
  const importsQuery = useQuery({
    queryKey: [...adminQueryKeys.importJobs(), 'recent', RECENT_IMPORT_COUNT],
    queryFn: () => listImportJobs(undefined, RECENT_IMPORT_COUNT),
    enabled: scopeKind === 'import',
  });
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [retrying, setRetrying] = useState('');

  async function start() {
    setSaving(true);
    setError('');
    try {
      const created = await createDataQualityRun({
        checks,
        scope: {
          kind: scopeKind,
          org_id:
            scopeKind === 'organization' ? organization?.id : undefined,
          import_job_id: scopeKind === 'import' ? importJobId : undefined,
        },
      });
      await setRunParam(created.id);
      await getAdminQueryClient().invalidateQueries({
        queryKey: adminQueryKeys.dataQualityRuns(),
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Run failed.');
    } finally {
      setSaving(false);
    }
  }

  async function retry(id: string) {
    setRetrying(id);
    setError('');
    try {
      await retryDataQualityRun(id);
      await getAdminQueryClient().invalidateQueries({
        queryKey: adminQueryKeys.dataQualityRuns(),
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Retry failed.');
    } finally {
      setRetrying('');
    }
  }

  function openCheck(runId: string, tab: 'names' | 'duplicates') {
    void setSection('data-quality');
    void setTab(tab === 'duplicates' ? null : tab);
    void setRunParam(runId);
  }

  const items = runsQuery.data?.items ?? [];
  const recentImports = (importsQuery.data?.items ?? []).slice(0, RECENT_IMPORT_COUNT);
  const scopeReady =
    scopeKind === 'organization'
      ? Boolean(organization?.id)
      : scopeKind === 'import'
        ? Boolean(importJobId)
        : true;

  return (
    <div className='space-y-4'>
      <h2 className='sr-only'>{PAGE_NAME}</h2>
      {error ? <StatusBanner kind='error'>{error}</StatusBanner> : null}
      <AdminInputCard
        title='Run checks'
        titleLevel='h3'
        actions={
          <Button
            type='button'
            onClick={() => {
              void start();
            }}
            loading={saving}
            disabled={checks.length === 0 || !scopeReady}
          >
            Run checks
          </Button>
        }
      >
        <AdminFieldGrid columns={2}>
          <AdminField label='Checks' span='full'>
            <div className='space-y-2'>
              {CHECKS.map(([key, label]) => (
                <label key={key} className='flex items-center gap-2 text-sm text-ink-700'>
                  <input
                    type='checkbox'
                    checked={checks.includes(key)}
                    onChange={(event) => {
                      setChecks((current) =>
                        event.target.checked
                          ? [...current, key]
                          : current.filter((item) => item !== key)
                      );
                    }}
                  />
                  {label}
                </label>
              ))}
            </div>
          </AdminField>
          <AdminField label='Scope' htmlFor='data-quality-scope'>
            <Select
              id='data-quality-scope'
              value={scopeKind}
              onChange={(event) => setScopeKind(event.target.value as ScopeKind)}
            >
              <option value='pending_review'>Pending review</option>
              <option value='all'>All</option>
              <option value='organization'>One organization</option>
              <option value='import'>One import</option>
            </Select>
          </AdminField>
          {scopeKind === 'organization' ? (
            <AdminField label='Organization' htmlFor='data-quality-org'>
              <OrganizationAutocomplete
                id='data-quality-org'
                selected={organization}
                onSelect={setOrganization}
                placeholder='Organization name'
              />
            </AdminField>
          ) : null}
          {scopeKind === 'import' ? (
            <AdminField
              label='Import'
              htmlFor='data-quality-import'
              error={
                importsQuery.isError ? 'Could not load imports.' : undefined
              }
            >
              <Select
                id='data-quality-import'
                value={importJobId}
                disabled={importsQuery.isLoading}
                onChange={(event) => setImportJobId(event.target.value)}
              >
                <option value=''>
                  {importsQuery.isLoading ? 'Loading…' : 'Select an import'}
                </option>
                {recentImports.map((job) => (
                  <option key={job.id} value={job.id}>
                    {formatDateTime(job.created_at)}
                  </option>
                ))}
              </Select>
            </AdminField>
          ) : null}
        </AdminFieldGrid>
      </AdminInputCard>
      <ResourceTableShell
        ariaLabel={PAGE_NAME}
        rows={items}
        getLabel={(item) => `run ${item.id}`}
        middleColumnCount={3}
        isLoading={runsQuery.isLoading}
        error={
          runsQuery.isError
            ? runsQuery.error instanceof Error
              ? runsQuery.error.message
              : 'Failed to load runs'
            : ''
        }
        emptyLabel='No runs yet.'
        head={
          <>
            <AdminDataTableHeadCell>When</AdminDataTableHeadCell>
            <AdminDataTableHeadCell>Status</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>Trigger</AdminDataTableHeadCell>
          </>
        }
        renderCells={(item) => (
          <>
            <AdminDataTableCell>
              <AdminTableTime value={item.created_at} emphasis />
            </AdminDataTableCell>
            <AdminDataTableCell>{item.status}</AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>{triggerLabel(item.trigger)}</AdminDataTableCell>
          </>
        )}
        renderActions={(item) => (
          <div className='flex flex-wrap gap-2'>
            <Button type='button' variant='secondary' size='sm' onClick={() => openCheck(item.id, 'names')}>
              Names
            </Button>
            <Button
              type='button'
              variant='secondary'
              size='sm'
              onClick={() => openCheck(item.id, 'duplicates')}
            >
              Duplicates
            </Button>
            <Button
              type='button'
              variant='secondary'
              size='sm'
              loading={retrying === item.id}
              onClick={() => {
                void retry(item.id);
              }}
            >
              Run again
            </Button>
          </div>
        )}
        detail={
          runParam ? (
            <p className='text-sm text-ink-700'>Selected run {runParam}</p>
          ) : null
        }
        isExpanded={(id) => id === runParam}
        onToggle={(id) => {
          void setRunParam(id === runParam ? null : id);
        }}
      />
    </div>
  );
}

export function runStatusLabel(run: DataQualityRun) {
  const names = run.checks.map((check) => `${check.name} ${check.status}`).join(', ');
  return `${run.status}${names ? ` · ${names}` : ''}`;
}
