'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useQueryState } from 'nuqs';

import { usePaginatedList } from '../../../hooks/use-paginated-list';
import { adminQueryKeys } from '../../../lib/admin-query-keys';
import { buildApiUrl, request } from '../../../lib/api-client-core';
import {
  getCategorySuggestionSettings,
  getCategorySuggestionSummary,
  decideCategoryReviewsBulk,
  listCategoryReviews,
  startCategoryScan,
  type ActivityCategoryReview,
  type CategoryReviewBulkResult,
  type CategorySuggestionSummary,
} from '../../../lib/api-client-category-suggestions';
import { StatusBanner } from '../../status-banner';
import { AdminFilterBar, AdminFilterField } from '../../ui/admin-filter-bar';
import { Button } from '../../ui/button';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { Input } from '../../ui/input';
import { Select } from '../../ui/select';
import { decideMatchingPending } from './category-checks-bulk';
import { CategoryChecksTable } from './category-checks-table';

interface ReviewFilters {
  status: string;
  verdict: string;
  q: string;
  org_id: string;
  proposed_category_id: string;
}

interface CategoryOption {
  id: string;
  name: string;
}

const DEFAULT_FILTERS: ReviewFilters = {
  status: '',
  verdict: '',
  q: '',
  org_id: '',
  proposed_category_id: '',
};

