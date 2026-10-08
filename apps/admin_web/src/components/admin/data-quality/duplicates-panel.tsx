'use client';

import { useQuery } from '@tanstack/react-query';
import { useQueryState } from 'nuqs';
import { useRef, useState } from 'react';

import { useExpandedRecord } from '../../../hooks/use-expanded-record';
import { usePaginatedList } from '../../../hooks/use-paginated-list';
import { adminQueryKeys } from '../../../lib/admin-query-keys';
import {
  dismissOrgDuplicates,
  getOrgDuplicate,
  listOrgDuplicates,
  type OrgDuplicateGroup,
} from '../../../lib/api-client-data-quality';
import { ApiError } from '../../../lib/api-client';
import { StatusBanner } from '../../status-banner';
import { AdminDataTableCell, AdminDataTableHeadCell } from '../../ui/admin-data-table';
import { AdminEditorPanel } from '../../ui/admin-editor-panel';
import { AdminFilterBar, AdminFilterField } from '../../ui/admin-filter-bar';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { ResourceTableShell } from '../../ui/resource-table-shell';
import { Select } from '../../ui/select';
import { OrganizationMergeEditor } from './organization-merge-editor';

interface DuplicateFilters {
  q: string;
  matchSignal: string;
  review_status: string;
}

const DEFAULT_FILTERS: DuplicateFilters = {
  q: '',
  matchSignal: '',
  review_status: '',
};

export function DuplicatesPanel() {
  const [organization, setOrganization] = useQueryState('organization');
  const orgIdRef = useRef(organization);
  orgIdRef.current = organization;
  const expanded = useExpandedRecord({ paramName: 'duplicate' });
  const list = usePaginatedList<OrgDuplicateGroup, DuplicateFilters>({
    queryKey: [...adminQueryKeys.orgDuplicates(), organization ?? ''],
    defaultFilters: DEFAULT_FILTERS,
    debounceKeys: ['q'],
    errorPrefix: 'Failed to load duplicates',
    fetcher: async ({ cursor, limit, q, matchSignal, review_status }) => {
      const page = await listOrgDuplicates({
        cursor: cursor ?? undefined,
        limit,
        q: q || undefined,
        signal: matchSignal || undefined,
        review_status: review_status || undefined,
        org_id: orgIdRef.current || undefined,
      });
      return { items: page.items, nextCursor: page.next_cursor ?? null };
    },
  });
  const [error, setError] = useState('');
  const [isDismissing, setIsDismissing] = useState(false);
  const listed = list.items.find((item) => item.id === expanded.expandedId) ?? null;
  const detailQuery = useQuery({
    queryKey: ['admin', 'org-duplicates', 'one', expanded.expandedId],
    queryFn: () => getOrgDuplicate(expanded.expandedId as string),
    enabled: Boolean(expanded.expandedId) && !list.isLoading && listed === null,
  });
  const open = listed ?? detailQuery.data ?? null;

  async function dismiss(group: OrgDuplicateGroup) {
    setIsDismissing(true);
    setError('');
    try {
      await dismissOrgDuplicates(group.organizations.map((org) => org.id));
      expanded.collapse();
      await list.refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not dismiss this group.');
    } finally {
      setIsDismissing(false);
    }
  }

  return (
    <div className='space-y-4'>
      <h2 className='sr-only'>Duplicates</h2>
      <p className='text-sm text-slate-600'>
        Groups share a name, phone, email, source id, or a similar spelling.
        Merging keeps one organization, moves its locations and activities, and
        sends later imports of the removed source id or place id to the survivor.
      </p>
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
      {error ? (
        <StatusBanner kind='error'>
          {error}
        </StatusBanner>
      ) : null}
      <ResourceTableShell
        ariaLabel='Duplicate organizations'
        rows={list.items}
        getLabel={(item) => item.organizations.map((org) => org.name).join(', ')}
        middleColumnCount={3}
        hasActions={false}
        isLoading={list.isLoading}
        isLoadingMore={list.isLoadingMore}
        hasMore={list.hasMore}
        onLoadMore={() => {
          void list.loadMore();
        }}
        error={list.error}
        emptyLabel='No duplicate organizations match these filters.'
        isExpanded={expanded.isExpanded}
        onToggle={expanded.toggle}
        detail={
          open ? (
            <AdminEditorPanel>
              <OrganizationMergeEditor
                key={`${open.organizations.map((org) => org.id).join(',')}:${open.suggested_survivor_id}`}
                organizations={open.organizations}
                suggestedSurvivorId={open.suggested_survivor_id}
                onMerged={() => {
                  expanded.collapse();
                  void list.refetch();
                }}
              />
              <Button
                type='button'
                variant='secondary'
                onClick={() => void dismiss(open)}
                loading={isDismissing}
                loadingLabel='Saving…'
              >
                Not duplicates
              </Button>
            </AdminEditorPanel>
          ) : null
        }
        filters={
          <AdminFilterBar>
            <AdminFilterField label='Name' htmlFor='duplicate-name-filter'>
              <Input
                id='duplicate-name-filter'
                value={list.filters.q}
                onChange={(event) => list.setFilter('q', event.target.value)}
              />
            </AdminFilterField>
            <AdminFilterField label='Signal' htmlFor='duplicate-signal-filter'>
              <Select
                id='duplicate-signal-filter'
                value={list.filters.matchSignal}
                onChange={(event) => list.setFilter('matchSignal', event.target.value)}
              >
                <option value=''>Any</option>
                <option value='name'>Name</option>
                <option value='phone'>Phone</option>
                <option value='email'>Email</option>
                <option value='source_id'>Source id</option>
                <option value='social'>Social</option>
                <option value='website'>Website</option>
                <option value='translation'>Translation</option>
              </Select>
            </AdminFilterField>
            <AdminFilterField label='Review' htmlFor='duplicate-review-filter'>
              <Select
                id='duplicate-review-filter'
                value={list.filters.review_status}
                onChange={(event) => list.setFilter('review_status', event.target.value)}
              >
                <option value=''>Any</option>
                <option value='pending_review'>Pending review</option>
                <option value='approved'>Approved</option>
                <option value='rejected'>Rejected</option>
              </Select>
            </AdminFilterField>
          </AdminFilterBar>
        }
        head={
          <>
            <AdminDataTableHeadCell>Names</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>Score</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>Signals</AdminDataTableHeadCell>
          </>
        }
        renderCells={(item) => (
          <>
            <AdminDataTableCell>
              {item.organizations.map((org) => org.name).join(' · ')}
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>{item.score}</AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {item.signals.join(', ')}
            </AdminDataTableCell>
          </>
        )}
      />
    </div>
  );
}
