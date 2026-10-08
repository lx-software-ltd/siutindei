'use client';

import { useQuery } from '@tanstack/react-query';
import { useQueryState } from 'nuqs';
import { useRef, useState } from 'react';

import { useExpandedRecord } from '../../../hooks/use-expanded-record';
import { usePaginatedList } from '../../../hooks/use-paginated-list';
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
import { AdminDataTableCell, AdminDataTableHeadCell } from '../../ui/admin-data-table';
import { AdminEditorPanel } from '../../ui/admin-editor-panel';
import { AdminField, AdminFieldGrid } from '../../ui/admin-field-grid';
import { AdminFilterBar, AdminFilterField } from '../../ui/admin-filter-bar';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { ResourceTableShell } from '../../ui/resource-table-shell';
import { Select } from '../../ui/select';
import { Textarea } from '../../ui/textarea';

function splitNameSettingList(value: string): string[] {
  return value.split(/\s+/).filter(Boolean);
}

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
  q: string;
  entity_type: string;
  rule: string;
  status: string;
}

const DEFAULT_FILTERS: NameFilters = {
  q: '',
  entity_type: '',
  rule: '',
  status: 'pending',
};

export function NamesPanel() {
  const [organization, setOrganization] = useQueryState('organization');
  const orgIdRef = useRef(organization);
  orgIdRef.current = organization;
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
    queryKey: [...adminQueryKeys.nameFixes(), organization ?? ''],
    defaultFilters: DEFAULT_FILTERS,
    debounceKeys: ['q'],
    errorPrefix: 'Failed to load name fixes',
    fetcher: async ({ cursor, limit, q, entity_type, rule, status }) => {
      const page = await listNameFixes({
        cursor: cursor ?? undefined,
        limit,
        q: q || undefined,
        entity_type: entity_type || undefined,
        rule: rule || undefined,
        status: status || undefined,
        org_id: orgIdRef.current || undefined,
      });
      return { items: page.items, nextCursor: page.next_cursor ?? null };
    },
  });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [isScanning, setIsScanning] = useState(false);
  const [sweepScope, setSweepScope] = useState<'pending_review' | 'all'>(
    'pending_review'
  );
  const [activeId, setActiveId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const listed = list.items.find((item) => item.id === expanded.expandedId) ?? null;
  const detailQuery = useQuery({
    queryKey: [...adminQueryKeys.nameFixes(), 'one', expanded.expandedId],
    queryFn: () => getNameFix(expanded.expandedId as string),
    enabled: Boolean(expanded.expandedId) && !list.isLoading && listed === null,
  });
  const open = listed ?? detailQuery.data ?? null;
  const pending = summaryQuery.data?.by_status.pending ?? 0;
  const summary = summaryQuery.data ? `${pending} pending` : 'No pending names.';

  async function sweep() {
    setIsScanning(true);
    setError('');
    setNotice('');
    try {
      const result = await scanNameFixes({
        entity_type: list.filters.entity_type || undefined,
        review_scope: sweepScope,
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
      setIsScanning(false);
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
    const ids = Array.from(selected);
    if (ids.length === 0) {
      setError('Select at least one name.');
      return;
    }
    setError('');
    try {
      const result = await decideNameFixesBulk({ action, ids });
      setNotice(`Updated ${result.decided}. ${result.failed} failed.`);
      setSelected(new Set());
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
      <h2 className='sr-only'>Names</h2>
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
        <StatusBanner variant='info' kind='info'>
          {notice}
        </StatusBanner>
      ) : null}
      {error ? (
        <StatusBanner variant='error' kind='error'>
          {error}
        </StatusBanner>
      ) : null}
      <ResourceTableShell
        ariaLabel='Name fixes'
        toolbar={
          <div className='mb-3 flex flex-wrap items-end gap-2'>
            <p className='w-full text-sm text-slate-700'>{summary}</p>
            <AdminFilterField label='Sweep' htmlFor='name-fix-scope'>
              <Select
                id='name-fix-scope'
                value={sweepScope}
                onChange={(event) =>
                  setSweepScope(event.target.value === 'all' ? 'all' : 'pending_review')
                }
              >
                <option value='pending_review'>Pending review</option>
                <option value='all'>All organizations</option>
              </Select>
            </AdminFilterField>
            <Button
              type='button'
              onClick={() => void sweep()}
              loading={isScanning}
              loadingLabel='Scanning…'
            >
              Sweep scan
            </Button>
            <Button type='button' variant='secondary' onClick={() => void bulk('apply')} disabled={selected.size === 0}>
              Apply selected
            </Button>
            <Button type='button' variant='secondary' onClick={() => void bulk('dismiss')} disabled={selected.size === 0}>
              Dismiss selected
            </Button>
          </div>
        }
        rows={list.items}
        getLabel={(item) => item.current_value}
        middleColumnCount={4}
        hasActions={false}
        isExpanded={expanded.isExpanded}
        onToggle={expanded.toggle}
        detail={
          open && open.status === 'pending' ? (
            <AdminEditorPanel>
              <p className='text-sm text-slate-700'>
                {open.current_value} becomes {open.proposed_value}
              </p>
              <div className='flex gap-2'>
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
              </div>
            </AdminEditorPanel>
          ) : null
        }
        isLoading={list.isLoading}
        isLoadingMore={list.isLoadingMore}
        hasMore={list.hasMore}
        onLoadMore={() => void list.loadMore()}
        error={list.error}
        emptyLabel='No names match these filters. Sweep scan to find some.'
        filters={
          <AdminFilterBar>
            <AdminFilterField label='Name' htmlFor='name-fix-q'>
              <Input
                id='name-fix-q'
                value={list.filters.q}
                onChange={(event) => list.setFilter('q', event.target.value)}
              />
            </AdminFilterField>
            <AdminFilterField label='Record' htmlFor='name-fix-entity'>
              <Select
                id='name-fix-entity'
                value={list.filters.entity_type}
                onChange={(event) => list.setFilter('entity_type', event.target.value)}
              >
                <option value=''>Organizations and activities</option>
                <option value='organization'>Organizations</option>
                <option value='activity'>Activities</option>
              </Select>
            </AdminFilterField>
            <AdminFilterField label='Status' htmlFor='name-fix-status'>
              <Select
                id='name-fix-status'
                value={list.filters.status}
                onChange={(event) => list.setFilter('status', event.target.value)}
              >
                <option value='pending'>Pending</option>
                <option value='applied'>Applied</option>
                <option value='dismissed'>Dismissed</option>
              </Select>
            </AdminFilterField>
            <AdminFilterField label='Rule' htmlFor='name-fix-rule'>
              <Select
                id='name-fix-rule'
                value={list.filters.rule}
                onChange={(event) => list.setFilter('rule', event.target.value)}
              >
                <option value=''>All rules</option>
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
            type='checkbox'
            aria-label='Select all rows'
            checked={list.items.length > 0 && list.items.every((item) => selected.has(item.id))}
            onChange={(event) => {
              const checked = event.target.checked;
              setSelected((current) => {
                const next = new Set(current);
                for (const item of list.items) {
                  if (checked) {
                    next.add(item.id);
                  } else {
                    next.delete(item.id);
                  }
                }
                return next;
              });
            }}
          />
        }
        renderLeading={(item) => (
          <input
            type='checkbox'
            aria-label='Select row'
            checked={selected.has(item.id)}
            onClick={(event) => event.stopPropagation()}
            onChange={(event) => {
              setSelected((current) => {
                const next = new Set(current);
                if (event.target.checked) {
                  next.add(item.id);
                } else {
                  next.delete(item.id);
                }
                return next;
              });
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
            <AdminDataTableCell>{item.current_value}</AdminDataTableCell>
            <AdminDataTableCell>{item.proposed_value}</AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>{item.entity_type}</AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>{item.rules.join(', ')}</AdminDataTableCell>
          </>
        )}
      />
      {settings ? (
        <div className='space-y-3 rounded-lg border border-slate-200 bg-white p-4'>
          <h3 className='text-sm font-medium text-slate-900'>Rules</h3>
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
          <Button type='button' variant='secondary' onClick={() => void saveSettings()}>
            Save rules
          </Button>
        </div>
      ) : null}
    </div>
  );
}
