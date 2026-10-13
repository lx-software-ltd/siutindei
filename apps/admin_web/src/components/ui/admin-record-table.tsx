'use client';

import { useEffect, useRef, type ReactNode } from 'react';

import { clsx } from 'clsx';

import { AdminDataTableBody, AdminDataTableCell, AdminDataTableHead } from './admin-data-table';
import { AdminSkeletonRows } from './admin-skeleton';
import { Button } from './button';
import { Card } from './card';

export interface AdminRecordTableProps {
  /** Left-aligned `AdminFilterBar` fields. Omit when there are no filters. */
  filters?: ReactNode;
  /** Left-aligned create / sweep / bulk buttons. Omit when there are none. */
  actions?: ReactNode;
  /** Header `<tr>`; start with `<AdminDataTableHeadCell />` for the expand column. */
  head: ReactNode;
  /** Body rows, normally `AdminExpandableRow` elements (draft row first). */
  children: ReactNode;
  /** Number of `<td>` cells per row; drives skeleton and empty-state spans. */
  columnCount: number;
  /** Rendered rows (excluding a draft row); used to pick skeleton vs empty state. */
  rowCount: number;
  isLoading: boolean;
  isLoadingMore?: boolean;
  hasMore?: boolean;
  onLoadMore?: () => void | Promise<void>;
  emptyLabel?: string;
  /**
   * Extra classes on the `<table>`. Do not pass min-w-*; the scroll
   * container handles overflow.
   */
  tableClassName?: string;
  /**
   * Render without the white card. For nested record tables inside an open
   * editor (notes, members), whose parent already provides the card.
   */
  embedded?: boolean;
  'aria-label': string;
}

/**
 * Table-first listing: an untitled white card with optional filters,
 * optional left-aligned actions, the table, and optional Load more.
 */
export function AdminRecordTable({
  filters,
  actions,
  head,
  children,
  columnCount,
  rowCount,
  isLoading,
  isLoadingMore = false,
  hasMore = false,
  onLoadMore,
  emptyLabel = 'No records match the current filters.',
  tableClassName,
  embedded = false,
  'aria-label': ariaLabel,
}: AdminRecordTableProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const element = scrollRef.current;
    if (!element || typeof ResizeObserver === 'undefined') {
      return;
    }
    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width;
      if (width) {
        element.style.setProperty('--admin-table-viewport', `${Math.floor(width)}px`);
      }
    });
    observer.observe(element);
    return () => {
      observer.disconnect();
    };
  }, []);

  const showSkeleton = isLoading && rowCount === 0;
  const showEmpty = !isLoading && !isLoadingMore && rowCount === 0;

  const Shell = embedded ? 'section' : Card;

  return (
    <Shell data-testid='admin-record-table' data-embedded={embedded ? 'true' : undefined}>
      {filters}
      {actions ? (
        <div
          className='mb-3 flex flex-wrap items-center justify-start gap-2'
          data-testid='admin-record-table-actions'
        >
          {actions}
        </div>
      ) : null}
      <div
        ref={scrollRef}
        className='admin-record-table-scroll overflow-x-auto rounded-md border border-slate-200 bg-white'
        aria-busy={isLoading || isLoadingMore ? true : undefined}
      >
        <table
          aria-label={ariaLabel}
          className={clsx('w-full divide-y divide-slate-200 text-left', tableClassName)}
        >
          <AdminDataTableHead>
            <tr>{head}</tr>
          </AdminDataTableHead>
          <AdminDataTableBody>
            {children}
            {showSkeleton ? <AdminSkeletonRows columnCount={columnCount} /> : null}
            {showEmpty ? (
              <tr>
                <AdminDataTableCell colSpan={columnCount} className='py-8 text-center text-slate-500'>
                  {emptyLabel}
                </AdminDataTableCell>
              </tr>
            ) : null}
          </AdminDataTableBody>
        </table>
      </div>
      {isLoading && rowCount > 0 ? (
        <p className='sr-only' role='status'>
          Refreshing...
        </p>
      ) : null}
      {hasMore && onLoadMore ? (
        <div className='mt-3'>
          <Button
            type='button'
            variant='outline'
            onClick={() => void onLoadMore()}
            loading={isLoadingMore}
            loadingLabel='Loading…'
          >
            Load more
          </Button>
        </div>
      ) : null}
    </Shell>
  );
}
