'use client';

import { useQuery } from '@tanstack/react-query';
import { useQueryState } from 'nuqs';
import { useEffect, useState } from 'react';

import { useBulkRowSelection } from '../../../hooks/use-bulk-row-selection';
import { useExpandedRecord } from '../../../hooks/use-expanded-record';
import { usePaginatedList } from '../../../hooks/use-paginated-list';
import { adminTabLabel, formatAdminPageName } from '../../../lib/admin-page-name';
import { getAdminQueryClient } from '../../../lib/admin-query-client';
import { adminQueryKeys } from '../../../lib/admin-query-keys';
import { ApiError } from '../../../lib/api-client';
import {
  decideNameFix,
  decideNameFixesBulk,
  getNameFix,
  getNameFixSettings,
  getNameFixSummary,
  listNameFixes,
  scanNameFixes,
  updateNameFixSettings,
  type NameFixProposal,
  type NameFixSettings,
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
  formatAdminTableLabels,
} from '../../ui/admin-table-value';
import { AdminEditorPanel } from '../../ui/admin-editor-panel';
import { AdminField, AdminFieldGrid } from '../../ui/admin-field-grid';
import { AdminInputCard } from '../../ui/admin-input-card';
import { AdminKpiCard } from '../../ui/admin-kpi-card';
import { AdminFilterBar, AdminFilterField } from '../../ui/admin-filter-bar';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { ResourceTableShell } from '../../ui/resource-table-shell';
import { Select } from '../../ui/select';
import { Textarea } from '../../ui/textarea';

function splitNameSettingList(value: string): string[] {
  return value.split(/\s+/).filter(Boolean);
}

const PAGE_NAME = formatAdminPageName('Data quality', adminTabLabel.names);

const NAME_RULES = [
  'html_entities',
  'nfkc',
  'whitespace',
  'trailing_punctuation',
  'cjk_spacing',
  'title_case',
  'brackets',
  'split_bilingual',
] as const;

interface NameFilters {
  entity_type: string;
  rule: string;
  status: string;
}

const DEFAULT_FILTERS: NameFilters = {
  entity_type: '',
  rule: '',
  status: 'pending',
};

