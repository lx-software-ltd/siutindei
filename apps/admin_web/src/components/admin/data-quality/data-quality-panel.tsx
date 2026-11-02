'use client';

import type { ReactNode, Ref } from 'react';

import type { ReviewScope } from '@/hooks/use-data-quality-queue';
import { StatusBanner } from '@/components/status-banner';
import {
  AdminDataTableCell,
  AdminDataTableCellMeta,
  AdminDataTableHeadCell,
  type AdminDataTableColumnPriority,
} from '@/components/ui/admin-data-table';
import { AdminTableName } from '@/components/ui/admin-table-value';
import { AdminKpiCard } from '@/components/ui/admin-kpi-card';
import { AdminFilterBar, AdminFilterField } from '@/components/ui/admin-filter-bar';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ResourceTableShell } from '@/components/ui/resource-table-shell';
import { Select } from '@/components/ui/select';
import { ModelBudgetCard } from './sweep-shared';

interface QualityQueue<T extends { id: string }> {
  list: {
    items: T[];
    isLoading: boolean;
    isLoadingMore: boolean;
    hasMore: boolean;
    loadMore: () => void;
    error: string;
  };
  notice: string;
  error: string;
  pending: number;
  sweepProgress: string | null;
  scanningScope: string | null;
  sweepBusy: boolean;
  selection: {
    selected: { size: number; has: (id: string) => boolean };
    selectScope: string;
    selectAllRef: Ref<HTMLInputElement>;
    headerChecked: boolean;
    headerLabel: string;
    cycleHeader: () => void;
    toggleRow: (id: string, checked: boolean) => void;
  };
  expanded: {
    isExpanded: (id: string) => boolean;
    toggle: (id: string) => void;
  };
  sweep: (scope: ReviewScope) => Promise<void>;
  bulk: (action: 'apply' | 'dismiss') => Promise<void>;
  budget: {
    monthCost: number;
    limit: number;
    value: string;
    onChange: (value: string) => void;
    save: () => Promise<void>;
  } | null;
}

export interface QualityColumn<T> {
  header: string;
  priority?: Exclude<AdminDataTableColumnPriority, 'primary'>;
  metaLabel?: string;
  empty?: (item: T) => boolean;
  cell: (item: T) => ReactNode;
}

export function QualityText({
  id,
  label,
  value,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <AdminFilterField>
      <Input
        id={id}
        aria-label={label}
        value={value}
        placeholder={label}
        onChange={(event) => onChange(event.target.value)}
      />
    </AdminFilterField>
  );
}

export function QualitySelect({
  id,
  label,
  value,
  onChange,
  options,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: readonly (readonly [string, string])[];
}) {
  return (
    <AdminFilterField>
      <Select
        id={id}
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map(([optionValue, optionLabel]) => (
          <option key={optionValue || label} value={optionValue}>
            {optionLabel}
          </option>
        ))}
      </Select>
    </AdminFilterField>
  );
}

export function QualityFilters({ children }: { children: ReactNode }) {
  return <AdminFilterBar>{children}</AdminFilterBar>;
}

export const STATUS_FILTERS = [
  ['pending', 'Pending'],
  ['applied', 'Applied'],
  ['dismissed', 'Dismissed'],
] as const;

