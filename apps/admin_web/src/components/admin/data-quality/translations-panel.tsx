'use client';

import { useState } from 'react';

import {
  DataQualityPanel,
  QualityFilters,
  QualitySelect,
  QualityText,
  STATUS_FILTERS,
} from '@/components/admin/data-quality/data-quality-panel';
import { ReviewQueueScopeNote, sweepLimitNote } from '@/components/admin/data-quality/sweep-shared';
import { AdminEditorPanel } from '@/components/ui/admin-editor-panel';
import { AdminField, AdminFieldGrid } from '@/components/ui/admin-field-grid';
import { adminTableText, formatAdminTableLabel } from '@/components/ui/admin-table-value';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { useDataQualityQueue } from '@/hooks/use-data-quality-queue';
import { adminTabLabel, formatAdminPageName } from '@/lib/admin-page-name';
import { adminQueryKeys } from '@/lib/admin-query-keys';
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
  type TranslationFixScanResult,
  type TranslationFixSettings,
  type TranslationFixSummary,
} from '@/lib/api-client-data-quality';

const PAGE_NAME = formatAdminPageName('Data quality', adminTabLabel.translations);
const LANGUAGES = [
  ['en', 'English'],
  ['zh', 'Chinese'],
  ['zh-HK', 'Hong Kong'],
] as const;
const RECORDS = [
  ['', 'Any record'],
  ['organization', 'Organizations'],
  ['activity', 'Activities'],
] as const;
const FIELDS = [
  ['', 'Any field'],
  ['name', 'Name'],
  ['description', 'Description'],
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
  if (field === 'name') return 'Name';
  if (field === 'description') return 'Description';
  return formatAdminTableLabel(field);
}

function scanNotice(result: TranslationFixScanResult): string {
  const scanned = result.total_entities == null ? '' : ` Scanned ${result.total_entities} entities.`;
  const warning = result.error ? ` ${result.error}` : '';
  return `Cleared ${result.cleared}, skipped ${result.skipped}, queued ${result.queued_for_model}.${scanned}${sweepLimitNote(result.truncated)}${warning}`;
}

