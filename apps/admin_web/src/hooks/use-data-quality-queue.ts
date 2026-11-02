'use client';

import { useQuery } from '@tanstack/react-query';
import { useQueryState } from 'nuqs';
import { useEffect, useState } from 'react';

import { SWEEP_TIMEOUT_MESSAGE } from '@/components/admin/data-quality/sweep-shared';
import { useBulkRowSelection } from '@/hooks/use-bulk-row-selection';
import { useExpandedRecord } from '@/hooks/use-expanded-record';
import {
  usePaginatedList,
  type PaginatedFetcherParams,
} from '@/hooks/use-paginated-list';
import { getAdminQueryClient } from '@/lib/admin-query-client';
import { ApiError } from '@/lib/api-client';

export type ReviewScope = 'pending_review' | 'all';

export interface ActiveSweepRun {
  status: string;
  batches_done: number;
  batches_total: number;
}

export interface FinishedSweepRun {
  scan_run_id: string;
  status: string;
  error?: string | null;
  created: number;
  updated: number;
  skipped: number;
  cleared: number;
}

export interface DataQualityPage<TItem> {
  items: TItem[];
  next_cursor?: string | null;
}

interface QueueConfig<TItem extends { id: string }, TFilters extends object, TSummary, TSettings> {
  queryKey: readonly unknown[];
  paramName: string;
  defaultFilters: TFilters;
  debounceKeys?: (keyof TFilters)[];
  errorPrefix: string;
  extraKey?: readonly unknown[];
  selectionFields: (keyof TFilters)[];
  fetchPage: (
    args: TFilters & { cursor?: string; limit: number; orgId: string | null; signal: AbortSignal }
  ) => Promise<DataQualityPage<TItem>>;
  getOne: (id: string) => Promise<TItem>;
  loadSummary: () => Promise<TSummary>;
  loadSettings: () => Promise<TSettings>;
  pendingCount: (summary: TSummary | undefined) => number;
  activeRun?: (summary: TSummary | undefined) => ActiveSweepRun | null;
  latestRun?: (summary: TSummary | undefined) => FinishedSweepRun | null;
  refreshListWhileActive?: boolean;
  scan: (args: {
    reviewScope: ReviewScope;
    filters: TFilters;
    orgId: string | null;
  }) => Promise<unknown>;
  formatScan: (result: unknown) => string;
  sweepTimeout?: boolean;
  trackScanRun?: boolean;
  decide: (
    item: TItem,
    action: 'apply' | 'dismiss',
    extra?: { targetLocationId?: string }
  ) => Promise<unknown>;
  bulk: (args: {
    action: 'apply' | 'dismiss';
    all: boolean;
    ids: string[];
    filters: TFilters;
    orgId: string | null;
  }) => Promise<{ decided: number; failed: number }>;
  appliedNotice: string;
  dismissedNotice: string;
  decideError: string;
  emptySelection: string;
  budget?: {
    readLimit: (settings: TSettings) => number;
    readMonthCost: (summary: TSummary | undefined) => number;
    save: (amount: number) => Promise<TSettings>;
    savedNotice: string;
    saveError: string;
  };
}

function failureMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

export function useDataQualityQueue<
  TItem extends { id: string },
  TFilters extends object,
  TSummary,
  TSettings,