export function DataQualityPanel<T extends { id: string }>({
  pageName,
  noticeTitle,
  queue,
  scope,
  columns,
  filters,
  detail,
  emptyLabel,
  getLabel,
  middleColumnCount,
  extraActions,
  settings,
  budgetDescription,
  budgetInputId,
}: {
  pageName: string;
  noticeTitle: string;
  queue: QualityQueue<T>;
  scope?: ReactNode;
  columns: QualityColumn<T>[];
  filters: ReactNode;
  detail: ReactNode;
  emptyLabel: string;
  getLabel: (item: T) => string;
  middleColumnCount: number;
  extraActions?: ReactNode;
  settings?: ReactNode;
  budgetDescription?: string;
  budgetInputId?: string;
}) {
  const { selected, selectScope, selectAllRef, headerChecked, headerLabel, cycleHeader, toggleRow } =
    queue.selection;
  const [first, ...rest] = columns;
  const hidden = rest.filter((column) => column.priority);

  return (
    <div className='space-y-4'>
      <h2 className='sr-only'>{pageName}</h2>
      {scope}
      {queue.notice ? (
        <StatusBanner kind='info' title={noticeTitle}>
          {queue.notice}
        </StatusBanner>
      ) : null}
      {queue.error ? <StatusBanner kind='error'>{queue.error}</StatusBanner> : null}
      {selectScope === 'all' ? (
        <StatusBanner kind='info' title='Selection'>
          All matching records are selected, including rows not on this page.
        </StatusBanner>
      ) : null}
      <div className='grid gap-3 sm:grid-cols-3'>
        <AdminKpiCard label='Pending' value={queue.pending} />
        {queue.sweepProgress ? <AdminKpiCard label='Sweep' value={queue.sweepProgress} /> : null}
      </div>
      <ResourceTableShell
        ariaLabel={pageName}
        actions={
          <>
            <Button
              type='button'
              onClick={() => void queue.sweep('pending_review')}
              loading={queue.scanningScope === 'pending_review'}
              loadingLabel='Scanning…'
              disabled={queue.sweepBusy}
            >
              Sweep pending
            </Button>
            <Button
              type='button'
              onClick={() => void queue.sweep('all')}
              loading={queue.scanningScope === 'all'}
              loadingLabel='Scanning…'
              disabled={queue.sweepBusy}
            >
              Sweep all orgs
            </Button>
            <Button
              type='button'
              variant='secondary'
              onClick={() => void queue.bulk('apply')}
              disabled={selectScope !== 'all' && selected.size === 0}
            >
              Apply selected
            </Button>
            <Button
              type='button'
              variant='secondary'
              onClick={() => void queue.bulk('dismiss')}
              disabled={selectScope !== 'all' && selected.size === 0}
            >
              Dismiss selected
            </Button>
            {extraActions}
          </>
        }
        rows={queue.list.items as T[]}
        getLabel={getLabel}
        middleColumnCount={middleColumnCount}
        hasActions={false}
        isExpanded={queue.expanded.isExpanded}
        onToggle={queue.expanded.toggle}
        detail={detail}
        isLoading={queue.list.isLoading}
        isLoadingMore={queue.list.isLoadingMore}
        hasMore={queue.list.hasMore}
        onLoadMore={() => void queue.list.loadMore()}
        error={queue.list.error}
        emptyLabel={emptyLabel}
        filters={filters}
        leadingHead={
          <input
            ref={selectAllRef}
            type='checkbox'
            aria-label={headerLabel}
            checked={headerChecked}
            onChange={cycleHeader}
          />
        }
        renderLeading={(item) => (
          <input
            type='checkbox'
            aria-label='Select row'
            checked={selectScope === 'all' || selected.has(item.id)}
            onClick={(event) => event.stopPropagation()}
            onChange={(event) => {
              toggleRow(item.id, event.target.checked);
            }}
          />
        )}
        head={
          <>
            {columns.map((column) => (
              <AdminDataTableHeadCell key={column.header} priority={column.priority}>
                {column.header}
              </AdminDataTableHeadCell>
            ))}
          </>
        }
        renderCells={(item) => (
          <>
            <AdminDataTableCell>
              <AdminTableName>{first?.cell(item)}</AdminTableName>
              {hidden.map((column) => (
                <AdminDataTableCellMeta
                  key={column.header}
                  until={column.priority ?? 'secondary'}
                  label={column.metaLabel ?? column.header}
                  empty={column.empty?.(item)}
                >
                  {column.cell(item)}
                </AdminDataTableCellMeta>
              ))}
            </AdminDataTableCell>
            {rest.map((column) => (
              <AdminDataTableCell key={column.header} priority={column.priority}>
                {column.cell(item)}
              </AdminDataTableCell>
            ))}
          </>
        )}
      />
      {settings}
      {queue.budget && budgetDescription && budgetInputId ? (
        <ModelBudgetCard
          monthCost={queue.budget.monthCost}
          limit={queue.budget.limit}
          value={queue.budget.value}
          onChange={queue.budget.onChange}
          onSave={() => void queue.budget?.save()}
          inputId={budgetInputId}
          description={budgetDescription}
        />
      ) : null}
    </div>
  );
}
