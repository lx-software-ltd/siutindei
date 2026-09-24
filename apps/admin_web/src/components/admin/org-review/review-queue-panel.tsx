'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQueryState } from 'nuqs';

import { ApiError } from '../../../lib/api-client';
import {
  bulkOrgReview,
  getOrgReviewDetail,
  getOrgReviewSummary,
  listOrgReviews,
  type OrgReviewDetail,
  type OrgReviewListItem,
  type OrgReviewSummary,
} from '../../../lib/api-client-org-review';
import { StatusBanner } from '../../status-banner';
import { Button } from '../../ui/button';
import { Card } from '../../ui/card';
import { DataTable } from '../../ui/data-table';
import { Input } from '../../ui/input';
import { Label } from '../../ui/label';
import { Select } from '../../ui/select';
import { StatusBadge } from '../../ui/status-badge';
import { BulkFieldsDialog } from './bulk-fields-dialog';

const ISSUE_OPTIONS = [
  ['', 'Any issue'],
  ['missing_description', 'Missing description'],
  ['no_locations', 'No locations'],
  ['no_activities', 'No activities'],
  ['missing_coordinates', 'Missing map pin'],
  ['missing_pricing', 'Missing price'],
  ['missing_schedule', 'Missing schedule'],
  ['no_contact', 'No contact'],
  ['no_media', 'No photos'],
  ['source_attribution', 'Import note in description'],
];

function sectionForIssue(entityType: string) {
  if (entityType === 'location') {
    return 'locations';
  }
  if (entityType === 'activity') {
    return 'activities';
  }
  return 'organizations';
}