export function NamesPanel() {
  const [organization, setOrganization] = useQueryState('organization');
  const [runId, setRun] = useQueryState('run');
  const expanded = useExpandedRecord({ paramName: 'name-fix' });
  const summaryQuery = useQuery({
    queryKey: [...adminQueryKeys.nameFixes(), 'summary'],
    queryFn: getNameFixSummary,
  });
  const settingsQuery = useQuery({
    queryKey: [...adminQueryKeys.nameFixes(), 'settings'],
    queryFn: getNameFixSettings,
  });
  const [draft, setDraft] = useState<NameFixSettings | null>(null);
  const [exceptionText, setExceptionText] = useState<string | null>(null);
  const [suffixText, setSuffixText] = useState<string | null>(null);
  const settings = draft ?? settingsQuery.data ?? null;
  const exceptionValue = exceptionText ?? settings?.exception_words.join(' ') ?? '';
  const suffixValue = suffixText ?? settings?.bracket_suffixes.join(' ') ?? '';
  const list = usePaginatedList<NameFixProposal, NameFilters>({
    queryKey: [...adminQueryKeys.nameFixes(), organization ?? '', runId ?? ''],
    defaultFilters: DEFAULT_FILTERS,
    errorPrefix: 'Failed to load name fixes',
    fetcher: async ({ cursor, limit, entity_type, rule, status }) => {
      const page = await listNameFixes({
        cursor: cursor ?? undefined,
        limit,
        entity_type: entity_type || undefined,
        rule: rule || undefined,
        status: runId ? undefined : status || undefined,
        org_id: organization || undefined,
        run: runId || undefined,
      });
      return { items: page.items, nextCursor: page.next_cursor ?? null };
    },
  });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [scanningScope, setScanningScope] = useState<
    'pending_review' | 'all' | null
  >(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const {
    selected,
    selectScope,
    selectAllRef,
    headerChecked,
    headerLabel,
    cycleHeader,
    toggleRow,
    resetSelection,
  } = useBulkRowSelection(list.items, list.hasMore);

  useEffect(() => {
    resetSelection();
  }, [
    list.filters.entity_type,
    list.filters.rule,
    list.filters.status,
    organization,
    resetSelection,
  ]);

  const listed = list.items.find((item) => item.id === expanded.expandedId) ?? null;
  const detailQuery = useQuery({
    queryKey: [...adminQueryKeys.nameFixes(), 'one', expanded.expandedId],
    queryFn: () => getNameFix(expanded.expandedId as string),
    enabled: Boolean(expanded.expandedId) && !list.isLoading && listed === null,
  });
  const open = listed ?? detailQuery.data ?? null;
  const pending = summaryQuery.data?.by_status.pending ?? 0;

  async function sweep(reviewScope: 'pending_review' | 'all') {
    setScanningScope(reviewScope);
    setError('');
    setNotice('');
    try {
      const result = await scanNameFixes({
        entity_type: list.filters.entity_type || undefined,
        review_scope: reviewScope,
      });
      const stopped = result.truncated
        ? ' Scan stopped at the limit; run it again to continue.'
        : '';
      setNotice(
        `Created ${result.created}, updated ${result.updated}, skipped ${result.skipped}, cleared ${result.cleared ?? 0}.${stopped}`
      );
      await getAdminQueryClient().invalidateQueries({
        queryKey: [...adminQueryKeys.nameFixes(), 'summary'],
      });
      await list.refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Scan failed.');
    } finally {
      setScanningScope(null);
    }
  }

  async function decide(id: string, action: 'apply' | 'dismiss') {
    setActiveId(id);
    setError('');
    try {
      await decideNameFix(id, { action });
      setNotice(action === 'apply' ? 'Name updated.' : 'Proposal dismissed.');
      await getAdminQueryClient().invalidateQueries({
        queryKey: [...adminQueryKeys.nameFixes(), 'summary'],
      });
      await list.refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not update the name.');
    } finally {
      setActiveId(null);
    }
  }

  async function bulk(action: 'apply' | 'dismiss') {
    if (selectScope !== 'all' && selected.size === 0) {
      setError('Select at least one name.');
      return;
    }
    setError('');
    try {
      const result = await decideNameFixesBulk(
        selectScope === 'all'
          ? {
              action,
              entity_type: list.filters.entity_type || undefined,
              rule: list.filters.rule || undefined,
              org_id: organization || undefined,
            }
          : { action, ids: Array.from(selected) }
      );
      setNotice(`Updated ${result.decided}. ${result.failed} failed.`);
      resetSelection();
      await getAdminQueryClient().invalidateQueries({
        queryKey: [...adminQueryKeys.nameFixes(), 'summary'],
      });
      await list.refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Bulk update failed.');
    }
  }

  async function saveSettings() {
    if (!settings) {
      return;
    }
    setError('');
    try {
      const saved = await updateNameFixSettings({
        ...settings,
        exception_words: splitNameSettingList(exceptionValue),
        bracket_suffixes: splitNameSettingList(suffixValue),
      });
      getAdminQueryClient().setQueryData([...adminQueryKeys.nameFixes(), 'settings'], saved);
      setDraft(null);
      setExceptionText(null);
      setSuffixText(null);
      setNotice('Name rules saved.');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save rules.');
    }
  }

  return (
    <div className='space-y-4'>
      <h2 className='sr-only'>{PAGE_NAME}</h2>
      {runId ? (
        <p className='text-sm text-slate-600'>
          Names from this run, including changes the import already applied.{' '}
          <button
            type='button'
            className='underline underline-offset-2'
            onClick={() => {
              void setRun(null);
            }}
          >
            Show all
          </button>
        </p>
      ) : null}
      {organization ? (
        <p className='text-sm text-slate-600'>
          Filtered to the organization from the review queue.{' '}
          <button
            type='button'
            className='underline'
            onClick={() => {
              void setOrganization(null);
            }}
          >
            Show all
          </button>
        </p>
      ) : null}
      {notice ? (
        <StatusBanner kind='info' title='Names'>
          {notice}
        </StatusBanner>
      ) : null}
      {error ? (
        <StatusBanner kind='error'>
          {error}
        </StatusBanner>
      ) : null}
      {selectScope === 'all' ? (
        <StatusBanner kind='info' title='Selection'>
          All matching records are selected, including rows not on this page.
        </StatusBanner>
      ) : null}
      <div className='grid gap-3 sm:grid-cols-3'>
        <AdminKpiCard label='Pending' value={pending} />
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
              disabled={scanningScope !== null}
            >
              Sweep pending
            </Button>
            <Button
              type='button'
              onClick={() => void sweep('all')}
              loading={scanningScope === 'all'}
              loadingLabel='Scanning…'
              disabled={scanningScope !== null}
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
        getLabel={(item) => item.current_value}
        middleColumnCount={4}
        hasActions={false}
        isExpanded={expanded.isExpanded}
        onToggle={expanded.toggle}
        detail={
          open && open.status === 'pending' ? (
            <AdminEditorPanel
              actions={
                <>
                  <Button
                    type='button'
                    onClick={() => void decide(open.id, 'apply')}
                    loading={activeId === open.id}
                    loadingLabel='Saving…'
                  >
                    Apply
                  </Button>
                  <Button
                    type='button'
                    variant='secondary'
                    onClick={() => void decide(open.id, 'dismiss')}
                  >
                    Dismiss
                  </Button>
                </>
              }
            >
              <p className='text-sm text-slate-700'>
                {open.current_value} becomes {open.proposed_value}
              </p>
            </AdminEditorPanel>
          ) : null
        }
        isLoading={list.isLoading}
        isLoadingMore={list.isLoadingMore}
        hasMore={list.hasMore}
        onLoadMore={() => void list.loadMore()}
        error={list.error}
        emptyLabel='No names match these filters. Sweep pending or Sweep all orgs to find some.'
        filters={
          <AdminFilterBar>
            <AdminFilterField>
              <Select
                id='name-fix-entity'
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
                id='name-fix-status'
                aria-label='Status'
                value={list.filters.status}
                onChange={(event) => list.setFilter('status', event.target.value)}
              >
                <option value='pending'>Pending</option>
                <option value='applied'>Applied</option>
                <option value='dismissed'>Dismissed</option>
              </Select>
            </AdminFilterField>
            <AdminFilterField>
              <Select
                id='name-fix-rule'
                aria-label='Rule'
                value={list.filters.rule}
                onChange={(event) => list.setFilter('rule', event.target.value)}
              >
                <option value=''>Any rule</option>
                {(settings?.available_rules ?? NAME_RULES).map((rule) => (
                  <option key={rule} value={rule}>
                    {rule}
                  </option>
                ))}
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
            <AdminDataTableHeadCell>Current</AdminDataTableHeadCell>
            <AdminDataTableHeadCell>Proposed</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>Record</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>Rules</AdminDataTableHeadCell>
          </>
        }
        renderCells={(item) => (
          <>
            <AdminDataTableCell>
              <AdminTableName>{item.current_value}</AdminTableName>
              <AdminDataTableCellMeta until='secondary' label='Record'>
                {formatAdminTableLabel(item.entity_type)}
              </AdminDataTableCellMeta>
              <AdminDataTableCellMeta until='tertiary' label='Rules'>
                {formatAdminTableLabels(item.rules)}
              </AdminDataTableCellMeta>
            </AdminDataTableCell>
            <AdminDataTableCell>{adminTableText(item.proposed_value)}</AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {formatAdminTableLabel(item.entity_type)}
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              {formatAdminTableLabels(item.rules)}
            </AdminDataTableCell>
          </>
        )}
      />
      {settings ? (
        <AdminInputCard
          title='Rules'
          titleLevel='h3'
          actions={
            <Button type='button' variant='secondary' onClick={() => void saveSettings()}>
              Save rules
            </Button>
          }
        >
          <div className='flex flex-wrap gap-3'>
            {(settings.available_rules ?? settings.enabled_rules).map((rule) => (
              <label key={rule} className='flex items-center gap-2 text-sm text-slate-700'>
                <input
                  type='checkbox'
                  checked={settings.enabled_rules.includes(rule)}
                  onChange={(event) => {
                    const enabled = event.target.checked
                      ? [...settings.enabled_rules, rule]
                      : settings.enabled_rules.filter((item) => item !== rule);
                    setDraft({ ...settings, enabled_rules: enabled });
                  }}
                />
                {rule}
              </label>
            ))}
          </div>
          <AdminFieldGrid columns={1}>
            <AdminField
              label='Words to leave in capitals'
              htmlFor='name-fix-exceptions'
              hint='Separate words with spaces or new lines.'
            >
              <Textarea
                id='name-fix-exceptions'
                rows={3}
                value={exceptionValue}
                onChange={(event) => setExceptionText(event.target.value)}
              />
            </AdminField>
            <AdminField
              label='Bracket suffixes to remove'
              htmlFor='name-fix-suffixes'
              hint='Separate suffixes with spaces.'
            >
              <Input
                id='name-fix-suffixes'
                value={suffixValue}
                onChange={(event) => setSuffixText(event.target.value)}
              />
            </AdminField>
          </AdminFieldGrid>
        </AdminInputCard>
      ) : null}
    </div>
  );
}