export function TranslationsPanel() {
  const [draftText, setDraftText] = useState<Record<string, string>>({});
  const [appliedDraftKey, setAppliedDraftKey] = useState<string | null>(null);
  const queue = useDataQualityQueue<
    TranslationFixProposal,
    TranslationFilters,
    TranslationFixSummary,
    TranslationFixSettings
  >({
    queryKey: adminQueryKeys.translationFixes(),
    paramName: 'translation-fix',
    defaultFilters: DEFAULT_FILTERS,
    debounceKeys: ['q'],
    errorPrefix: 'Failed to load translation fixes',
    selectionFields: ['q', 'entity_type', 'field', 'status'],
    refreshListWhileActive: true,
    sweepTimeout: true,
    trackScanRun: true,
    fetchPage: ({ cursor, limit, orgId, q, entity_type, field, status }) =>
      listTranslationFixes({
        cursor,
        limit,
        q: q || undefined,
        entity_type: entity_type || undefined,
        field: field || undefined,
        status: status || undefined,
        org_id: orgId || undefined,
      }),
    getOne: getTranslationFix,
    loadSummary: getTranslationFixSummary,
    loadSettings: getTranslationFixSettings,
    pendingCount: (summary) => summary?.by_status.pending ?? 0,
    activeRun: (summary) => {
      const run = summary?.active_run;
      if (!run) return null;
      return {
        status: run.status,
        batches_done: run.batches_done ?? 0,
        batches_total: run.batches_total ?? 0,
      };
    },
    latestRun: (summary) => summary?.latest_run ?? null,
    scan: ({ reviewScope, filters, orgId }) =>
      scanTranslationFixes({
        entity_type: filters.entity_type || undefined,
        q: filters.q || undefined,
        org_id: orgId || undefined,
        review_scope: reviewScope,
      }),
    formatScan: (result) => scanNotice(result as TranslationFixScanResult),
    decide: (item, action) =>
      decideTranslationFix(item.id, {
        action,
        ...(action === 'apply' ? { translations: draftText } : {}),
      }),
    bulk: ({ action, all, ids, filters, orgId }) =>
      decideTranslationFixesBulk(
        all
          ? {
              action,
              entity_type: filters.entity_type || undefined,
              field: filters.field || undefined,
              q: filters.q || undefined,
              org_id: orgId || undefined,
            }
          : { action, ids }
      ),
    appliedNotice: 'Translation updated.',
    dismissedNotice: 'Proposal dismissed.',
    decideError: 'Could not update the translation.',
    emptySelection: 'Select at least one translation.',
    budget: {
      readLimit: (settings) => settings.monthly_cost_limit_usd,
      readMonthCost: (summary) => summary?.month_cost_usd ?? 0,
      save: (monthly) => updateTranslationFixSettings({ monthly_cost_limit_usd: monthly }),
      savedNotice: 'Translation budget saved.',
      saveError: 'Could not save the budget.',
    },
  });
  const open = queue.open;
  const draftKey = `${open?.id ?? ''}\0${(open?.missing_languages ?? []).join(',')}\0${JSON.stringify(open?.proposed_text ?? {})}`;
  if (draftKey !== appliedDraftKey) {
    setAppliedDraftKey(draftKey);
    if (open?.id) {
      const proposed = open.proposed_text ?? {};
      const next: Record<string, string> = {};
      for (const code of open.missing_languages ?? []) {
        next[code] = proposed[code] ?? '';
      }
      setDraftText(next);
    }
  }
  const filters = queue.list.filters;

  return (
    <DataQualityPanel
      pageName={PAGE_NAME}
      noticeTitle='Translations'
      queue={queue}
      scope={
        queue.organization ? (
          <ReviewQueueScopeNote onClear={() => void queue.setOrganization(null)} />
        ) : null
      }
      getLabel={(item) => item.entity_name || item.current_label}
      middleColumnCount={4}
      emptyLabel='No translations match these filters. Sweep pending or Sweep all orgs to find some.'
      budgetDescription='Uses the category-check model. Category checks and location sweeps are not counted.'
      budgetInputId='translation-fix-budget'
      filters={
        <QualityFilters>
          <QualityText
            id='translation-fix-q'
            label='Name'
            value={filters.q}
            onChange={(value) => queue.list.setFilter('q', value)}
          />
          <QualitySelect
            id='translation-fix-entity'
            label='Record'
            value={filters.entity_type}
            onChange={(value) => queue.list.setFilter('entity_type', value)}
            options={RECORDS}
          />
          <QualitySelect
            id='translation-fix-field'
            label='Field'
            value={filters.field}
            onChange={(value) => queue.list.setFilter('field', value)}
            options={FIELDS}
          />
          <QualitySelect
            id='translation-fix-status'
            label='Status'
            value={filters.status}
            onChange={(value) => queue.list.setFilter('status', value)}
            options={STATUS_FILTERS}
          />
        </QualityFilters>
      }
      columns={[
        {
          header: 'Record',
          cell: (item) => item.entity_name || formatAdminTableLabel(item.entity_type),
        },
        { header: 'Field', cell: (item) => fieldLabel(item.field) },
        { header: 'Missing', priority: 'secondary', cell: (item) => adminTableText(item.missing_label) },
        {
          header: 'Proposed',
          priority: 'secondary',
          cell: (item) => adminTableText(item.proposed_label),
        },
      ]}
      detail={
        open && open.status === 'pending' ? (
          <AdminEditorPanel>
            {open.rationale ? <p className='text-sm text-ink-700'>{open.rationale}</p> : null}
            {LANGUAGES.filter((entry) => open.source_text?.[entry[0]]).map(([code, label]) => (
              <p key={code} className='text-sm text-ink-700'>
                {label}: {open.source_text?.[code]}
              </p>
            ))}
            <AdminFieldGrid columns={1}>
              {(open.missing_languages ?? []).map((code) => {
                const label = LANGUAGES.find((entry) => entry[0] === code)?.[1] ?? code;
                const long = open.field === 'description';
                const shared = {
                  id: `translation-fix-${code}`,
                  value: draftText[code] ?? '',
                  onChange: (event: { target: { value: string } }) =>
                    setDraftText((current) => ({ ...current, [code]: event.target.value })),
                };
                return (
                  <AdminField key={code} label={label} htmlFor={shared.id}>
                    {long ? <Textarea {...shared} rows={4} /> : <Input {...shared} />}
                  </AdminField>
                );
              })}
            </AdminFieldGrid>
            <div className='flex gap-2'>
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
            </div>
          </AdminEditorPanel>
        ) : null
      }
    />
  );
}
