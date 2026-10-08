'use client';

import { useEffect, useState, type ReactNode } from 'react';

import { useExpandedRecord } from '../../../hooks/use-expanded-record';
import {
  decideCategoryReview,
  getCategoryReview,
  type ActivityCategoryReview,
} from '../../../lib/api-client-category-suggestions';
import { canApplyReview } from './category-checks-bulk';
import { DeleteIcon, EditIcon, ReviewIcon } from '../../icons/action-icons';
import { AdminEditorPanel } from '../../ui/admin-editor-panel';
import {
  AdminDataTableCell,
  AdminDataTableHeadCell,
} from '../../ui/admin-data-table';
import { AdminRowActions } from '../../ui/admin-row-actions';
import { ResourceTableShell } from '../../ui/resource-table-shell';
import { StatusBadge } from '../../ui/status-badge';

interface CategoryChecksTableProps {
  items: ActivityCategoryReview[];
  isLoading: boolean;
  isLoadingMore?: boolean;
  error?: string;
  hasMore?: boolean;
  onLoadMore?: () => void;
  onReload: () => void;
  filters?: ReactNode;
  toolbar?: ReactNode;
}

export function CategoryChecksTable({
  items,
  isLoading,
  isLoadingMore = false,
  error = '',
  hasMore = false,
  onLoadMore,
  onReload,
  filters,
  toolbar,
}: CategoryChecksTableProps) {
  const expanded = useExpandedRecord({ paramName: 'category-check' });
  const openInList = items.some((item) => item.id === expanded.expandedId);
  const detail = expanded.expandedId ? (
    <CheckDetail
      key={expanded.expandedId}
      reviewId={expanded.expandedId}
      fallback={items.find((item) => item.id === expanded.expandedId) ?? null}
    />
  ) : null;

  return (
    <div className='space-y-4'>
      <ResourceTableShell
        ariaLabel='Category Checks'
        rows={items}
        getLabel={(item) => item.activity_name || item.activity_id}
        middleColumnCount={5}
        isLoading={isLoading}
        isLoadingMore={isLoadingMore}
        hasMore={hasMore}
        onLoadMore={onLoadMore}
        error={error}
        emptyLabel='No category checks yet.'
        isExpanded={expanded.isExpanded}
        onToggle={expanded.toggle}
        detail={openInList ? detail : null}
        filters={filters}
        toolbar={toolbar}
        renderActions={(item) => (
          <ReviewActions item={item} onReload={onReload} />
        )}
        head={
          <>
            <AdminDataTableHeadCell>Activity</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>
              Organization
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>
              Category
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>
              Verdict
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>
              Status
            </AdminDataTableHeadCell>
          </>
        }
        renderCells={(item) => (
          <>
            <AdminDataTableCell>
              <span className='font-medium'>
                {item.activity_name || item.activity_id}
              </span>
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {item.org_name || '—'}
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {item.current_category_name || '—'}
              {' → '}
              {item.proposed_category_name || '—'}
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              {item.verdict}
              {item.confidence != null ? ` ${item.confidence}` : ''}
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              <StatusBadge status={item.status.replace(/_/g, ' ')} />
            </AdminDataTableCell>
          </>
        )}
      />
      {expanded.expandedId && !openInList && !isLoading ? detail : null}
    </div>
  );
}

function ReviewActions({
  item,
  onReload,
}: {
  item: ActivityCategoryReview;
  onReload: () => void;
}) {
  const [pending, setPending] = useState('');

  async function decide(action: 'apply' | 'dismiss' | 'revert') {
    setPending(action);
    try {
      await decideCategoryReview(item.id, { action });
      onReload();
    } finally {
      setPending('');
    }
  }

  const isPending = item.status === 'pending';
  const canApply = isPending && canApplyReview(item);
  const canRevert = item.status === 'auto_applied' || item.status === 'applied';
  return (
    <AdminRowActions
      actions={[
        {
          key: 'apply',
          label: pending === 'apply' ? 'Applying…' : 'Apply',
          icon: <EditIcon className='h-4 w-4' />,
          hidden: !canApply,
          disabled: pending !== '',
          onClick: () => void decide('apply'),
        },
        {
          key: 'dismiss',
          label: 'Dismiss',
          icon: <DeleteIcon className='h-4 w-4' />,
          hidden: !isPending,
          disabled: pending !== '',
          onClick: () => void decide('dismiss'),
        },
        {
          key: 'revert',
          label: 'Revert',
          icon: <ReviewIcon className='h-4 w-4' />,
          hidden: !canRevert,
          disabled: pending !== '',
          onClick: () => void decide('revert'),
        },
      ]}
    />
  );
}

function CheckDetail({
  reviewId,
  fallback,
}: {
  reviewId: string;
  fallback: ActivityCategoryReview | null;
}) {
  const [item, setItem] = useState<ActivityCategoryReview | null>(fallback);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    getCategoryReview(reviewId)
      .then((row) => {
        if (!cancelled) {
          setItem(row);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [reviewId]);

  if (!item) {
    return (
      <AdminEditorPanel>
        <p className='text-sm text-slate-600'>
          {error || 'Loading category check.'}
        </p>
      </AdminEditorPanel>
    );
  }

  return (
    <AdminEditorPanel>
      <p className='text-sm text-slate-700'>{item.rationale || 'No rationale.'}</p>
      {item.suggestion_id ? (
        <p className='text-sm text-slate-600'>
          Suggested category is waiting in Category Suggestions.
        </p>
      ) : null}
      {error ? <p className='text-sm text-red-600'>{error}</p> : null}
    </AdminEditorPanel>
  );
}
