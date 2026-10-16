'use client';

import { useQuery } from '@tanstack/react-query';
import { useQueryState } from 'nuqs';
import { useEffect, useRef, useState } from 'react';

import { useBulkRowSelection } from '../../../hooks/use-bulk-row-selection';
import { useExpandedRecord } from '../../../hooks/use-expanded-record';
import { usePaginatedList } from '../../../hooks/use-paginated-list';
import { adminTabLabel, formatAdminPageName } from '../../../lib/admin-page-name';
import { getAdminQueryClient } from '../../../lib/admin-query-client';
import { adminQueryKeys } from '../../../lib/admin-query-keys';
import { ApiError } from '../../../lib/api-client';
import {
  decideTranslationFix,
  decideTranslationFixesBulk,
  getTranslationFix,
  getTranslationFixSettings,
  getTranslationFixSummary,
  listTranslationFixes,
  scanTranslationFixes,
  updateTranslationFixSettings,
  type TranslationFixProposal,
  type TranslationFixSettings,
} from '../../../lib/api-client-data-quality';
import { StatusBanner } from '../../status-banner';
import {
  AdminDataTableCell,
  AdminDataTableCellMeta,
  AdminDataTableHeadCell,
} from '../../ui/admin-data-table';
import {
  adminTableText,
  AdminTableName,
  formatAdminTableLabel,
} from '../../ui/admin-table-value';
import { AdminEditorPanel } from '../../ui/admin-editor-panel';
import { AdminField, AdminFieldGrid } from '../../ui/admin-field-grid';
import { AdminKpiCard } from '../../ui/admin-kpi-card';
import { AdminFilterBar, AdminFilterField } from '../../ui/admin-filter-bar';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { ResourceTableShell } from '../../ui/resource-table-shell';
import { Select } from '../../ui/select';
import { Textarea } from '../../ui/textarea';
import {
  ModelBudgetCard,
  ReviewQueueScopeNote,
  SWEEP_TIMEOUT_MESSAGE,
  sweepLimitNote,
} from './sweep-shared';

const PAGE_NAME = formatAdminPageName('Data quality', adminTabLabel.translations);

const LANGUAGES = [
  ['en', 'English'],
  ['zh', 'Chinese'],
  ['zh-HK', 'Hong Kong'],
] as const;

interface TranslationFilters {
  q: string;
  entity_type: string;
  field: string;
  status: string;
}

const DEFAULT_FILTERS: TranslationFilters = {
  q: '',
  entity_type: '',
  field: '',
  status: 'pending',
};

function fieldLabel(field: string): string {
  if (field === 'name') {
    return 'Name';
  }
  if (field === 'description') {
    return 'Description';
  }
  return formatAdminTableLabel(field);
}