export function ReviewQueuePanel() {
  const [jobParam, setJobParam] = useQueryState('job');
  const [, setSection] = useQueryState('section');
  const [, setEdit] = useQueryState('edit');
  const [reviewStatus, setReviewStatus] = useState('pending_review');
  const [sourceInput, setSourceInput] = useState('');
  const [source, setSource] = useState('');
  const [issue, setIssue] = useState('');
  const [hasBlockers, setHasBlockers] = useState('');
  const [queryInput, setQueryInput] = useState('');
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<'name' | 'last_imported_at'>('name');
  const summaryLoaded = useRef(false);
  const [items, setItems] = useState<OrgReviewListItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [summary, setSummary] = useState<OrgReviewSummary | null>(null);
  const [detail, setDetail] = useState<OrgReviewDetail | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [force, setForce] = useState(false);
  const [showFields, setShowFields] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  const filters = useMemo(
    () => ({
      review_status: reviewStatus || undefined,
      source: source || undefined,
      issue: issue || undefined,
      has_blockers:
        hasBlockers === '' ? undefined : hasBlockers === 'true',
      q: query || undefined,
      import_job_id: jobParam || undefined,
      sort: sort === 'last_imported_at' ? sort : undefined,
      limit: 50,
    }),
    [hasBlockers, issue, jobParam, query, reviewStatus, sort, source]
  );

  const load = useCallback(
    async (cursor?: string, refreshSummary = false) => {
      setIsLoading(true);
      setError('');
      const shouldLoadSummary = refreshSummary || !summaryLoaded.current;
      try {
        const [page, counts] = await Promise.all([
          listOrgReviews({ ...filters, cursor }),
          shouldLoadSummary ? getOrgReviewSummary() : Promise.resolve(null),
        ]);
        setItems((prev) => (cursor ? [...prev, ...page.items] : page.items));
        setNextCursor(page.next_cursor ?? null);
        if (counts) {
          setSummary(counts);
          summaryLoaded.current = true;
        }
        if (!cursor) {
          setSelected(new Set());
        }
      } catch (err) {
        setError(
          err instanceof ApiError ? err.message : 'Failed to load the review queue.'
        );
      } finally {
        setIsLoading(false);
      }
    },
    [filters]
  );

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setSource(sourceInput);
      setQuery(queryInput);
    }, 300);
    return () => window.clearTimeout(handle);
  }, [queryInput, sourceInput]);

  function commitTextFilters() {
    setSource(sourceInput);
    setQuery(queryInput);
  }

  useEffect(() => {
    void load();
  }, [load]);

  async function openDetail(item: OrgReviewListItem) {
    setError('');
    try {
      setDetail(await getOrgReviewDetail(item.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load details.');
    }
  }

  async function runBulk(
    action: 'approve' | 'reject' | 'reopen' | 'set_fields',
    fields?: Record<string, string>
  ) {
    const orgIds = Array.from(selected);
    if (orgIds.length === 0) {
      setError('Select at least one organization.');
      return;
    }
    setIsSaving(true);
    setError('');
    setNotice('');
    try {
      const response = await bulkOrgReview({
        org_ids: orgIds,
        action,
        force: action === 'approve' ? force : undefined,
        fields,
      });
      const blocked = response.results.filter((item) => item.status === 'blocked');
      const failed = response.results.filter((item) => item.status === 'error');
      const ok = response.results.filter((item) => item.status === 'ok');
      setNotice(
        `Updated ${ok.length}. ${blocked.length} still missing details. ${failed.length} failed.`
      );
      setShowFields(false);
      await load(undefined, true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Bulk update failed.');
    } finally {
      setIsSaving(false);
    }
  }

  const pendingCount = summary?.by_review_status.pending_review ?? 0;

  return (
    <div className='space-y-6'>
      <Card
        title='Review queue'
        description={
          'Imported organizations stay pending until you release them. ' +
          'Public search keeps the current listings until ORG_REVIEW_GATE_ENABLED ' +
          'is turned on. After a release, search can stay cached for up to 5 minutes.'
        }
      >
        <div className='space-y-4'>
          {error && (
            <StatusBanner variant='error' title='Review queue'>
              {error}
            </StatusBanner>
          )}
          {notice && (
            <StatusBanner variant='info' title='Bulk result'>
              {notice}
            </StatusBanner>
          )}
          <div className='grid gap-3 sm:grid-cols-3'>
            <div className='rounded-lg border border-slate-200 p-3'>
              <p className='text-xs text-slate-500'>Pending review</p>
              <p className='text-2xl font-semibold text-slate-900'>{pendingCount}</p>
            </div>
            <div className='rounded-lg border border-slate-200 p-3'>
              <p className='text-xs text-slate-500'>With missing details</p>
              <p className='text-2xl font-semibold text-slate-900'>
                {summary?.with_blockers ?? 0}
              </p>
            </div>
            <div className='rounded-lg border border-slate-200 p-3'>
              <p className='text-xs text-slate-500'>Approved</p>
              <p className='text-2xl font-semibold text-slate-900'>
                {summary?.by_review_status.approved ?? 0}
              </p>
            </div>
          </div>
          <div className='grid gap-3 md:grid-cols-3'>
            <div className='space-y-1'>
              <Label htmlFor='review-status-filter'>Review</Label>
              <Select
                id='review-status-filter'
                value={reviewStatus}
                onChange={(event) => setReviewStatus(event.target.value)}
              >
                <option value=''>All</option>
                <option value='pending_review'>Pending review</option>
                <option value='approved'>Approved</option>
                <option value='rejected'>Rejected</option>
              </Select>
            </div>
            <div className='space-y-1'>
              <Label htmlFor='review-issue-filter'>Missing detail</Label>
              <Select
                id='review-issue-filter'
                value={issue}
                onChange={(event) => setIssue(event.target.value)}
              >
                {ISSUE_OPTIONS.map(([value, label]) => (
                  <option key={value || 'any'} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </div>
            <div className='space-y-1'>
              <Label htmlFor='review-blocker-filter'>Blockers</Label>
              <Select
                id='review-blocker-filter'
                value={hasBlockers}
                onChange={(event) => setHasBlockers(event.target.value)}
              >
                <option value=''>Any</option>
                <option value='true'>Has blockers</option>
                <option value='false'>No blockers</option>
              </Select>
            </div>
            <div className='space-y-1'>
              <Label htmlFor='review-source-filter'>Source</Label>
              <Input
                id='review-source-filter'
                value={sourceInput}
                placeholder='lcsd'
                onChange={(event) => setSourceInput(event.target.value)}
                onBlur={commitTextFilters}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    commitTextFilters();
                  }
                }}
              />
            </div>
            <div className='space-y-1'>
              <Label htmlFor='review-name-filter'>Name</Label>
              <Input
                id='review-name-filter'
                value={queryInput}
                onChange={(event) => setQueryInput(event.target.value)}
                onBlur={commitTextFilters}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    commitTextFilters();
                  }
                }}
              />
            </div>
            <div className='space-y-1'>
              <Label htmlFor='review-sort'>Sort</Label>
              <Select
                id='review-sort'
                value={sort}
                onChange={(event) =>
                  setSort(
                    event.target.value === 'last_imported_at'
                      ? 'last_imported_at'
                      : 'name'
                  )
                }
              >
                <option value='name'>Name</option>
                <option value='last_imported_at'>Recently imported</option>
              </Select>
            </div>
            {jobParam && (
              <div className='flex items-end'>
                <Button
                  type='button'
                  variant='secondary'
                  onClick={() => {
                    void setJobParam(null);
                  }}
                >
                  Clear import filter
                </Button>
              </div>
            )}
          </div>
          <div className='flex flex-wrap items-center gap-2'>
            <Button
              type='button'
              onClick={() => void runBulk('approve')}
              disabled={isSaving || selected.size === 0}
            >
              Approve
            </Button>
            <Button
              type='button'
              variant='secondary'
              onClick={() => void runBulk('reject')}
              disabled={isSaving || selected.size === 0}
            >
              Reject
            </Button>
            <Button
              type='button'
              variant='secondary'
              onClick={() => void runBulk('reopen')}
              disabled={isSaving || selected.size === 0}
            >
              Reopen
            </Button>
            <Button
              type='button'
              variant='secondary'
              onClick={() => setShowFields((prev) => !prev)}
              disabled={selected.size === 0}
            >
              Apply properties
            </Button>
            <label className='flex items-center gap-2 text-sm text-slate-700'>
              <input
                type='checkbox'
                checked={force}
                onChange={(event) => setForce(event.target.checked)}
              />
              Release even when details are missing
            </label>
          </div>
          {showFields && (
            <BulkFieldsDialog
              isSaving={isSaving}
              onCancel={() => setShowFields(false)}
              onInvalid={(message) => setError(message)}
              onApply={(fields) => {
                if (Object.keys(fields).length === 0) {
                  setError('Tick at least one property.');
                  return;
                }
                void runBulk('set_fields', fields);
              }}
            />
          )}
          {isLoading && items.length === 0 ? (
            <p className='text-sm text-slate-600'>Loading organizations...</p>
          ) : (
            <DataTable
              columns={[
                {
                  key: 'name',
                  header: 'Name',
                  primary: true,
                  render: (item: OrgReviewListItem) => item.name,
                },
                {
                  key: 'source',
                  header: 'Source',
                  secondary: true,
                  render: (item: OrgReviewListItem) => item.source || '—',
                },
                {
                  key: 'review',
                  header: 'Review',
                  render: (item: OrgReviewListItem) => (
                    <StatusBadge
                      status={item.review_status.replaceAll('_', ' ')}
                    />
                  ),
                },
                {
                  key: 'issues',
                  header: 'Missing',
                  render: (item: OrgReviewListItem) =>
                    item.issues.length === 0
                      ? 'Ready'
                      : item.issues
                          .slice(0, 3)
                          .map((entry) => entry.message)
                          .join('; '),
                },
                {
                  key: 'completeness',
                  header: 'Complete',
                  render: (item: OrgReviewListItem) =>
                    `${Math.round(item.completeness * 100)}%`,
                },
              ]}
              data={items}
              keyExtractor={(item) => item.id}
              selectable
              selectedKeys={selected}
              onToggleRow={(key) => {
                setSelected((prev) => {
                  const next = new Set(prev);
                  if (next.has(key)) {
                    next.delete(key);
                  } else {
                    next.add(key);
                  }
                  return next;
                });
              }}
              onToggleAll={(keys, isSelected) => {
                setSelected((prev) => {
                  const next = new Set(prev);
                  keys.forEach((key) => {
                    if (isSelected) {
                      next.add(key);
                    } else {
                      next.delete(key);
                    }
                  });
                  return next;
                });
              }}
              onEdit={(item) => {
                void openDetail(item);
              }}
              nextCursor={nextCursor}
              onLoadMore={() => {
                if (nextCursor) {
                  void load(nextCursor);
                }
              }}
              isLoading={isLoading}
              emptyMessage='No organizations match these filters.'
            />
          )}
        </div>
      </Card>
      {detail && (
        <Card
          title={detail.name}
          description='Fix a row by opening the record, then come back and approve.'
        >
          <ul className='space-y-2 text-sm text-slate-700'>
            {detail.issues.length === 0 && <li>Nothing is missing.</li>}
            {detail.issues.map((entry) => (
              <li key={`${entry.entity_id}-${entry.code}`}>
                <span className='font-medium'>{entry.message}</span>
                <button
                  type='button'
                  className='ml-2 text-slate-900 underline'
                  onClick={() => {
                    void setSection(sectionForIssue(entry.entity_type));
                    void setEdit(entry.entity_id);
                  }}
                >
                  Fix
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