>(config: QueueConfig<TItem, TFilters, TSummary, TSettings>) {
  const [organization, setOrganization] = useQueryState('organization');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [scanningScope, setScanningScope] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [sweepRunId, setSweepRunId] = useState<string | null>(null);
  const [sweepHandledId, setSweepHandledId] = useState<string | null>(null);
  const [draftLimit, setDraftLimit] = useState<string | null>(null);
  const expanded = useExpandedRecord({ paramName: config.paramName });
  const client = getAdminQueryClient();
  const summaryKey = [...config.queryKey, 'summary'] as const;
  const settingsKey = [...config.queryKey, 'settings'] as const;

  const summaryQuery = useQuery(
    {
      queryKey: summaryKey,
      queryFn: () => config.loadSummary(),
      refetchInterval: (query) => {
        const status = config.activeRun?.(query.state.data)?.status;
        return status === 'queued' || status === 'running' ? 3000 : false;
      },
    },
    client
  );
  const settingsQuery = useQuery(
    {
      queryKey: settingsKey,
      queryFn: () => config.loadSettings(),
    },
    client
  );

  const active = config.activeRun?.(summaryQuery.data) ?? null;
  const sweepActive = active?.status === 'queued' || active?.status === 'running';
  const listKey = [...config.queryKey, organization ?? '', ...(config.extraKey ?? [])];

  const list = usePaginatedList<TItem, TFilters>({
    queryKey: listKey,
    defaultFilters: config.defaultFilters,
    debounceKeys: config.debounceKeys,
    errorPrefix: config.errorPrefix,
    refetchInterval: config.refreshListWhileActive && sweepActive ? 3000 : false,
    fetcher: async (params: PaginatedFetcherParams<TFilters>) => {
      const { cursor, limit, signal, ...filters } = params;
      const page = await config.fetchPage({
        ...(filters as TFilters),
        cursor: cursor ?? undefined,
        limit,
        orgId: organization,
        signal,
      });
      return { items: page.items, nextCursor: page.next_cursor ?? null };
    },
  });

  const selection = useBulkRowSelection(list.items, list.hasMore);
  const resetSelection = selection.resetSelection;
  const selectionKey = config.selectionFields
    .map((key) => String(list.filters[key] ?? ''))
    .concat(organization ?? '')
    .join('\0');
  useEffect(() => {
    resetSelection();
  }, [selectionKey, resetSelection]);

  const listed = list.items.find((item) => item.id === expanded.expandedId) ?? null;
  const detailQuery = useQuery(
    {
      queryKey: [...config.queryKey, 'one', expanded.expandedId],
      queryFn: () => config.getOne(expanded.expandedId as string),
      enabled: Boolean(expanded.expandedId) && !list.isLoading && listed === null,
    },
    client
  );
  const open = listed ?? detailQuery.data ?? null;

  const latest = config.latestRun?.(summaryQuery.data) ?? null;
  const sweepFinished =
    sweepRunId &&
    latest &&
    latest.scan_run_id === sweepRunId &&
    (latest.status === 'done' || latest.status === 'failed')
      ? latest
      : null;
  if (sweepFinished && sweepHandledId !== sweepFinished.scan_run_id) {
    setSweepHandledId(sweepFinished.scan_run_id);
    setNotice((current) => {
      const sweepNotice = current.startsWith('Cleared ') || current.includes('queued ');
      if (!sweepNotice) {
        return current;
      }
      const warning = sweepFinished.error ? ` ${sweepFinished.error}` : '';
      return `Created ${sweepFinished.created}, updated ${sweepFinished.updated}, skipped ${sweepFinished.skipped}, cleared ${sweepFinished.cleared}.${warning}`;
    });
  }

  async function refresh() {
    await client.invalidateQueries({ queryKey: [...config.queryKey, 'summary'] });
    await list.refetch();
  }

  async function runScan(
    key: string,
    job: () => Promise<unknown>,
    format: (result: unknown) => string,
    options: { timeout?: boolean; failure: string; trackRun?: boolean }
  ) {
    setScanningScope(key);
    setError('');
    setNotice('');
    try {
      const result = await job();
      if (options.trackRun && result && typeof result === 'object' && 'scan_run_id' in result) {
        const runId = String((result as { scan_run_id?: string }).scan_run_id ?? '');
        setSweepRunId(runId || null);
        setSweepHandledId(null);
      }
      setNotice(format(result));
      await refresh();
    } catch (err) {
      if (options.timeout && err instanceof ApiError && err.status === 504) {
        setError(SWEEP_TIMEOUT_MESSAGE);
        await refresh();
      } else {
        setError(failureMessage(err, options.failure));
      }
    } finally {
      setScanningScope(null);
    }
  }

  async function sweep(reviewScope: ReviewScope) {
    await runScan(
      reviewScope,
      () =>
        config.scan({
          reviewScope,
          filters: list.filters,
          orgId: organization,
        }),
      (result) => config.formatScan(result),
      {
        timeout: config.sweepTimeout,
        failure: 'Scan failed.',
        trackRun: config.trackScanRun,
      }
    );
  }

  async function decide(
    item: TItem,
    action: 'apply' | 'dismiss',
    extra?: { targetLocationId?: string; activeId?: string }
  ) {
    setActiveId(extra?.activeId ?? item.id);
    setError('');
    try {
      await config.decide(item, action, extra);
      setNotice(action === 'apply' ? config.appliedNotice : config.dismissedNotice);
      await refresh();
    } catch (err) {
      setError(failureMessage(err, config.decideError));
    } finally {
      setActiveId(null);
    }
  }

  async function bulk(action: 'apply' | 'dismiss') {
    if (selection.selectScope !== 'all' && selection.selected.size === 0) {
      setError(config.emptySelection);
      return;
    }
    setError('');
    try {
      const result = await config.bulk({
        action,
        all: selection.selectScope === 'all',
        ids: Array.from(selection.selected),
        filters: list.filters,
        orgId: organization,
      });
      setNotice(`Updated ${result.decided}. ${result.failed} failed.`);
      resetSelection();
      await refresh();
    } catch (err) {
      setError(failureMessage(err, 'Bulk update failed.'));
    }
  }

  const settings = settingsQuery.data;
  const budgetConfig = config.budget;
  const limitValue =
    draftLimit ?? (settings && budgetConfig ? String(budgetConfig.readLimit(settings)) : '');

  async function saveBudget() {
    const current = config.budget;
    if (!current) {
      return;
    }
    const monthly = Number(limitValue);
    if (!Number.isFinite(monthly)) {
      setError('Enter a monthly limit.');
      return;
    }
    setError('');
    try {
      const saved = await current.save(monthly);
      client.setQueryData(settingsKey, saved);
      setDraftLimit(null);
      setNotice(current.savedNotice);
    } catch (err) {
      setError(failureMessage(err, current.saveError));
    }
  }

  return {
    list,
    summary: summaryQuery.data,
    settings,
    organization,
    setOrganization,
    expanded,
    open,
    error,
    notice,
    setError,
    setNotice,
    scanningScope,
    sweepBusy: scanningScope !== null || sweepActive,
    activeId,
    pending: config.pendingCount(summaryQuery.data),
    sweepProgress:
      active && sweepActive ? `${active.batches_done} of ${active.batches_total}` : null,
    selection,
    sweep,
    decide,
    bulk,
    runScan,
    refresh,
    budget:
      settings && budgetConfig
        ? {
            monthCost: budgetConfig.readMonthCost(summaryQuery.data),
            limit: budgetConfig.readLimit(settings),
            value: limitValue,
            onChange: setDraftLimit,
            save: saveBudget,
          }
        : null,
  };
}
