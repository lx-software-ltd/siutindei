'use client';

import { useCallback, useEffect, useState } from 'react';

import { usePaginatedList } from '../../../hooks/use-paginated-list';
import { adminQueryKeys } from '../../../lib/admin-query-keys';
import { buildApiUrl, request } from '../../../lib/api-client-core';
import {
  getCategorySuggestionSettings,
  getCategorySuggestionSummary,
  listCategoryReviews,
  startCategoryScan,
  type ActivityCategoryReview,
  type CategorySuggestionSummary,
} from '../../../lib/api-client-category-suggestions';
import { StatusBanner } from '../../status-banner';
import { AdminCreateButton } from '../../ui/admin-create-button';
import { AdminFilterBar, AdminFilterField } from '../../ui/admin-filter-bar';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { Input } from '../../ui/input';
import { Select } from '../../ui/select';
import { CategoryChecksTable } from './category-checks-table';

interface ReviewFilters {
  status: string;
  verdict: string;
  q: string;
  org_id: string;
}

interface PendingOrganization {
  id: string;
  name: string;
  review_status?: string;
}

const DEFAULT_FILTERS: ReviewFilters = {
  status: '',
  verdict: '',
  q: '',
  org_id: '',
};

export function CategoryChecksPanel() {
  const fetchReviews = useCallback(
    async ({
      cursor,
      limit,
      status,
      verdict,
      q,
      org_id,
    }: ReviewFilters & { cursor: string | null; limit: number }) => {
      const page = await listCategoryReviews({
        cursor: cursor ?? undefined,
        limit,
        status: status || undefined,
        verdict: verdict || undefined,
        q: q || undefined,
        org_id: org_id || undefined,
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
  const [organizations, setOrganizations] = useState<PendingOrganization[]>([]);
  const [threshold, setThreshold] = useState<number | null>(0.9);
  const [confirmMode, setConfirmMode] = useState<'discover' | 'verify' | null>(
    null
  );
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState('');

  const { refetch } = list;
  const selectedOrgId = list.filters.org_id;
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
    const url = new URL(buildApiUrl('v1/admin/organizations'));
    url.searchParams.set('review_status', 'pending_review');
    url.searchParams.set('limit', '100');
    void request<{ items: PendingOrganization[] }>(url.toString())
      .then((page) => {
        if (!cancelled) {
          setOrganizations(
            page.items.filter((item) => item.review_status === 'pending_review')
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

  const candidates = summary?.scan_candidate_total ?? 0;
  const scanLimit = summary?.scan_limit ?? 500;
  const batchSize = summary?.scan_batch_size ?? 10;
  const scanCount = Math.min(candidates, scanLimit);
  const batches = Math.max(1, Math.ceil(scanCount / batchSize));
  const discoverActivities = summary?.discover_activity_total ?? 0;
  const discoverLabels = summary?.discover_label_total ?? 0;
  const discoverCount = Math.min(discoverLabels, scanLimit);
  const discoverBatches = Math.ceil(discoverCount / batchSize);
  const thresholdText =
    threshold === null
      ? 'Auto-assign is off.'
      : `Auto-assign when confidence is at least ${threshold}.`;
  const progress = active
    ? `${active.batches_done} of ${active.batches_total} batches. ${active.failed} failed.`
    : '';

  async function startScan(mode: 'discover' | 'verify') {
    setIsStarting(true);
    setError('');
    try {
      await startCategoryScan({
        org_id: selectedOrgId || undefined,
        mode,
      });
      setConfirmMode(null);
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Scan failed.');
    } finally {
      setIsStarting(false);
    }
  }

  return (
    <div className='space-y-4'>
      {error ? (
        <StatusBanner variant='error' title='Error'>
          {error}
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
        filters={
          <AdminFilterBar
            summary={
              progress ||
              `${summary?.review_pending_total ?? 0} waiting. ` +
                `${summary?.auto_applied_total ?? 0} auto-assigned.`
            }
            trailing={
              <div className='flex flex-wrap gap-2'>
                <AdminCreateButton
                  label='Discover categories'
                  disabled={
                    (discoverActivities === 0 && discoverLabels === 0) ||
                    isRunning ||
                    isStarting
                  }
                  onClick={() => setConfirmMode('discover')}
                />
                <AdminCreateButton
                  label='Verify categories'
                  disabled={scanCount === 0 || isRunning || isStarting}
                  onClick={() => setConfirmMode('verify')}
                />
              </div>
            }
          >
            <AdminFilterField label='Organization' htmlFor='check-org-filter'>
              <Select
                id='check-org-filter'
                value={selectedOrgId}
                onChange={(event) => list.setFilter('org_id', event.target.value)}
              >
                <option value=''>All pending organizations</option>
                {organizations.map((organization) => (
                  <option key={organization.id} value={organization.id}>
                    {organization.name}
                  </option>
                ))}
              </Select>
            </AdminFilterField>
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
      />
      <ConfirmDialog
        open={confirmMode !== null}
        title={
          confirmMode === 'discover' ? 'Discover categories' : 'Verify categories'
        }
        message={
          confirmMode === 'discover'
            ? `${discoverLabels} unknown ${
                discoverLabels === 1 ? 'label' : 'labels'
              } across ${discoverActivities} ${
                discoverActivities === 1 ? 'activity' : 'activities'
              } in ${discoverBatches} model ${
                discoverBatches === 1 ? 'call' : 'calls'
              }. Existing matches are assigned now. ${thresholdText}`
            : `${
                candidates > scanCount
                  ? `Scan ${scanCount} of ${candidates} activities`
                  : `Scan ${scanCount} activities`
              } in ${batches} model ${batches === 1 ? 'call' : 'calls'}. ${thresholdText}`
        }
        confirmLabel='Start scan'
        confirmLoading={isStarting}
        confirmLoadingLabel='Starting…'
        onConfirm={() => {
          if (confirmMode) {
            void startScan(confirmMode);
          }
        }}
        onCancel={() => setConfirmMode(null)}
      />
    </div>
  );
}
