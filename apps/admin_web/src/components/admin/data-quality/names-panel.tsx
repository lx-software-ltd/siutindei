'use client';

import { useQueryState } from 'nuqs';
import { useState } from 'react';

import {
  DataQualityPanel,
  QualityFilters,
  QualitySelect,
  STATUS_FILTERS,
} from '@/components/admin/data-quality/data-quality-panel';
import { AdminEditorPanel } from '@/components/ui/admin-editor-panel';
import { AdminField, AdminFieldGrid } from '@/components/ui/admin-field-grid';
import { AdminInputCard } from '@/components/ui/admin-input-card';
import {
  adminTableText,
  formatAdminTableLabel,
  formatAdminTableLabels,
} from '@/components/ui/admin-table-value';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { useDataQualityQueue } from '@/hooks/use-data-quality-queue';
import { adminTabLabel, formatAdminPageName } from '@/lib/admin-page-name';
import { getAdminQueryClient } from '@/lib/admin-query-client';
import { adminQueryKeys } from '@/lib/admin-query-keys';
import { ApiError } from '@/lib/api-client';
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
} from '@/lib/api-client-data-quality';

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
const RECORDS = [
  ['', 'Any record'],
  ['organization', 'Organizations'],
  ['activity', 'Activities'],
] as const;

interface NameFilters {
  entity_type: string;
  rule: string;
  status: string;
}

const DEFAULT_FILTERS: NameFilters = { entity_type: '', rule: '', status: 'pending' };

type NameSummary = Awaited<ReturnType<typeof getNameFixSummary>>;

function splitNameSettingList(value: string): string[] {
  return value.split(/\s+/).filter(Boolean);
}

export function NamesPanel() {
  const [runId, setRun] = useQueryState('run');
  const [draft, setDraft] = useState<NameFixSettings | null>(null);
  const [exceptionText, setExceptionText] = useState<string | null>(null);
  const [suffixText, setSuffixText] = useState<string | null>(null);
  const queue = useDataQualityQueue<NameFixProposal, NameFilters, NameSummary, NameFixSettings>({
    queryKey: adminQueryKeys.nameFixes(),
    paramName: 'name-fix',
    defaultFilters: DEFAULT_FILTERS,
    errorPrefix: 'Failed to load name fixes',
    extraKey: [runId ?? ''],
    selectionFields: ['entity_type', 'rule', 'status'],
    fetchPage: ({ cursor, limit, orgId, entity_type, rule, status }) =>
      listNameFixes({
        cursor,
        limit,
        entity_type: entity_type || undefined,
        rule: rule || undefined,
        status: runId ? undefined : status || undefined,
        org_id: orgId || undefined,
        run: runId || undefined,
      }),
    getOne: getNameFix,
    loadSummary: getNameFixSummary,
    loadSettings: getNameFixSettings,
    pendingCount: (summary) => summary?.by_status.pending ?? 0,
    scan: ({ reviewScope, filters }) =>
      scanNameFixes({
        entity_type: filters.entity_type || undefined,
        review_scope: reviewScope,
      }),
    formatScan: (result) => {
      const scan = result as Awaited<ReturnType<typeof scanNameFixes>>;
      const stopped = scan.truncated ? ' Scan stopped at the limit; run it again to continue.' : '';
      return `Created ${scan.created}, updated ${scan.updated}, skipped ${scan.skipped}, cleared ${scan.cleared ?? 0}.${stopped}`;
    },
    decide: (item, action) => decideNameFix(item.id, { action }),
    bulk: ({ action, all, ids, filters, orgId }) =>
      decideNameFixesBulk(
        all
          ? {
              action,
              entity_type: filters.entity_type || undefined,
              rule: filters.rule || undefined,
              org_id: orgId || undefined,
            }
          : { action, ids }
      ),
    appliedNotice: 'Name updated.',
    dismissedNotice: 'Proposal dismissed.',
    decideError: 'Could not update the name.',
    emptySelection: 'Select at least one name.',
  });
  const settings = draft ?? queue.settings ?? null;
  const exceptionValue = exceptionText ?? settings?.exception_words.join(' ') ?? '';
  const suffixValue = suffixText ?? settings?.bracket_suffixes.join(' ') ?? '';
  const filters = queue.list.filters;
  const open = queue.open;
  const rules = settings?.available_rules ?? NAME_RULES;

  async function saveSettings() {
    if (!settings) return;
    queue.setError('');
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
      queue.setNotice('Name rules saved.');
    } catch (err) {
      queue.setError(err instanceof ApiError ? err.message : 'Could not save rules.');
    }
  }

  return (
    <DataQualityPanel
      pageName={PAGE_NAME}
      noticeTitle='Names'
      queue={queue}
      scope={
        <>
          {runId ? (
            <p className='text-sm text-ink-700'>
              Names from this run, including changes the import already applied.{' '}
              <button type='button' className='underline underline-offset-2' onClick={() => void setRun(null)}>
                Show all
              </button>
            </p>
          ) : null}
          {queue.organization ? (
            <p className='text-sm text-ink-700'>
              Filtered to the organization from the review queue.{' '}
              <button type='button' className='underline' onClick={() => void queue.setOrganization(null)}>
                Show all
              </button>
            </p>
          ) : null}
        </>
      }
      getLabel={(item) => item.current_value}
      middleColumnCount={4}
      emptyLabel='No names match these filters. Sweep pending or Sweep all orgs to find some.'
      filters={
        <QualityFilters>
          <QualitySelect
            id='name-fix-entity'
            label='Record'
            value={filters.entity_type}
            onChange={(value) => queue.list.setFilter('entity_type', value)}
            options={RECORDS}
          />
          <QualitySelect
            id='name-fix-status'
            label='Status'
            value={filters.status}
            onChange={(value) => queue.list.setFilter('status', value)}
            options={STATUS_FILTERS}
          />
          <QualitySelect
            id='name-fix-rule'
            label='Rule'
            value={filters.rule}
            onChange={(value) => queue.list.setFilter('rule', value)}
            options={[['', 'Any rule'], ...rules.map((rule) => [rule, rule] as const)]}
          />
        </QualityFilters>
      }
      columns={[
        { header: 'Current', cell: (item) => item.current_value },
        { header: 'Proposed', cell: (item) => adminTableText(item.proposed_value) },
        {
          header: 'Record',
          priority: 'secondary',
          cell: (item) => formatAdminTableLabel(item.entity_type),
        },
        { header: 'Rules', priority: 'tertiary', cell: (item) => formatAdminTableLabels(item.rules) },
      ]}
      detail={
        open && open.status === 'pending' ? (
          <AdminEditorPanel
            actions={
              <>
                <Button
                  type='button'
                  onClick={() => void queue.decide(open, 'apply')}
                  loading={queue.activeId === open.id}
                  loadingLabel='Saving…'
                >
                  Apply
                </Button>
                <Button type='button' variant='secondary' onClick={() => void queue.decide(open, 'dismiss')}>
                  Dismiss
                </Button>
              </>
            }
          >
            <p className='text-sm text-ink-700'>
              {open.current_value} becomes {open.proposed_value}
            </p>
          </AdminEditorPanel>
        ) : null
      }
      settings={
        settings ? (
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
                <label key={rule} className='flex items-center gap-2 text-sm text-ink-700'>
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
        ) : null
      }
    />
  );
}
