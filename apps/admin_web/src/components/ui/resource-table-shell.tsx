'use client';

import type { ReactNode } from 'react';

import { DeleteIcon } from '@/components/icons/action-icons';
import { DRAFT_RECORD_ID } from '@/hooks/use-expanded-record';

import {
  AdminDataTableCell,
  AdminDataTableHeadCell,
  AdminDataTableOperationsHeadCell,
} from './admin-data-table';
import { AdminExpandableRow } from './admin-expandable-row';
import { AdminRecordTable } from './admin-record-table';
import { AdminRowActions, type AdminRowAction } from './admin-row-actions';

/** One danger Delete control for an Operations cell. */
export function deleteRowActions(onDelete: () => void): ReactNode {
  return (
    <AdminRowActions
      actions={[
        {
          key: 'delete',
          label: 'Delete',
          tone: 'danger',
          icon: <DeleteIcon className='h-4 w-4' />,
          onClick: () => {
            onDelete();
          },
        },
      ]}
    />
  );
}

export function rowActions(actions: AdminRowAction[]): ReactNode {
  return <AdminRowActions actions={actions} />;
}

export interface ResourceTableShellProps<T extends { id: string }> {
  ariaLabel: string;
  filters?: ReactNode;
  toolbar?: ReactNode;
  /** Header cells between the expand column and Operations. */
  head: ReactNode;
  /** Body cells matching `head`, for one existing row. */
  renderCells: (item: T) => ReactNode;
  renderActions?: (item: T) => ReactNode;
  /** Shared editor. Mounted only inside the open row. */
  detail: ReactNode;
  rows: T[];
  getLabel: (item: T) => string;
  middleColumnCount: number;
  hasActions?: boolean;
  isLoading: boolean;
  isLoadingMore?: boolean;
  hasMore?: boolean;
  onLoadMore?: () => void | Promise<void>;
  error?: string;
  emptyLabel?: string;
  isExpanded: (id: string) => boolean;
  onToggle: (id: string) => void;
  isDraftOpen?: boolean;
  draftLabel?: string;
  onToggleDraft?: () => void;
  /** Checkbox (or other control) rendered before the chevron. */
  renderLeading?: (item: T) => ReactNode;
  draftLeading?: ReactNode;
  leadingHead?: ReactNode;
}

/**
 * Record table with an optional draft row and one expanded editor.
 * Column order: optional leading, expand chevron, caller cells, Operations.
 */
export function ResourceTableShell<T extends { id: string }>({
  ariaLabel,
  filters,
  toolbar,
  head,
  renderCells,
  renderActions,
  detail,
  rows,
  getLabel,
  middleColumnCount,
  hasActions = true,
  isLoading,
  isLoadingMore,
  hasMore,
  onLoadMore,
  error,
  emptyLabel,
  isExpanded,
  onToggle,
  isDraftOpen = false,
  draftLabel = 'New record',
  onToggleDraft,
  renderLeading,
  draftLeading,
  leadingHead,
}: ResourceTableShellProps<T>) {
  const hasLeading = Boolean(renderLeading || leadingHead);
  const columnCount =
    (hasLeading ? 1 : 0) + 1 + middleColumnCount + (hasActions ? 1 : 0);

  const draftCells = Array.from({ length: middleColumnCount }, (_, index) => (
    <AdminDataTableCell key={index}>
      {index === 0 ? draftLabel : ''}
    </AdminDataTableCell>
  ));

  return (
    <AdminRecordTable
      aria-label={ariaLabel}
      filters={filters}
      toolbar={toolbar}
      columnCount={columnCount}
      rowCount={rows.length + (isDraftOpen ? 1 : 0)}
      isLoading={isLoading}
      isLoadingMore={isLoadingMore}
      hasMore={hasMore}
      onLoadMore={onLoadMore}
      error={error}
      emptyLabel={emptyLabel}
      head={
        <>
          {hasLeading ? (
            <AdminDataTableHeadCell className='w-10'>
              {leadingHead}
            </AdminDataTableHeadCell>
          ) : null}
          <AdminDataTableHeadCell className='w-10'>
            <span className='sr-only'>Expand</span>
          </AdminDataTableHeadCell>
          {head}
          {hasActions ? <AdminDataTableOperationsHeadCell /> : null}
        </>
      }
    >
      {isDraftOpen ? (
        <AdminExpandableRow
          id={DRAFT_RECORD_ID}
          label={draftLabel}
          expanded
          isDraft
          onToggle={() => onToggleDraft?.()}
          columnCount={columnCount}
          leading={hasLeading ? draftLeading : undefined}
          cells={draftCells}
          actions={hasActions ? null : undefined}
          detail={detail}
        />
      ) : null}
      {rows.map((item) => {
        const open = isExpanded(item.id);
        return (
          <AdminExpandableRow
            key={item.id}
            id={item.id}
            label={getLabel(item)}
            expanded={open}
            onToggle={() => onToggle(item.id)}
            columnCount={columnCount}
            leading={hasLeading ? renderLeading?.(item) : undefined}
            cells={renderCells(item)}
            actions={hasActions ? renderActions?.(item) ?? null : undefined}
            detail={open ? detail : null}
          />
        );
      })}
    </AdminRecordTable>
  );
}
