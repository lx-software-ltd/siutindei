'use client';

import type { ReactNode } from 'react';

import { DeleteIcon } from '../icons/action-icons';
import { Button } from './button';

export interface DataTableColumn<T> {
  key: string;
  header: ReactNode;
  render: (item: T) => ReactNode;
  headerClassName?: string;
  cellClassName?: string;
  /** Hide this column on mobile card view */
  hideOnMobile?: boolean;
  /** Use as primary label in mobile card view */
  primary?: boolean;
  /** Use as secondary label in mobile card view */
  secondary?: boolean;
}

export interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  data: T[];
  keyExtractor: (item: T) => string;
  onEdit?: (item: T) => void;
  onDelete?: (item: T) => void;
  renderActions?: (item: T, context: 'desktop' | 'mobile') => ReactNode;
  actionsHeader?: ReactNode;
  nextCursor?: string | null;
  onLoadMore?: () => void;
  isLoading?: boolean;
  emptyMessage?: string;
  selectable?: boolean;
  selectedKeys?: ReadonlySet<string>;
  onToggleRow?: (key: string) => void;
  onToggleAll?: (keys: string[], selected: boolean) => void;
}

export function DataTable<T>({
  columns,
  data,
  keyExtractor,
  onEdit,
  onDelete,
  renderActions,
  actionsHeader = 'Actions',
  nextCursor,
  onLoadMore,
  isLoading,
  emptyMessage = 'No items found.',
  selectable = false,
  selectedKeys,
  onToggleRow,
  onToggleAll,
}: DataTableProps<T>) {
  if (data.length === 0) {
    return <p className='text-sm text-slate-600'>{emptyMessage}</p>;
  }

  const primaryColumn = columns.find((c) => c.primary);
  const secondaryColumn = columns.find((c) => c.secondary);
  const detailColumns = columns.filter(
    (c) => !c.primary && !c.secondary && !c.hideOnMobile
  );
  const isRowEditable = Boolean(onEdit);
  const hasActions = Boolean(onDelete || renderActions);
  const rowKeys = data.map((item) => keyExtractor(item));
  const allSelected =
    selectable &&
    rowKeys.length > 0 &&
    rowKeys.every((key) => selectedKeys?.has(key));

  return (
    <>
      {/* Desktop table view */}
      <div className='hidden overflow-x-auto md:block'>
        <table className='w-full text-left text-sm'>
          <thead className='border-b border-slate-200 text-slate-500'>
            <tr>
              {selectable && (
                <th className='w-10 py-2 pr-2'>
                  <input
                    type='checkbox'
                    aria-label='Select all rows'
                    checked={allSelected}
                    onChange={(event) => {
                      onToggleAll?.(rowKeys, event.target.checked);
                    }}
                  />
                </th>
              )}
              {columns.map((column) => (
                <th
                  key={column.key}
                  className={`py-2 pr-4 last:pr-0${
                    column.headerClassName ? ` ${column.headerClassName}` : ''
                  }`}
                >
                  {column.header}
                </th>
              ))}
              {hasActions && (
                <th className='py-2 text-right'>{actionsHeader}</th>
              )}
            </tr>
          </thead>
          <tbody>
            {data.map((item) => (
              <tr
                key={keyExtractor(item)}
                className={`border-b border-slate-100${
                  isRowEditable ? ' cursor-pointer hover:bg-slate-50' : ''
                }`}
                onClick={
                  onEdit
                    ? () => {
                        onEdit(item);
                      }
                    : undefined
                }
              >
                {selectable && (
                  <td
                    className='py-2 pr-2'
                    onClick={(event) => {
                      event.stopPropagation();
                    }}
                  >
                    <input
                      type='checkbox'
                      aria-label='Select row'
                      checked={selectedKeys?.has(keyExtractor(item)) ?? false}
                      onChange={() => {
                        onToggleRow?.(keyExtractor(item));
                      }}
                    />
                  </td>
                )}
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={`py-2 pr-4 last:pr-0${
                      column.cellClassName ? ` ${column.cellClassName}` : ''
                    }`}
                  >
                    {column.render(item)}
                  </td>
                ))}
                {hasActions && (
                  <td
                    className='py-2 text-right'
                    onClick={(event) => {
                      event.stopPropagation();
                    }}
                  >
                    <div className='flex justify-end gap-2'>
                      {renderActions ? renderActions(item, 'desktop') : null}
                      {onDelete && (
                        <Button
                          type='button'
                          size='sm'
                          variant='danger'
                          onClick={() => onDelete(item)}
                          title='Delete'
                          aria-label='Delete'
                        >
                          <DeleteIcon className='h-4 w-4' />
                        </Button>
                      )}
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile card view */}
      <div className='space-y-3 md:hidden'>
        {data.map((item) => (
          <div
            key={keyExtractor(item)}
            className={`rounded-lg border border-slate-200 bg-slate-50 p-3${
              isRowEditable ? ' cursor-pointer' : ''
            }`}
            onClick={
              onEdit
                ? () => {
                    onEdit(item);
                  }
                : undefined
            }
          >
            {/* Primary info */}
            <div className='flex items-start gap-2'>
              {selectable && (
                <input
                  type='checkbox'
                  aria-label='Select row'
                  checked={selectedKeys?.has(keyExtractor(item)) ?? false}
                  onClick={(event) => {
                    event.stopPropagation();
                  }}
                  onChange={() => {
                    onToggleRow?.(keyExtractor(item));
                  }}
                />
              )}
              {primaryColumn && (
                <div className='font-medium text-slate-900'>
                  {primaryColumn.render(item)}
                </div>
              )}
            </div>
            {/* Secondary info */}
            {secondaryColumn && (
              <div className='mt-0.5 text-sm text-slate-600'>
                {secondaryColumn.render(item)}
              </div>
            )}
            {/* Detail rows */}
            {detailColumns.length > 0 && (
              <div className='mt-2 space-y-1 border-t border-slate-200 pt-2'>
                {detailColumns.map((column) => (
                  <div
                    key={column.key}
                    className='flex items-start justify-between gap-2 text-sm'
                  >
                    <span className='text-slate-500'>{column.header}:</span>
                    <span className='text-right text-slate-700'>
                      {column.render(item)}
                    </span>
                  </div>
                ))}
              </div>
            )}
            {/* Actions */}
            {hasActions && (
              <div
                className='mt-3 flex gap-2 border-t border-slate-200 pt-3'
                onClick={(event) => {
                  event.stopPropagation();
                }}
              >
                {renderActions ? renderActions(item, 'mobile') : null}
                {onDelete && (
                  <Button
                    type='button'
                    size='sm'
                    variant='danger'
                    onClick={() => onDelete(item)}
                    className='flex-1'
                    title='Delete'
                    aria-label='Delete'
                  >
                    <DeleteIcon className='h-4 w-4' />
                  </Button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Load more button */}
      {nextCursor && onLoadMore && (
        <div className='mt-4'>
          <Button
            type='button'
            variant='secondary'
            onClick={onLoadMore}
            disabled={isLoading}
            className='w-full sm:w-auto'
          >
            {isLoading ? 'Loading...' : 'Load more'}
          </Button>
        </div>
      )}
    </>
  );
}