export function CategoryChecksPanel() {
  const [organizationParam] = useQueryState('organization');
  const scopedOrgId = organizationParam ?? '';
  const fetchReviews = useCallback(
    async ({
      cursor,
      limit,
      status,
      verdict,
      q,
      org_id,
      proposed_category_id,
    }: ReviewFilters & { cursor: string | null; limit: number }) => {
      const page = await listCategoryReviews({
        cursor: cursor ?? undefined,
        limit,
        status: status || undefined,
        verdict: verdict || undefined,
        q: q || undefined,
        org_id: org_id || undefined,
        proposed_category_id: proposed_category_id || undefined,
      });
      return { items: page.items, nextCursor: page.next_cursor || null };
    },
    []
  );
  const list = usePaginatedList<ActivityCategoryReview, ReviewFilters>({
    queryKey: adminQueryKeys.categoryReviews(),
    defaultFilters: DEFAULT_FILTERS,
    debounceKeys: ['q'],
    errorPrefix: 'Could not load category checks',
    fetcher: fetchReviews,
  });
  const [summary, setSummary] = useState<CategorySuggestionSummary | null>(null);
  const [threshold, setThreshold] = useState<number | null>(0.9);
  const [categories, setCategories] = useState<CategoryOption[]>([]);
  const [confirmMode, setConfirmMode] = useState<
    'pending_review' | 'all' | null
  >(null);
  const [selectScope, setSelectScope] = useState<'none' | 'visible' | 'all'>(
    'none'
  );
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [ignoreCurrent, setIgnoreCurrent] = useState(false);
  const [bulkAction, setBulkAction] = useState<'apply' | 'dismiss' | null>(null);
  const [bulkPreview, setBulkPreview] = useState<CategoryReviewBulkResult | null>(
    null
  );
  const [bulkProgress, setBulkProgress] = useState('');
  const [isStarting, setIsStarting] = useState(false);
  const [isBulkRunning, setIsBulkRunning] = useState(false);
  const [error, setError] = useState('');
  const bulkAbort = useRef<AbortController | null>(null);
  const selectAllRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate =
        selectScope === 'visible' && list.hasMore;
    }
  }, [list.hasMore, selectScope]);

  const { refetch, setFilter } = list;
  const selectedOrgId = scopedOrgId || list.filters.org_id;

  useEffect(() => {
    if (list.filters.org_id === scopedOrgId) {
      return;
    }
    setFilter('org_id', scopedOrgId);
  }, [list.filters.org_id, scopedOrgId, setFilter]);

  const reload = useCallback(() => {
    void refetch();
    void getCategorySuggestionSummary(selectedOrgId || undefined)
      .then((counts) => setSummary(counts))
      .catch(() => undefined);
  }, [refetch, selectedOrgId]);

  useEffect(() => {
    let cancelled = false;
    void getCategorySuggestionSummary(selectedOrgId || undefined)
      .then((counts) => {
        if (!cancelled) {
          setSummary(counts);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [selectedOrgId]);

  useEffect(() => {
    let cancelled = false;
    const categoriesUrl = new URL(buildApiUrl('v1/admin/activity-categories'));
    categoriesUrl.searchParams.set('limit', '200');
    void request<{ items: CategoryOption[] }>(categoriesUrl.toString())
      .then((page) => {
        if (!cancelled) {
          setCategories(
            [...page.items].sort((left, right) => left.name.localeCompare(right.name))
          );
        }
      })
      .catch(() => undefined);
    void getCategorySuggestionSettings()
      .then((settings) => {
        if (!cancelled) {
          setThreshold(
            settings.auto_assign_threshold === undefined
              ? 0.9
              : settings.auto_assign_threshold
          );
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  const active = summary?.active_scan_run;
  const isRunning = active?.status === 'queued' || active?.status === 'running';

  useEffect(() => {
    if (!isRunning) {
      return;
    }
    const timer = window.setInterval(reload, 5000);
    return () => window.clearInterval(timer);
  }, [isRunning, reload]);

  const pendingCandidates = summary?.scan_candidate_total ?? 0;
  const allCandidates = summary?.scan_candidate_total_all ?? pendingCandidates;
  const sweepScope = confirmMode === 'all' ? 'all' : 'pending_review';
  const candidates =
    sweepScope === 'all' ? allCandidates : pendingCandidates;
  const scanLimit = summary?.scan_limit ?? 500;
  const batchSize = summary?.scan_batch_size ?? 10;
  const scanCount = Math.min(candidates, scanLimit);
  const batches = Math.max(1, Math.ceil(scanCount / batchSize));
  const thresholdText =
    threshold === null
      ? 'Auto-assign is off.'
      : `Auto-assign when confidence is at least ${threshold}.`;
  const progress = active
    ? `${active.batches_done} of ${active.batches_total} batches. ${active.failed} failed.`
    : '';

  async function startScan(reviewScope: 'pending_review' | 'all') {
    setIsStarting(true);
    setError('');
    try {
      await startCategoryScan({
        org_id: selectedOrgId || undefined,
        mode: 'verify',
        review_scope: reviewScope,
        rescan: ignoreCurrent ? true : undefined,
        ignore_current_category: ignoreCurrent ? true : undefined,
      });
      setConfirmMode(null);
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Scan failed.');
    } finally {
      setIsStarting(false);
    }
  }

  const visibleIds = list.items.map((item) => item.id);
  const hasSelection = selectScope === 'all' || selected.size > 0;
  const bulkFilters = {
    verdict: list.filters.verdict || undefined,
    q: list.filters.q || undefined,
    org_id: list.filters.org_id || undefined,
    proposed_category_id: list.filters.proposed_category_id || undefined,
    ...(selectScope === 'all' ? {} : { ids: Array.from(selected) }),
  };
  const filtersAreBlank =
    selectScope === 'all' &&
    !list.filters.verdict &&
    !list.filters.q &&
    !list.filters.org_id &&
    !list.filters.proposed_category_id;

  useEffect(() => {
    setSelectScope('none');
    setSelected(new Set());
  }, [
    list.filters.status,
    list.filters.verdict,
    list.filters.q,
    list.filters.org_id,
    list.filters.proposed_category_id,
  ]);

  useEffect(() => {
    if (selectScope !== 'visible') {
      return;
    }
    setSelected((current) => {
      let changed = false;
      const next = new Set(current);
      for (const item of list.items) {
        if (!next.has(item.id)) {
          next.add(item.id);
          changed = true;
        }
      }
      return changed ? next : current;
    });
  }, [list.items, selectScope]);

  function cycleSelectScope() {
    if (selectScope === 'none') {
      setSelected(new Set(visibleIds));
      setSelectScope('visible');
      return;
    }
    if (selectScope === 'visible' && list.hasMore) {
      setSelectScope('all');
      return;
    }
    setSelected(new Set());
    setSelectScope('none');
  }

  useEffect(() => {
    if (bulkAction === null) {
      setBulkPreview(null);
      setBulkProgress('');
      return;
    }
    const controller = new AbortController();
    let cancelled = false;
    decideCategoryReviewsBulk(
      {
        action: bulkAction,
        dry_run: true,
        ...bulkFilters,
      },
      controller.signal
    )
      .then((result) => {
        if (!cancelled) {
          setBulkPreview(result);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setBulkPreview(null);
        }
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [
    bulkAction,
    list.filters.org_id,
    list.filters.proposed_category_id,
    list.filters.q,
    list.filters.verdict,
    selectScope,
    selected,
  ]);

  async function runBulk(action: 'apply' | 'dismiss') {
    const controller = new AbortController();
    bulkAbort.current = controller;
    setIsBulkRunning(true);
    setError('');
    setBulkProgress('');
    try {
      const result = await decideMatchingPending(bulkFilters, action, {
        signal: controller.signal,
        onProgress: (progress) => {
          setBulkProgress(
            `${progress.decided} of ${progress.matched} updated. ` +
              `${progress.failed} failed.`
          );
        },
      });
      setBulkAction(null);
      setSelectScope('none');
      setSelected(new Set());
      const verb = action === 'apply' ? 'applied' : 'dismissed';
      const details = result.failures.map((item) => item.message).join(' ');
      if (result.cancelled) {
        setError(`Stopped after ${result.decided} ${verb}.`);
      } else if (result.truncated) {
        setError(
          `Stopped after ${result.decided} ${verb}. More matching reviews remain.`
        );
      } else if (result.failed > 0) {
        setError(`${result.decided} ${verb}, ${result.failed} failed. ${details}`);
      }
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Bulk update failed.');
    } finally {
      bulkAbort.current = null;
      setIsBulkRunning(false);
    }
  }

  return (
    <div className='space-y-4'>
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
      <CategoryChecksTable
        items={list.items}
        isLoading={list.isLoading}
        isLoadingMore={list.isLoadingMore}
        error={list.error}
        hasMore={list.hasMore}
        onLoadMore={() => {
          void list.loadMore();
        }}
        onReload={reload}
        leadingHead={
          <input
            ref={selectAllRef}
            type='checkbox'
            aria-label={
              selectScope === 'all'
                ? 'Clear selection'
                : selectScope === 'visible' && list.hasMore
                  ? 'Select all matching rows'
                  : 'Select visible rows'
            }
            checked={selectScope === 'all' || selectScope === 'visible'}
            onChange={() => cycleSelectScope()}
          />
        }
        renderLeading={(item) => (
          <input
            type='checkbox'
            aria-label='Select row'
            checked={selectScope === 'all' || selected.has(item.id)}
            onClick={(event) => event.stopPropagation()}
            onChange={(event) => {
              setSelectScope('visible');
              setSelected((current) => {
                const next = new Set(current);
                if (event.target.checked) {
                  next.add(item.id);
                } else {
                  next.delete(item.id);
                }
                if (next.size === 0) {
                  setSelectScope('none');
                }
                return next;
              });
            }}
          />
        )}
        filters={
          <AdminFilterBar
            summary={
              progress ||
              `${summary?.review_pending_total ?? 0} waiting. ` +
                `${summary?.auto_applied_total ?? 0} auto-assigned.`
            }
          >
            {scopedOrgId ? (
              <AdminFilterField label='Organization' htmlFor='check-org-filter'>
                <Input
                  id='check-org-filter'
                  value={scopedOrgId}
                  readOnly
                />
              </AdminFilterField>
            ) : null}
            <AdminFilterField label='Status' htmlFor='check-status-filter'>
              <Select
                id='check-status-filter'
                value={list.filters.status}
                onChange={(event) => list.setFilter('status', event.target.value)}
              >
                <option value=''>Any</option>
                <option value='pending'>Pending</option>
                <option value='confirmed'>Confirmed</option>
                <option value='auto_applied'>Auto-assigned</option>
                <option value='applied'>Applied</option>
                <option value='dismissed'>Dismissed</option>
                <option value='reverted'>Reverted</option>
              </Select>
            </AdminFilterField>
            <AdminFilterField label='Verdict' htmlFor='check-verdict-filter'>
              <Select
                id='check-verdict-filter'
                value={list.filters.verdict}
                onChange={(event) => list.setFilter('verdict', event.target.value)}
              >
                <option value=''>Any</option>
                <option value='confirm'>Confirm</option>
                <option value='reassign'>Reassign</option>
                <option value='propose'>Propose</option>
              </Select>
            </AdminFilterField>
            <AdminFilterField
              label='Proposed category'
              htmlFor='check-proposed-filter'
            >
              <Select
                id='check-proposed-filter'
                value={list.filters.proposed_category_id}
                onChange={(event) =>
                  list.setFilter('proposed_category_id', event.target.value)
                }
              >
                <option value=''>Any</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </Select>
            </AdminFilterField>
            <AdminFilterField label='Search' htmlFor='check-search'>
              <Input
                id='check-search'
                value={list.filters.q}
                placeholder='Activity or organization'
                onChange={(event) => list.setFilter('q', event.target.value)}
              />
            </AdminFilterField>
          </AdminFilterBar>
        }
        toolbar={
          <div className='mb-3 flex flex-wrap gap-2'>
            <Button
              type='button'
              size='sm'
              disabled={pendingCandidates === 0 || isRunning || isStarting}
              loading={isStarting && confirmMode === 'pending_review'}
              loadingLabel='Scanning…'
              onClick={() => setConfirmMode('pending_review')}
            >
              Sweep pending
            </Button>
            <Button
              type='button'
              size='sm'
              disabled={allCandidates === 0 || isRunning || isStarting}
              loading={isStarting && confirmMode === 'all'}
              loadingLabel='Scanning…'
              onClick={() => setConfirmMode('all')}
            >
              Sweep all orgs
            </Button>
            <Button
              type='button'
              variant='outline'
              size='sm'
              disabled={!hasSelection || isRunning || isStarting || isBulkRunning}
              loading={isBulkRunning && bulkAction === 'apply'}
              loadingLabel='Applying…'
              onClick={() => setBulkAction('apply')}
            >
              Apply matching
            </Button>
            <Button
              type='button'
              variant='outline'
              size='sm'
              disabled={!hasSelection || isRunning || isStarting || isBulkRunning}
              loading={isBulkRunning && bulkAction === 'dismiss'}
              loadingLabel='Dismissing…'
              onClick={() => setBulkAction('dismiss')}
            >
              Dismiss matching
            </Button>
          </div>
        }
      />
      <ConfirmDialog
        open={confirmMode !== null}
        title={confirmMode === 'all' ? 'Sweep all orgs' : 'Sweep pending'}
        message={`${
          candidates > scanCount
            ? `Scan ${scanCount} of ${candidates} activities`
            : `Scan ${scanCount} activities`
        } in ${batches} model ${batches === 1 ? 'call' : 'calls'}. ${
          confirmMode === 'all'
            ? 'Includes approved organizations. '
            : 'Organizations still in review. '
        }${thresholdText}`}
        confirmLabel='Start scan'
        confirmLoading={isStarting}
        confirmLoadingLabel='Starting…'
        onConfirm={() => {
          if (confirmMode) {
            void startScan(confirmMode);
          }
        }}
        onCancel={() => setConfirmMode(null)}
      >
        {confirmMode === 'pending_review' || confirmMode === 'all' ? (
          <label className='mt-3 flex items-start gap-2 text-sm text-slate-700'>
            <input
              id='check-ignore-current'
              type='checkbox'
              className='mt-1'
              checked={ignoreCurrent}
              onChange={(event) => setIgnoreCurrent(event.target.checked)}
            />
            <span>
              Ignore the current category. Template descriptions are omitted
              and activities checked in the last 30 days are included.
            </span>
          </label>
        ) : null}
      </ConfirmDialog>
      <ConfirmDialog
        open={bulkAction !== null}
        title={
          bulkAction === 'dismiss'
            ? 'Dismiss matching reviews'
            : 'Apply matching reviews'
        }
        message={
          selectScope === 'all'
            ? bulkAction === 'dismiss'
              ? 'Dismiss every pending review that matches the current filters.'
              : 'Apply every pending reassignment that matches the current filters.'
            : bulkAction === 'dismiss'
              ? `Dismiss the ${selected.size} selected pending reviews.`
              : `Apply the ${selected.size} selected pending reviews.`
        }
        confirmLabel={bulkAction === 'dismiss' ? 'Dismiss pending' : 'Apply pending'}
        confirmLoading={isBulkRunning}
        confirmLoadingLabel={
          bulkAction === 'dismiss' ? 'Dismissing…' : 'Applying…'
        }
        onConfirm={() => {
          if (bulkAction) {
            void runBulk(bulkAction);
          }
        }}
        onCancel={() => {
          if (isBulkRunning) {
            bulkAbort.current?.abort();
            return;
          }
          setBulkAction(null);
        }}
      >
        <p>
          {selectScope === 'all'
            ? filtersAreBlank
              ? 'No filters are set, so this includes every pending review.'
              : 'Only reviews matching the current filters are included.'
            : 'Only the selected visible rows are included.'}
        </p>
        <p className='mt-2'>
          {bulkPreview
            ? `${bulkPreview.applicable} will be ${
                bulkAction === 'dismiss' ? 'dismissed' : 'applied'
              }. ${bulkPreview.skipped} will be skipped.`
            : 'Counting matching reviews.'}
        </p>
        {bulkProgress ? <p className='mt-2'>{bulkProgress}</p> : null}
      </ConfirmDialog>
    </div>
  );
}