export function TranslationsPanel() {
  const [organization, setOrganization] = useQueryState('organization');
  const orgIdRef = useRef(organization);
  orgIdRef.current = organization;
  const sweepRunId = useRef<string | null>(null);
  const sweepNoticeDone = useRef(false);
  const expanded = useExpandedRecord({ paramName: 'translation-fix' });
  const summaryQuery = useQuery({
    queryKey: [...adminQueryKeys.translationFixes(), 'summary'],
    queryFn: getTranslationFixSummary,
    refetchInterval: (query) => {
      const status = query.state.data?.active_run?.status;
      return status === 'queued' || status === 'running' ? 3000 : false;
    },
  });
  const settingsQuery = useQuery({
    queryKey: [...adminQueryKeys.translationFixes(), 'settings'],
    queryFn: getTranslationFixSettings,
  });
  const [draftLimit, setDraftLimit] = useState<string | null>(null);
  const settings = settingsQuery.data ?? null;
  const limitValue =
    draftLimit ?? (settings ? String(settings.monthly_cost_limit_usd) : '');
  const activeRun = summaryQuery.data?.active_run ?? null;
  const latestRun = summaryQuery.data?.latest_run ?? null;
  const sweepActive =
    activeRun?.status === 'queued' || activeRun?.status === 'running';
  const list = usePaginatedList<TranslationFixProposal, TranslationFilters>({
    queryKey: [...adminQueryKeys.translationFixes(), organization ?? ''],
    defaultFilters: DEFAULT_FILTERS,
    debounceKeys: ['q'],
    errorPrefix: 'Failed to load translation fixes',
    refetchInterval: sweepActive ? 3000 : false,
    fetcher: async ({ cursor, limit, q, entity_type, field, status }) => {
      const page = await listTranslationFixes({
        cursor: cursor ?? undefined,
        limit,
        q: q || undefined,
        entity_type: entity_type || undefined,
        field: field || undefined,
        status: status || undefined,
        org_id: orgIdRef.current || undefined,
      });
      return { items: page.items, nextCursor: page.next_cursor ?? null };
    },
  });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [scanningScope, setScanningScope] = useState<'pending_review' | 'all' | null>(
    null
  );
  const [activeId, setActiveId] = useState<string | null>(null);
  const [draftText, setDraftText] = useState<Record<string, string>>({});
  const selection = useBulkRowSelection(list.items, list.hasMore);
  const {
    selected,
    selectScope,
    selectAllRef,
    headerChecked,
    headerLabel,
    cycleHeader,
    toggleRow,
    resetSelection,
  } = selection;
  const sweepBusy = scanningScope !== null || sweepActive;

  useEffect(() => {
    resetSelection();
  }, [
    list.filters.q,
    list.filters.entity_type,
    list.filters.field,
    list.filters.status,
    organization,
    resetSelection,
  ]);

  const listed = list.items.find((item) => item.id === expanded.expandedId) ?? null;
  const detailQuery = useQuery({
    queryKey: [...adminQueryKeys.translationFixes(), 'one', expanded.expandedId],
    queryFn: () => getTranslationFix(expanded.expandedId as string),
    enabled: Boolean(expanded.expandedId) && !list.isLoading && listed === null,
  });
  const open = listed ?? detailQuery.data ?? null;
  const openId = open?.id ?? '';
  const openMissing = (open?.missing_languages ?? []).join(',');
  const openProposed = JSON.stringify(open?.proposed_text ?? {});
  useEffect(() => {
    if (!openId) {
      return;
    }
    const proposed = open?.proposed_text ?? {};
    const next: Record<string, string> = {};
    for (const code of open?.missing_languages ?? []) {
      next[code] = proposed[code] ?? '';
    }
    setDraftText(next);
  }, [openId, openMissing, openProposed, open]);

  const pending = summaryQuery.data?.by_status.pending ?? 0;
  const sweepProgress =
    activeRun && sweepActive
      ? `${activeRun.batches_done} of ${activeRun.batches_total}`
      : null;

  useEffect(() => {
    if (sweepNoticeDone.current) {
      return;
    }
    const started = sweepRunId.current;
    if (!started || !latestRun || latestRun.scan_run_id !== started) {
      return;
    }
    if (latestRun.status !== 'done' && latestRun.status !== 'failed') {
      return;
    }
    sweepNoticeDone.current = true;
    setNotice((current) => {
      const sweepNotice =
        current.startsWith('Cleared ') || current.includes('queued ');
      if (!sweepNotice) {
        return current;
      }
      const warning = latestRun.error ? ` ${latestRun.error}` : '';
      return `Created ${latestRun.created}, updated ${latestRun.updated}, skipped ${latestRun.skipped}, cleared ${latestRun.cleared}.${warning}`;
    });
  }, [latestRun, notice]);

  async function refresh() {
    await getAdminQueryClient().invalidateQueries({
      queryKey: [...adminQueryKeys.translationFixes(), 'summary'],
    });
    await list.refetch();
  }

  async function sweep(reviewScope: 'pending_review' | 'all') {
    setScanningScope(reviewScope);
    setError('');
    setNotice('');
    try {
      const result = await scanTranslationFixes({
        entity_type: list.filters.entity_type || undefined,
        q: list.filters.q || undefined,
        org_id: organization || undefined,
        review_scope: reviewScope,
      });
      const scanned =
        result.total_entities == null ? '' : ` Scanned ${result.total_entities} entities.`;
      const warning = result.error ? ` ${result.error}` : '';
      sweepRunId.current = result.scan_run_id;
      sweepNoticeDone.current = false;
      setNotice(
        `Cleared ${result.cleared}, skipped ${result.skipped}, queued ${result.queued_for_model}.${scanned}${sweepLimitNote(result.truncated)}${warning}`
      );
      await refresh();
    } catch (err) {
      if (err instanceof ApiError && err.status === 504) {
        setError(SWEEP_TIMEOUT_MESSAGE);
        await refresh();
      } else {
        setError(err instanceof ApiError ? err.message : 'Scan failed.');
      }
    } finally {
      setScanningScope(null);
    }
  }

  async function decide(item: TranslationFixProposal, action: 'apply' | 'dismiss') {
    setActiveId(item.id);
    setError('');
    try {
      await decideTranslationFix(item.id, {
        action,
        ...(action === 'apply' ? { translations: draftText } : {}),
      });
      setNotice(action === 'apply' ? 'Translation updated.' : 'Proposal dismissed.');
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not update the translation.');
    } finally {
      setActiveId(null);
    }
  }

  async function bulk(action: 'apply' | 'dismiss') {
    if (selectScope !== 'all' && selected.size === 0) {
      setError('Select at least one translation.');
      return;
    }
    setError('');
    try {
      const result = await decideTranslationFixesBulk(
        selectScope === 'all'
          ? {
              action,
              entity_type: list.filters.entity_type || undefined,
              field: list.filters.field || undefined,
              q: list.filters.q || undefined,
              org_id: organization || undefined,
            }
          : { action, ids: Array.from(selected) }
      );
      setNotice(`Updated ${result.decided}. ${result.failed} failed.`);
      resetSelection();
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Bulk update failed.');
    }
  }

  async function saveSettings() {
    const monthly = Number(limitValue);
    if (!Number.isFinite(monthly)) {
      setError('Enter a monthly limit.');
      return;
    }
    setError('');
    try {
      const saved = await updateTranslationFixSettings({
        monthly_cost_limit_usd: monthly,
      });
      getAdminQueryClient().setQueryData<TranslationFixSettings>(
        [...adminQueryKeys.translationFixes(), 'settings'],
        saved
      );
      setDraftLimit(null);
      setNotice('Translation budget saved.');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save the budget.');
    }
  }

  return (
    <div className='space-y-4'>
      <h2 className='sr-only'>{PAGE_NAME}</h2>
      {organization ? (
        <ReviewQueueScopeNote
          onClear={() => {
            void setOrganization(null);
          }}
        />
      ) : null}
      {notice ? (
        <StatusBanner kind='info' title='Translations'>
          {notice}
        </StatusBanner>
      ) : null}
      {error ? <StatusBanner kind='error'>{error}</StatusBanner> : null}
      {selectScope === 'all' ? (
        <StatusBanner kind='info' title='Selection'>
          All matching records are selected, including rows not on this page.
        </StatusBanner>
      ) : null}
      <div className='grid gap-3 sm:grid-cols-3'>
        <AdminKpiCard label='Pending' value={pending} />
        {sweepProgress ? <AdminKpiCard label='Sweep' value={sweepProgress} /> : null}
      </div>
      <ResourceTableShell
        ariaLabel={PAGE_NAME}
        actions={
          <>
            <Button
              type='button'
              onClick={() => void sweep('pending_review')}
              loading={scanningScope === 'pending_review'}
              loadingLabel='Scanning…'
              disabled={sweepBusy}
            >
              Sweep pending
            </Button>
            <Button
              type='button'
              onClick={() => void sweep('all')}
              loading={scanningScope === 'all'}
              loadingLabel='Scanning…'
              disabled={sweepBusy}
            >
              Sweep all orgs
            </Button>
            <Button
              type='button'
              variant='secondary'
              onClick={() => void bulk('apply')}
              disabled={selectScope !== 'all' && selected.size === 0}
            >
              Apply selected
            </Button>
            <Button
              type='button'
              variant='secondary'
              onClick={() => void bulk('dismiss')}
              disabled={selectScope !== 'all' && selected.size === 0}
            >
              Dismiss selected
            </Button>
          </>
        }
        rows={list.items}
        getLabel={(item) => item.entity_name || item.current_label}
        middleColumnCount={4}
        hasActions={false}
        isExpanded={expanded.isExpanded}
        onToggle={expanded.toggle}
        detail={
          open && open.status === 'pending' ? (
            <AdminEditorPanel>
              {open.rationale ? (
                <p className='text-sm text-slate-700'>{open.rationale}</p>
              ) : null}
              {LANGUAGES.filter((entry) => open.source_text?.[entry[0]]).map(
                ([code, label]) => (
                  <p key={code} className='text-sm text-slate-700'>
                    {label}: {open.source_text?.[code]}
                  </p>
                )
              )}
              <AdminFieldGrid columns={1}>
                {(open.missing_languages ?? []).map((code) => {
                  const label =
                    LANGUAGES.find((entry) => entry[0] === code)?.[1] ?? code;
                  const long = open.field === 'description';
                  return (
                    <AdminField
                      key={code}
                      label={label}
                      htmlFor={`translation-fix-${code}`}
                    >
                      {long ? (
                        <Textarea
                          id={`translation-fix-${code}`}
                          rows={4}
                          value={draftText[code] ?? ''}
                          onChange={(event) =>
                            setDraftText((current) => ({
                              ...current,
                              [code]: event.target.value,
                            }))
                          }
                        />
                      ) : (
                        <Input
                          id={`translation-fix-${code}`}
                          value={draftText[code] ?? ''}
                          onChange={(event) =>
                            setDraftText((current) => ({
                              ...current,
                              [code]: event.target.value,
                            }))
                          }
                        />
                      )}
                    </AdminField>
                  );
                })}
              </AdminFieldGrid>
              <div className='flex gap-2'>
                <Button
                  type='button'
                  onClick={() => void decide(open, 'apply')}
                  loading={activeId === open.id}
                  loadingLabel='Saving…'
                >
                  Apply
                </Button>
                <Button
                  type='button'
                  variant='secondary'
                  onClick={() => void decide(open, 'dismiss')}
                >
                  Dismiss
                </Button>
              </div>
            </AdminEditorPanel>
          ) : null
        }
        isLoading={list.isLoading}
        isLoadingMore={list.isLoadingMore}
        hasMore={list.hasMore}
        onLoadMore={() => void list.loadMore()}
        error={list.error}
        emptyLabel='No translations match these filters. Sweep pending or Sweep all orgs to find some.'
        filters={
          <AdminFilterBar>
            <AdminFilterField>
              <Input
                id='translation-fix-q'
                aria-label='Name'
                value={list.filters.q}
                placeholder='Name'
                onChange={(event) => list.setFilter('q', event.target.value)}
              />
            </AdminFilterField>
            <AdminFilterField>
              <Select
                id='translation-fix-entity'
                aria-label='Record'
                value={list.filters.entity_type}
                onChange={(event) => list.setFilter('entity_type', event.target.value)}
              >
                <option value=''>Any record</option>
                <option value='organization'>Organizations</option>
                <option value='activity'>Activities</option>
              </Select>
            </AdminFilterField>
            <AdminFilterField>
              <Select
                id='translation-fix-field'
                aria-label='Field'
                value={list.filters.field}
                onChange={(event) => list.setFilter('field', event.target.value)}
              >
                <option value=''>Any field</option>
                <option value='name'>Name</option>
                <option value='description'>Description</option>
              </Select>
            </AdminFilterField>
            <AdminFilterField>
              <Select
                id='translation-fix-status'
                aria-label='Status'
                value={list.filters.status}
                onChange={(event) => list.setFilter('status', event.target.value)}
              >
                <option value='pending'>Pending</option>
                <option value='applied'>Applied</option>
                <option value='dismissed'>Dismissed</option>
              </Select>
            </AdminFilterField>
          </AdminFilterBar>
        }
        leadingHead={
          <input
            ref={selectAllRef}
            type='checkbox'
            aria-label={headerLabel}
            checked={headerChecked}
            onChange={cycleHeader}
          />
        }
        renderLeading={(item) => (
          <input
            type='checkbox'
            aria-label='Select row'
            checked={selectScope === 'all' || selected.has(item.id)}
            onClick={(event) => event.stopPropagation()}
            onChange={(event) => {
              toggleRow(item.id, event.target.checked);
            }}
          />
        )}
        head={
          <>
            <AdminDataTableHeadCell>Record</AdminDataTableHeadCell>
            <AdminDataTableHeadCell>Field</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>Missing</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>Proposed</AdminDataTableHeadCell>
          </>
        }
        renderCells={(item) => (
          <>
            <AdminDataTableCell>
              <AdminTableName>
                {item.entity_name || formatAdminTableLabel(item.entity_type)}
              </AdminTableName>
              <AdminDataTableCellMeta until='secondary' label='Missing'>
                {adminTableText(item.missing_label)}
              </AdminDataTableCellMeta>
              <AdminDataTableCellMeta until='secondary' label='Proposed'>
                {adminTableText(item.proposed_label)}
              </AdminDataTableCellMeta>
            </AdminDataTableCell>
            <AdminDataTableCell>{fieldLabel(item.field)}</AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {adminTableText(item.missing_label)}
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {adminTableText(item.proposed_label)}
            </AdminDataTableCell>
          </>
        )}
      />
      {settings ? (
        <ModelBudgetCard
          monthCost={summaryQuery.data?.month_cost_usd ?? 0}
          limit={settings.monthly_cost_limit_usd}
          value={limitValue}
          onChange={setDraftLimit}
          onSave={() => void saveSettings()}
          inputId='translation-fix-budget'
          description='Uses the category-check model. Category checks and location sweeps are not counted.'
        />
      ) : null}
    </div>
  );
}
